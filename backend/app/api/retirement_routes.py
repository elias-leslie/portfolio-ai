"""Retirement Monte Carlo router (F5).

Thin serializer over :class:`RetirementPlanningService`. Three
endpoints per the plan:

- ``POST /api/retirement/scenarios`` — build inputs, run + persist
- ``GET /api/retirement/scenarios?household_id=…`` — list summaries
- ``GET /api/retirement/scenarios/{id}?detail=…`` — show one (compact
  by default, ``?detail=true`` adds percentile paths + CMA snapshot)

No Hatchet workflow; runs are user-initiated, capped at 50k trials.
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
from app.portfolio.contracts.retirement import (
    RetirementACAConfig,
    RetirementCollegeYear,
    RetirementInputs,
    RetirementPreview,
    ScenarioResults,
    ScenarioSummary,
    WithdrawalConfig,
)
from app.services.retirement_allocation_scenarios_service import (
    AllocationScenariosReplaceRequest,
)
from app.services.retirement_planning_service import (
    DEFAULT_LIST_LIMIT,
    DEFAULT_PREVIEW_TRIALS,
    DEFAULT_TRIALS,
    MAX_LIST_LIMIT,
    MAX_TRIALS,
    RetirementPlanningService,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/retirement", tags=["retirement"])


@lru_cache(maxsize=1)
def _storage() -> Any:
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _service() -> RetirementPlanningService:
    return RetirementPlanningService(_storage())


class AllocationHoldingRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=16)
    weight: float = Field(..., ge=0.0)
    dividend_yield: float | None = Field(None, ge=0.0, le=100.0)


class RunScenarioRequest(BaseModel):
    household_id: str = Field(..., min_length=1, max_length=64)
    name: str | None = Field(None, max_length=128)
    trials: int = Field(DEFAULT_TRIALS, ge=1, le=MAX_TRIALS)
    seed: int | None = Field(None)
    annual_expenses: float | None = Field(None, ge=0.0)
    annual_contribution: float | None = Field(None, ge=0.0)
    asset_allocation: dict[str, float] | None = None
    allocation_holdings: list[AllocationHoldingRequest] | None = None
    cash_yield: float | None = Field(None, ge=0.0, le=0.2)
    retirement_age: int | None = Field(None, ge=18, le=120)
    spouse_retirement_age: int | None = Field(None, ge=18, le=120)
    horizon_years: int | None = Field(None, ge=1, le=70)
    inflation_rate: float | None = Field(None, ge=0.0, le=0.2)
    social_security_payable_ratio: float | None = Field(None, ge=0.0, le=1.0)
    primary_age: int | None = Field(None, ge=18, le=120)
    spouse_age: int | None = Field(None, ge=18, le=120)
    # Partial-retirement window levers (REAL $); net income gates the
    # feature, None = off (preview falls back to profile columns).
    spouse_net_monthly_income: float | None = Field(None, ge=0.0)
    partial_retirement_monthly_spend: float | None = Field(None, ge=0.0)
    spouse_gross_annual_income: float | None = Field(None, ge=0.0)
    as_of_date: date | None = None
    # Floor-and-upside withdrawal plan; omit for profile-persisted
    # defaults (preview) or spend-the-gap semantics (scenarios).
    withdrawal: WithdrawalConfig | None = None


class PreviewRequest(RunScenarioRequest):
    # Interactive preview defaults to fewer trials than persisted scenarios —
    # it reruns on every slider change and latency matters more than tail
    # precision. Explicit ``trials`` still wins, up to MAX_TRIALS.
    trials: int = Field(DEFAULT_PREVIEW_TRIALS, ge=1, le=MAX_TRIALS)
    monthly_spend: float | None = Field(None, ge=0.0)
    primary_social_security_monthly: float | None = Field(None, ge=0.0)
    spouse_social_security_monthly: float | None = Field(None, ge=0.0)
    primary_social_security_annual_earnings: float | None = Field(None, ge=0.0)
    spouse_social_security_annual_earnings: float | None = Field(None, ge=0.0)
    primary_social_security_start_age: int | None = Field(None, ge=62, le=70)
    spouse_social_security_start_age: int | None = Field(None, ge=62, le=70)
    # Explicit college schedule (even empty) wins over the persisted one.
    college_schedule: list[RetirementCollegeYear] | None = None
    # Explicit ACA config (tier/OOP/covered-lives lever) wins over the
    # profile defaults; premium anchors still resolve server-side.
    aca: RetirementACAConfig | None = None


class IncomeStreamOverrideRequest(BaseModel):
    owner_name: str | None = Field(None, max_length=255)
    status: str | None = Field(None, max_length=32)
    merged_into_stream_key: str | None = Field(None, max_length=64)
    label: str | None = Field(None, max_length=255)


@router.post("/scenarios")
async def run_scenario(payload: RunScenarioRequest) -> dict[str, Any]:
    """Build inputs from household + portfolio, run the simulation, persist."""
    service = _service()

    def _execute() -> ScenarioResults:
        inputs: RetirementInputs = service.build_inputs(
            payload.household_id,
            annual_expenses=payload.annual_expenses,
            annual_contribution=payload.annual_contribution,
            asset_allocation=payload.asset_allocation,
            allocation_holdings=payload.allocation_holdings,
            cash_yield=payload.cash_yield,
            retirement_age=payload.retirement_age,
            spouse_retirement_age=payload.spouse_retirement_age,
            horizon_years=payload.horizon_years,
            inflation_rate=payload.inflation_rate,
            social_security_payable_ratio=payload.social_security_payable_ratio,
            primary_age=payload.primary_age,
            spouse_age=payload.spouse_age,
            spouse_net_monthly_income=payload.spouse_net_monthly_income,
            partial_retirement_monthly_spend=payload.partial_retirement_monthly_spend,
            spouse_gross_annual_income=payload.spouse_gross_annual_income,
            as_of_date=payload.as_of_date,
        )
        if payload.withdrawal is not None:
            inputs = inputs.model_copy(update={"withdrawal": payload.withdrawal})
        sim = service.run_simulation(inputs, trials=payload.trials, seed=payload.seed)
        name = payload.name or _default_scenario_name(inputs)
        return service.save_scenario(
            name=name, inputs=inputs, sim=sim, trials=payload.trials
        )

    results = await run_in_threadpool(_execute)
    return results.model_dump(mode="json")


@router.post("/preview")
async def preview(payload: PreviewRequest) -> dict[str, Any]:
    """Return a non-persisted account-type-aware retirement preview."""
    service = _service()

    def _execute() -> RetirementPreview:
        return service.preview(
            payload.household_id,
            annual_expenses=payload.annual_expenses,
            monthly_spend=payload.monthly_spend,
            asset_allocation=payload.asset_allocation,
            allocation_holdings=payload.allocation_holdings,
            cash_yield=payload.cash_yield,
            retirement_age=payload.retirement_age,
            spouse_retirement_age=payload.spouse_retirement_age,
            horizon_years=payload.horizon_years,
            annual_contribution=payload.annual_contribution,
            inflation_rate=payload.inflation_rate,
            social_security_payable_ratio=payload.social_security_payable_ratio,
            primary_age=payload.primary_age,
            spouse_age=payload.spouse_age,
            primary_social_security_monthly=payload.primary_social_security_monthly,
            spouse_social_security_monthly=payload.spouse_social_security_monthly,
            primary_social_security_annual_earnings=payload.primary_social_security_annual_earnings,
            spouse_social_security_annual_earnings=payload.spouse_social_security_annual_earnings,
            primary_social_security_start_age=payload.primary_social_security_start_age,
            spouse_social_security_start_age=payload.spouse_social_security_start_age,
            withdrawal=payload.withdrawal,
            college_schedule=(
                tuple(payload.college_schedule) if payload.college_schedule is not None else None
            ),
            aca=payload.aca,
            spouse_net_monthly_income=payload.spouse_net_monthly_income,
            partial_retirement_monthly_spend=payload.partial_retirement_monthly_spend,
            spouse_gross_annual_income=payload.spouse_gross_annual_income,
            trials=payload.trials,
            seed=payload.seed,
            as_of_date=payload.as_of_date,
        )

    preview_result = await run_in_threadpool(_execute)
    return preview_result.model_dump(mode="json")


@router.get("/scenarios")
async def list_scenarios(
    household_id: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(DEFAULT_LIST_LIMIT, ge=1, le=MAX_LIST_LIMIT),
) -> list[dict[str, Any]]:
    service = _service()
    rows: list[ScenarioSummary] = await run_in_threadpool(
        service.list_scenarios, household_id, limit=limit
    )
    return [row.model_dump(mode="json") for row in rows]


@router.get("/scenarios/{scenario_id}")
async def show_scenario(
    scenario_id: str,
    detail: bool = Query(False),
) -> dict[str, Any]:
    service = _service()
    results: ScenarioResults | None = await run_in_threadpool(
        service.show_scenario, scenario_id, detail=detail
    )
    if results is None:
        raise HTTPException(status_code=404, detail="scenario_not_found")
    return results.model_dump(mode="json")


@lru_cache(maxsize=1)
def _allocation_scenarios_service() -> Any:
    module = import_module("app.services.retirement_allocation_scenarios_service")
    return module.AllocationScenariosService(_storage())


@router.get("/allocation-scenarios")
async def list_allocation_scenarios() -> list[dict[str, Any]]:
    """Saved what-if allocation mixes for the allocation lab."""
    rows = await run_in_threadpool(_allocation_scenarios_service().list_scenarios)
    return [row.model_dump(mode="json") for row in rows]


@router.put("/allocation-scenarios")
async def replace_allocation_scenarios(
    payload: AllocationScenariosReplaceRequest,
) -> list[dict[str, Any]]:
    """Replace the full saved scenario list (UI manages it as a set)."""
    rows = await run_in_threadpool(
        _allocation_scenarios_service().replace_scenarios, payload
    )
    return [row.model_dump(mode="json") for row in rows]


@lru_cache(maxsize=1)
def _aca_marketplace_service() -> Any:
    module = import_module("app.services.aca_marketplace_ingest_service")
    return module.AcaMarketplaceIngestService()


class AcaPlansRefreshRequest(BaseModel):
    plan_year: int = Field(2026, ge=2014, le=2100)
    xlsx_path: str | None = None


@router.get("/aca-estimate")
async def aca_estimate(
    magi: float = Query(..., ge=0.0),
    ages: str | None = Query(None, max_length=64, description="CSV ages of covered lives"),
    household_size: int | None = Query(None, ge=1, le=12),
    tier: str = Query("silver", pattern="^(silver|bronze)$"),
) -> dict[str, Any]:
    """Premium/subsidy estimate at an explicit MAGI (inspectable PTC math)."""
    parsed_ages = (
        tuple(int(part) for part in ages.split(",") if part.strip()) if ages else None
    )
    result = await run_in_threadpool(
        lambda: _service().aca_estimate(
            magi_annual=magi, ages=parsed_ages, household_size=household_size, tier=tier
        )
    )
    if result is None:
        raise HTTPException(status_code=404, detail="aca_plans_not_ingested")
    return result


@router.get("/aca-plans")
async def list_aca_plans(
    plan_year: int | None = Query(None, ge=2014, le=2100),
    fips_county_code: str | None = Query(None, max_length=5),
) -> list[dict[str, Any]]:
    """Ingested CMS landscape plans (age-rated premiums by metal tier)."""
    return await run_in_threadpool(
        lambda: _aca_marketplace_service().list_plans(
            plan_year=plan_year, fips_county_code=fips_county_code
        )
    )


@router.post("/aca-plans/refresh")
async def refresh_aca_plans(payload: AcaPlansRefreshRequest) -> dict[str, Any]:
    """Re-ingest the CMS landscape PUF for the tracked counties."""
    try:
        return await run_in_threadpool(
            lambda: _aca_marketplace_service().ingest(
                plan_year=payload.plan_year, xlsx_path=payload.xlsx_path
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ACA PUF ingest failed: {exc}") from exc


@lru_cache(maxsize=1)
def _spending_actuals_service() -> Any:
    module = import_module("app.services.retirement_spending_actuals_service")
    return module.RetirementSpendingActualsService()


@router.get("/spending-actuals")
async def spending_actuals() -> dict[str, Any]:
    """Monthly spend run-rates derived from the deduped Money ledger."""
    result = await run_in_threadpool(_spending_actuals_service().build)
    return result.model_dump(mode="json")


@lru_cache(maxsize=1)
def _income_actuals_service() -> Any:
    module = import_module("app.services.retirement_income_actuals_service")
    return module.RetirementIncomeActualsService()


@router.get("/income-actuals")
async def income_actuals() -> dict[str, Any]:
    """Recurring income streams auto-detected from the Money ledger."""
    result = await run_in_threadpool(_income_actuals_service().build)
    return result.model_dump(mode="json")


@router.post("/income-actuals/streams/{stream_key}/override")
async def update_income_stream_override(
    stream_key: str, payload: IncomeStreamOverrideRequest
) -> dict[str, Any]:
    """Persist owner/status overrides for an auto-detected income stream."""
    try:
        result = await run_in_threadpool(
            _income_actuals_service().update_override, stream_key, payload
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump(mode="json")


def _default_scenario_name(inputs: RetirementInputs) -> str:
    return (
        f"Retire at {inputs.retirement_age}, "
        f"{inputs.horizon_years}y horizon, "
        f"${inputs.annual_expenses:,.0f}/yr"
    )
