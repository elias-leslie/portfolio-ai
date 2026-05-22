"""L1 macro deployment gate API.

Read-only endpoints exposing the latest gate snapshot, history, and
backtest helpers. All shapes are deterministic — composite + zone are
computed off persisted ``signal_macro_snapshots`` rows.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..macro_gate import repository
from ..macro_gate.backtest.monte_carlo import as_dict as sensitivity_as_dict
from ..macro_gate.backtest.monte_carlo import run_sensitivity
from ..macro_gate.backtest.walk_forward import replay, sanity_checks
from ..macro_gate.scoring import WEIGHTS, ZONES
from ..macro_gate.service import run as run_macro_gate

logger = get_logger(__name__)
router = APIRouter(prefix="/api/macro", tags=["macro-gate"])


class MacroSnapshotResponse(BaseModel):
    snapshot_date: str
    deployment_score: float
    zone: str
    coverage: float | None = None
    components: dict[str, float | None]
    raw: dict[str, float | None]
    weights: dict[str, float] = Field(default_factory=dict)
    component_quality: dict[str, dict[str, Any]] = Field(default_factory=dict)
    computed_at: str | None = None


class MacroHistoryResponse(BaseModel):
    snapshots: list[MacroSnapshotResponse]
    weights: dict[str, float]
    zones: list[str] = Field(default_factory=lambda: list(ZONES))


class BacktestResponse(BaseModel):
    start: str
    end: str
    rows: list[dict[str, Any]]
    sanity: dict[str, str]


class SensitivityResponse(BaseModel):
    samples: int
    perturbation: float
    baseline_zone_counts: dict[str, int]
    perturbed_zone_counts: dict[str, int]
    zone_change_rate: float
    score_std_avg: float


def _snapshot_to_response(row: dict) -> MacroSnapshotResponse:
    components = {
        "vix": row.get("vix_score"),
        "term": row.get("term_score"),
        "breadth": row.get("breadth_score"),
        "credit": row.get("credit_score"),
        "putcall": row.get("putcall_score"),
        "crowding": row.get("crowding_score"),
    }
    raw = {
        "vix_close": row.get("vix_close"),
        "term_spread_bps": row.get("term_spread_bps"),
        "breadth_pct": row.get("breadth_pct"),
        "hy_spread": row.get("hy_spread"),
        "put_call_ratio": row.get("put_call_ratio"),
        "factor_crowding_corr": row.get("factor_crowding_corr"),
    }
    raw_json = row.get("raw_json") or {}
    coverage = None
    if isinstance(raw_json, dict):
        coverage = raw_json.get("coverage")
    weights = raw_json.get("weights") if isinstance(raw_json, dict) else None
    component_quality = (
        raw_json.get("component_quality") if isinstance(raw_json, dict) else None
    )
    return MacroSnapshotResponse(
        snapshot_date=row["snapshot_date"],
        deployment_score=row["deployment_score"],
        zone=row["zone"],
        coverage=coverage,
        components=components,
        raw=raw,
        weights=weights if isinstance(weights, dict) else dict(WEIGHTS),
        component_quality=component_quality if isinstance(component_quality, dict) else {},
        computed_at=row.get("computed_at"),
    )


@router.get("/current", response_model=MacroSnapshotResponse)
async def current() -> MacroSnapshotResponse:
    snapshot = await run_in_threadpool(repository.get_latest)
    if snapshot is None:
        # On-demand compute when no persisted row exists yet (first-run convenience).
        gate_output = await run_in_threadpool(run_macro_gate)
        if gate_output is None:
            raise HTTPException(status_code=503, detail="macro_gate_inputs_unavailable")
        snapshot = await run_in_threadpool(repository.get_latest)
    if snapshot is None:
        raise HTTPException(status_code=503, detail="macro_gate_persist_failed")
    return _snapshot_to_response(snapshot)


@router.get("/history", response_model=MacroHistoryResponse)
async def history(days: int = Query(default=730, ge=1, le=3650)) -> MacroHistoryResponse:
    rows = await run_in_threadpool(repository.get_history, days)
    return MacroHistoryResponse(
        snapshots=[_snapshot_to_response(row) for row in rows],
        weights=dict(WEIGHTS),
    )


@router.get("/backtest", response_model=BacktestResponse)
async def backtest(
    start: date | None = Query(default=None, description="Inclusive start date"),
    end: date | None = Query(default=None, description="Inclusive end date"),
) -> BacktestResponse:
    today = date.today()
    end = end or today
    start = start or (today - timedelta(days=730))
    rows = await run_in_threadpool(replay, start, end)
    sanity = await run_in_threadpool(sanity_checks, rows)
    return BacktestResponse(
        start=start.isoformat(),
        end=end.isoformat(),
        rows=[
            {
                "snapshot_date": row.snapshot_date.isoformat(),
                "deployment_score": row.deployment_score,
                "zone": row.zone,
                "coverage": row.coverage,
            }
            for row in rows
        ],
        sanity=sanity,
    )


@router.get("/sensitivity", response_model=SensitivityResponse)
async def sensitivity(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    samples: int = Query(default=1000, ge=10, le=10000),
    perturbation: float = Query(default=0.10, ge=0.0, le=0.5),
) -> SensitivityResponse:
    today = date.today()
    end = end or today
    start = start or (today - timedelta(days=365))
    result = await run_in_threadpool(run_sensitivity, start, end, samples, perturbation)
    payload = sensitivity_as_dict(result)
    return SensitivityResponse(**payload)
