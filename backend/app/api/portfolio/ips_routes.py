"""IPS (Investment Policy Statement) + drift + rebalance routes.

Thin serializers over :mod:`app.portfolio.ips`. This module owns *no*
analytics — every endpoint instantiates the canonical services via
``lru_cache`` helpers and returns the contract instances unchanged.
Token-efficient defaults are enforced here: the drift endpoint returns
:class:`DriftSummary` by default and only the full :class:`DriftReport`
when ``?summary=false``.
"""

from __future__ import annotations

from datetime import date
from functools import lru_cache
from importlib import import_module
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.portfolio.contracts.ips import (
    DriftCoverage,
    DriftReport,
    IPSScope,
    IPSTarget,
    RebalancePlan,
)
from app.portfolio.ips import IncompleteHouseholdCoverageError

logger = get_logger(__name__)

router = APIRouter(prefix="/ips", tags=["portfolio-ips"])

_NUMERIC_COVERAGE_TOLERANCE_DOLLARS = 1.0


@lru_cache(maxsize=1)
def _storage():
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _ips_service():
    return import_module("app.portfolio.ips").IPSService(_storage())


@lru_cache(maxsize=1)
def _asset_classifier():
    return import_module("app.portfolio.asset_classification").AssetClassifier(_storage())


@lru_cache(maxsize=1)
def _price_fetcher():
    return import_module("app.portfolio.price_fetcher").PriceDataFetcher(_storage())


@lru_cache(maxsize=1)
def _household_allocation_service():
    service_mod = import_module("app.services.household_allocation_service")
    return service_mod.HouseholdAllocationService(
        _storage(),
        _asset_classifier(),
        _price_fetcher(),
    )


def _household_allocation_universe():
    household_service = import_module(
        "app.services.household_finance_service"
    ).HouseholdFinanceService()
    return _household_allocation_service().build(household_service.get_dashboard())


@lru_cache(maxsize=1)
def _drift_calculator():
    ips_mod = import_module("app.portfolio.ips")
    return ips_mod.DriftCalculator(
        _storage(),
        _asset_classifier(),
        _ips_service(),
        _price_fetcher(),
        household_allocation_provider=_household_allocation_universe,
    )


@lru_cache(maxsize=1)
def _ledger():
    return import_module("app.portfolio.transactions").TransactionLedger(_storage())


@lru_cache(maxsize=1)
def _tlh_analyzer():
    tlh_mod = import_module("app.portfolio.tlh")
    return tlh_mod.TLHAnalyzer(_storage(), _ledger(), _price_fetcher())


@lru_cache(maxsize=1)
def _rebalance_planner():
    ips_mod = import_module("app.portfolio.ips")
    return ips_mod.RebalancePlanner(_drift_calculator(), _tlh_analyzer(), _ledger())


def _household_drift_coverage(
    included_value: float,
    *,
    dashboard: Any | None = None,
    totals: Any | None = None,
) -> DriftCoverage:
    """Reconcile the allocation universe to trusted household investments."""
    try:
        if dashboard is None:
            household_service = import_module(
                "app.services.household_finance_service"
            ).HouseholdFinanceService()
            dashboard = household_service.get_dashboard()
        if totals is None:
            totals = import_module(
                "app.services.household_portfolio_totals"
            ).get_effective_portfolio_totals(
                _storage(),
                dashboard=dashboard,
            )
    except Exception as exc:
        logger.warning("rebalance_coverage_check_failed", error=str(exc))
        return DriftCoverage(
            status="unverified",
            message=(
                "Household investment coverage could not be verified. Treat this "
                "allocation as incomplete and do not generate trades from it."
            ),
        )

    account_control = getattr(dashboard, "account_control", None)
    blocking_count = int(getattr(account_control, "blocking_issue_count", 0) or 0)
    if blocking_count > 0:
        return DriftCoverage(
            status="blocked",
            message=(
                f"{blocking_count} account-control issue"
                f"{'s' if blocking_count != 1 else ''} block trusted household totals. "
                "Resolve them before evaluating allocation or generating trades."
            ),
        )

    canonical_raw = getattr(totals, "household_invested_total_value", None)
    canonical_value = float(canonical_raw or 0.0)
    if canonical_value <= 0:
        return DriftCoverage(
            status="unverified",
            message=(
                "Canonical household investment value is unavailable. Treat this "
                "allocation as incomplete and do not generate trades from it."
            ),
        )
    coverage_gap = abs(canonical_value - included_value)
    if coverage_gap <= _NUMERIC_COVERAGE_TOLERANCE_DOLLARS:
        return DriftCoverage(
            status="complete",
            canonical_total_value=canonical_value,
            coverage_pct=1.0,
            excluded_value=0.0,
            message="Allocation value reconciles to canonical household investments.",
        )
    if included_value < canonical_value:
        coverage_pct = max(0.0, min(included_value / canonical_value, 1.0))
        excluded_value = canonical_value - included_value
        return DriftCoverage(
            status="partial",
            canonical_total_value=canonical_value,
            coverage_pct=coverage_pct,
            excluded_value=excluded_value,
            message=(
                "The allocation view covers only "
                f"{coverage_pct:.1%} of canonical household investments. "
                "Reconcile the excluded holdings before relying on drift or generating trades."
            ),
        )
    return DriftCoverage(
        status="mismatch",
        canonical_total_value=canonical_value,
        coverage_pct=1.0,
        excluded_value=0.0,
        message=(
            "The allocation view exceeds canonical household investments. "
            "Reconcile duplicate or misclassified holdings before relying on drift or generating trades."
        ),
    )


