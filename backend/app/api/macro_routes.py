"""L1 macro deployment gate API.

Read-only endpoints exposing the latest gate snapshot, history, and
backtest helpers. All shapes are deterministic — composite + zone are
computed off persisted ``signal_macro_snapshots`` rows.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..macro_gate import conditions as macro_conditions
from ..macro_gate import conditions_history, repository
from ..macro_gate.backtest.monte_carlo import as_dict as sensitivity_as_dict
from ..macro_gate.backtest.monte_carlo import run_sensitivity
from ..macro_gate.backtest.walk_forward import replay, sanity_checks
from ..macro_gate.scoring import WEIGHTS, ZONES
from ..macro_gate.service import run as run_macro_gate
from ..services.market_events_service import get_macro_calendar_cluster
from ..utils.market_hours import NY_TZ

logger = get_logger(__name__)
router = APIRouter(prefix="/api/macro", tags=["macro-gate"])
CURRENT_MACRO_MAX_AGE = timedelta(minutes=5)


def _current_market_date() -> date:
    return datetime.now(NY_TZ).date()


def _next_catalyst() -> dict[str, Any] | None:
    """Next high-impact macro event (FOMC/CPI/NFP/...) for the Today panel.

    Best-effort: a calendar read failure must never break the conditions
    endpoint, so we swallow and return None (the catalyst tile simply hides).
    """
    try:
        cluster = get_macro_calendar_cluster(market_date=_current_market_date())
        return cluster.get("next_high_impact_event")
    except Exception:
        logger.debug("next_catalyst_lookup_failed", exc_info=True)
        return None


class MacroSnapshotResponse(BaseModel):
    snapshot_date: str
    deployment_score: float
    zone: str
    coverage: float | None = None
    components: dict[str, float | None]
    raw: dict[str, float | None]
    weights: dict[str, float] = Field(default_factory=dict)
    component_quality: dict[str, dict[str, Any]] = Field(default_factory=dict)
    degraded: bool = False
    stale_components: list[str] = Field(default_factory=list)
    computed_at: str | None = None


class MacroHistoryResponse(BaseModel):
    snapshots: list[MacroSnapshotResponse]
    weights: dict[str, float]
    zones: list[str] = Field(default_factory=lambda: list(ZONES))


class MacroConditionAlertResponse(BaseModel):
    active: bool
    priority: str | None = None
    reason: str | None = None


class MacroConditionTrendResponse(BaseModel):
    key: str
    label: str
    direction: str
    tone: str
    delta: float | None = None
    change_label: str
    summary: str
    window_days: int
    latest_date: str | None = None
    prior_date: str | None = None
    reversal: bool
    reversal_label: str | None = None
    sparkline: list[float] = Field(default_factory=list)


class MacroConditionShiftResponse(BaseModel):
    key: str
    label: str
    detail: str
    tone: str
    reversal: bool = False


class MacroConditionEvidenceResponse(BaseModel):
    key: str
    label: str
    value: str
    detail: str
    tone: str
    tooltip: str
    trend: MacroConditionTrendResponse | None = None


class MacroConditionBondSignalsResponse(BaseModel):
    as_of: str | None = None
    ten_year_two_year_bps: float | None = None
    ten_year_three_month_bps: float | None = None


class MacroConditionCreditSignalResponse(BaseModel):
    latest_date: str | None = None
    latest_value: float | None = None
    prior_date: str | None = None
    prior_value: float | None = None
    change_bps: float | None = None


class MacroConditionDrivingResponse(BaseModel):
    headline: str
    tone: str = "neutral"


class MacroConditionNextCatalystResponse(BaseModel):
    event_type: str
    event_date: str
    event_time: str | None = None
    title: str
    impact_score: int


class MacroConditionOvernightSignalResponse(BaseModel):
    key: str
    label: str
    symbol: str
    change_pct: float | None = None
    direction: str
    magnitude: str
    live: bool
    note: str | None = None


class MacroConditionOvernightLeanResponse(BaseModel):
    applies: bool
    session: str
    session_label: str
    direction: str
    confidence: int
    live_count: int
    headline: str
    stress_score: int | None = None
    drove_caution: bool = False
    note: str | None = None
    as_of: str | None = None
    signals: list[MacroConditionOvernightSignalResponse] = Field(default_factory=list)


class MacroConditionTriggerResponse(BaseModel):
    key: str
    label: str
    current: float | None = None
    current_display: str
    trigger: float
    trigger_display: str
    baseline: float
    direction: str
    unit: str = ""
    progress: float | None = None
    fired: bool = False
    tone: str = "neutral"
    note: str = ""


class MacroConditionsResponse(BaseModel):
    snapshot_date: str | None = None
    computed_at: str | None = None
    state: str
    stress_score: int | None = None
    macro_stress_score: int | None = None
    tape_pressure_score: int | None = None
    overall_caution_score: int | None = None
    overall_read: str = "unavailable"
    primary_driver: str = "data_limited"
    driver_detail: str = ""
    deployment_score: float | None = None
    macro_zone: str | None = None
    coverage: float | None = None
    tape_available: bool = False
    tape_state: str | None = None
    tape_as_of: str | None = None
    market_session: str | None = None
    tape_status: str | None = None
    next_catalyst: MacroConditionNextCatalystResponse | None = None
    overnight_lean: MacroConditionOvernightLeanResponse | None = None
    summary: str
    action_text: str
    driving: MacroConditionDrivingResponse | None = None
    what_matters: list[str] = Field(default_factory=list)
    what_to_do: list[str] = Field(default_factory=list)
    watch_items: list[str] = Field(default_factory=list)
    triggers: list[MacroConditionTriggerResponse] = Field(default_factory=list)
    trend: dict[str, MacroConditionTrendResponse] = Field(default_factory=dict)
    market_shifts: list[MacroConditionShiftResponse] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    alert: MacroConditionAlertResponse
    bond_signals: MacroConditionBondSignalsResponse
    credit_signal: MacroConditionCreditSignalResponse
    evidence: list[MacroConditionEvidenceResponse] = Field(default_factory=list)


class ConditionsHistoryPoint(BaseModel):
    recorded_at: str
    snapshot_date: str
    deployment_score: float | None = None
    macro_stress: int | None = None
    tape_pressure: int | None = None
    overall_caution: int | None = None
    overall_read: str | None = None
    primary_driver: str | None = None
    state: str | None = None
    tape_available: bool = False
    tape_state: str | None = None
    market_session: str | None = None


class ConditionsHistoryResponse(BaseModel):
    points: list[ConditionsHistoryPoint]
    severe_threshold: int = macro_conditions.SEVERE_STRESS_THRESHOLD
    selective_threshold: int = macro_conditions.SELECTIVE_CAUTION_THRESHOLD


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
    component_quality = raw_json.get("component_quality") if isinstance(raw_json, dict) else None
    degraded = bool(raw_json.get("degraded")) if isinstance(raw_json, dict) else False
    stale_components = raw_json.get("stale_components") if isinstance(raw_json, dict) else None
    return MacroSnapshotResponse(
        snapshot_date=row["snapshot_date"],
        deployment_score=row["deployment_score"],
        zone=row["zone"],
        coverage=coverage,
        components=components,
        raw=raw,
        weights=weights if isinstance(weights, dict) else dict(WEIGHTS),
        component_quality=component_quality if isinstance(component_quality, dict) else {},
        degraded=degraded,
        stale_components=stale_components if isinstance(stale_components, list) else [],
        computed_at=row.get("computed_at"),
    )


def _parse_snapshot_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.split("T")[0])
        except ValueError:
            return None
    return None


def _parse_computed_at(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def _should_refresh_current_snapshot(snapshot: dict | None) -> bool:
    if snapshot is None:
        return True
    snapshot_date = _parse_snapshot_date(snapshot.get("snapshot_date"))
    if snapshot_date is None or snapshot_date < _current_market_date():
        return True
    computed_at = _parse_computed_at(snapshot.get("computed_at"))
    if computed_at is None:
        return True
    return datetime.now(UTC) - computed_at.astimezone(UTC) > CURRENT_MACRO_MAX_AGE


def _latest_snapshot_or_refresh(*, force_quote_refresh: bool = False) -> dict | None:
    snapshot = repository.get_latest()
    should_refresh = force_quote_refresh or _should_refresh_current_snapshot(snapshot)
    if should_refresh:
        gate_output = run_macro_gate(
            force_quote_refresh=True,
            current_quote_max_age_minutes=0,
        )
        if gate_output is None and snapshot is None:
            return None
        snapshot = repository.get_latest() or snapshot
    return snapshot


def _latest_snapshot_or_bootstrap() -> dict | None:
    snapshot = repository.get_latest()
    if snapshot is not None:
        return snapshot
    return _latest_snapshot_or_refresh()


@router.get("/current", response_model=MacroSnapshotResponse)
async def current() -> MacroSnapshotResponse:
    snapshot = await run_in_threadpool(_latest_snapshot_or_refresh)
    if snapshot is None:
        raise HTTPException(status_code=503, detail="macro_gate_persist_failed")
    return _snapshot_to_response(snapshot)


@router.get("/conditions", response_model=MacroConditionsResponse)
async def current_conditions() -> MacroConditionsResponse:
    snapshot = await run_in_threadpool(_latest_snapshot_or_bootstrap)
    if snapshot is None:
        raise HTTPException(status_code=503, detail="macro_gate_inputs_unavailable")
    payload = await run_in_threadpool(macro_conditions.get_conditions_payload, snapshot)
    # Best-effort: log the headline numbers so the trend line can show what the
    # number was and when it moved. record() change-detects and swallows errors.
    await run_in_threadpool(conditions_history.record, payload)
    # Surface the next high-impact macro catalyst (forward-looking, not a score).
    # Attached AFTER record() so it never enters the conditions history, and kept
    # out of get_conditions_payload so the capture cron skips this calendar read.
    payload["next_catalyst"] = await run_in_threadpool(_next_catalyst)
    return MacroConditionsResponse(**payload)


@router.get("/conditions/history", response_model=ConditionsHistoryResponse)
async def conditions_history_endpoint(
    days: int = Query(default=90, ge=1, le=730),
) -> ConditionsHistoryResponse:
    rows = await run_in_threadpool(conditions_history.get_history, days)
    return ConditionsHistoryResponse(
        points=[ConditionsHistoryPoint(**row) for row in rows],
    )


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
    today = _current_market_date()
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
    today = _current_market_date()
    end = end or today
    start = start or (today - timedelta(days=365))
    result = await run_in_threadpool(run_sensitivity, start, end, samples, perturbation)
    payload = sensitivity_as_dict(result)
    return SensitivityResponse(**payload)