# ----------------------------------------------------------------------
# request bodies
# ----------------------------------------------------------------------


class IPSTargetUpsertRequest(BaseModel):
    """Body for ``PUT /api/portfolio/ips/targets``."""

    scope: IPSScope
    scope_id: str = Field(..., min_length=1, max_length=64)
    asset_class: str = Field(..., min_length=1, max_length=32)
    target_pct: float = Field(..., ge=0.0, le=1.0)
    drift_band_pct: float = Field(0.05, ge=0.0, le=1.0)
    notes: str | None = None


class RebalanceRequest(BaseModel):
    """Body for ``POST /api/portfolio/ips/rebalance``."""

    scope: IPSScope
    scope_id: str = Field(..., min_length=1, max_length=64)
    prefer_tax_advantaged: bool = True
    prefer_ltcg: bool = True
    snapshot_date: date | None = None


# ----------------------------------------------------------------------
# routes
# ----------------------------------------------------------------------


@router.get("/targets", response_model=list[IPSTarget])
async def get_targets(
    scope: IPSScope = Query(...),
    scope_id: str = Query(..., min_length=1, max_length=64),
) -> list[IPSTarget]:
    """Return all IPS targets for one (scope, scope_id)."""
    return await run_in_threadpool(_ips_service().get_targets, scope, scope_id)


@router.put("/targets", response_model=IPSTarget)
async def upsert_target(payload: IPSTargetUpsertRequest) -> IPSTarget:
    """Upsert one IPS target row, keyed on (scope, scope_id, asset_class)."""
    try:
        return await run_in_threadpool(
            _ips_service().set_target,
            scope=payload.scope,
            scope_id=payload.scope_id,
            asset_class=payload.asset_class,
            target_pct=payload.target_pct,
            drift_band_pct=payload.drift_band_pct,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/targets")
async def delete_target(
    scope: IPSScope = Query(...),
    scope_id: str = Query(..., min_length=1, max_length=64),
    asset_class: str = Query(..., min_length=1, max_length=32),
) -> dict[str, Any]:
    """Delete one IPS target row. Returns ``{deleted: bool}``."""
    deleted = await run_in_threadpool(
        _ips_service().delete_target,
        scope=scope,
        scope_id=scope_id,
        asset_class=asset_class,
    )
    return {"deleted": bool(deleted)}


@router.get("/drift")
async def get_drift(
    scope: IPSScope = Query(...),
    scope_id: str = Query(..., min_length=1, max_length=64),
    summary: bool = Query(True, description="Return compact summary; set false for full row table"),
) -> dict[str, Any]:
    """Return allocation drift for one scope.

    Default response is :class:`DriftSummary` (compact: max drift,
    classes out of band). Pass ``summary=false`` for the full
    :class:`DriftReport` with per-class rows.
    """
    if summary:
        digest = await run_in_threadpool(_drift_calculator().compute_summary, scope, scope_id)
        if scope == "household" and digest.coverage is None:
            coverage = await run_in_threadpool(
                _household_drift_coverage, digest.total_value
            )
            digest = digest.model_copy(update={"coverage": coverage})
        return digest.model_dump(mode="json")
    report: DriftReport = await run_in_threadpool(
        _drift_calculator().compute_drift, scope, scope_id
    )
    if scope == "household" and report.coverage is None:
        coverage = await run_in_threadpool(
            _household_drift_coverage, report.total_value
        )
        report = report.model_copy(update={"coverage": coverage})
    return report.model_dump(mode="json")


@router.post("/rebalance", response_model=RebalancePlan)
async def post_rebalance(payload: RebalanceRequest) -> RebalancePlan:
    """Propose a tax-aware rebalance plan for the scope.

    Three-pass: tax-advantaged-buys-first, LT-loss-and-LTCG-preferred
    sells, wash-sale-aware reroute or flag. See
    :class:`app.portfolio.ips.RebalancePlanner` for the contract.
    """
    try:
        return await run_in_threadpool(
            _rebalance_planner().propose_trades,
            payload.scope,
            payload.scope_id,
            prefer_tax_advantaged=payload.prefer_tax_advantaged,
            prefer_ltcg=payload.prefer_ltcg,
            snapshot_date=payload.snapshot_date,
        )
    except IncompleteHouseholdCoverageError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
