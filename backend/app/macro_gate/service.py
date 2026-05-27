"""Macro deployment gate service.

Pulls today's raw signal values from existing sources, builds the
composite, persists the snapshot, and returns the result for callers that
need it directly (the workflow + the read API).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from ..logging_config import get_logger
from . import repository
from .scoring import CompositeResult, RawSignals, build_composite
from .signals import factor_crowding, fear_greed_components, spx_breadth_200d, term_structure

logger = get_logger(__name__)
CROWDING_CACHE_MAX_DAYS = 10


@dataclass(frozen=True, slots=True)
class GateOutput:
    snapshot_date: date
    deployment_score: float
    zone: str
    coverage: float


@dataclass(frozen=True, slots=True)
class CollectedSignals:
    raw: RawSignals
    metadata: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CrowdingSignal:
    value: float
    as_of: date
    source: str
    status: str = "fresh"


def _quality(
    *,
    value: float | None,
    as_of: date | None,
    source: str,
    cadence: str,
    stale: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    status = "missing" if value is None else "stale" if stale else "fresh"
    return {
        "status": status,
        "as_of": as_of.isoformat() if as_of else None,
        "source": source,
        "cadence": cadence,
        "reason": reason,
    }


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.split("T")[0])
        except ValueError:
            return None
    return None


def _cached_crowding() -> CrowdingSignal | None:
    cached = repository.get_latest_crowding()
    if not cached or cached.get("factor_crowding_corr") is None:
        return None
    as_of = _parse_date(cached.get("as_of"))
    if as_of is None:
        return None
    if date.today() - as_of > timedelta(days=CROWDING_CACHE_MAX_DAYS):
        return None
    return CrowdingSignal(
        value=float(cached["factor_crowding_corr"]),
        as_of=as_of,
        source="cached_weekly",
    )


def _collect_crowding(snapshot_date: date | None = None) -> CrowdingSignal | None:
    if snapshot_date is None:
        cached = _cached_crowding()
        if cached is not None:
            return cached

    crowding_obs = factor_crowding.compute_crowding()
    if crowding_obs is None:
        return None
    return CrowdingSignal(
        value=crowding_obs.momentum_value_corr,
        as_of=crowding_obs.as_of,
        source="computed",
    )


def collect_signals(snapshot_date: date | None = None) -> CollectedSignals:
    """Gather raw signal values for today (or a backtest date)."""
    fear_greed = (
        fear_greed_components.fetch_on(snapshot_date)
        if snapshot_date is not None
        else fear_greed_components.fetch_latest()
    )
    term_obs = term_structure.fetch_latest()  # FRED is point-in-time stable enough for live use
    breadth_obs = spx_breadth_200d.compute_breadth(as_of=snapshot_date)
    crowding = _collect_crowding(snapshot_date=snapshot_date)

    raw = RawSignals(
        vix_close=fear_greed.vix_close if fear_greed else None,
        term_spread_bps=term_obs.spread_bps if term_obs else None,
        breadth_pct=breadth_obs.pct_above_200dma if breadth_obs else None,
        hy_spread=fear_greed.hy_spread if fear_greed else None,
        put_call_ratio=fear_greed.put_call_ratio if fear_greed else None,
        factor_crowding_corr=crowding.value if crowding else None,
    )
    metadata = {
        "component_quality": {
            "vix": _quality(
                value=raw.vix_close,
                as_of=fear_greed.vix_as_of if fear_greed else None,
                source="fear_greed_inputs.vix_close",
                cadence="daily_after_close",
                stale=fear_greed.vix_stale if fear_greed else False,
                reason="Carried forward from the last trading day's close."
                if fear_greed and fear_greed.vix_stale
                else None,
            ),
            "term": _quality(
                value=raw.term_spread_bps,
                as_of=term_obs.as_of if term_obs else None,
                source="fred.10y_minus_2y",
                cadence="daily",
            ),
            "breadth": _quality(
                value=raw.breadth_pct,
                as_of=breadth_obs.as_of if breadth_obs else None,
                source="day_bars.spx_200dma_breadth",
                cadence="daily_after_close",
            ),
            "credit": _quality(
                value=raw.hy_spread,
                as_of=fear_greed.hy_spread_as_of if fear_greed else None,
                source="fear_greed_inputs.hy_spread",
                cadence="daily_after_close",
                stale=fear_greed.hy_spread_stale if fear_greed else False,
                reason="Carried forward from the last trading day's close."
                if fear_greed and fear_greed.hy_spread_stale
                else None,
            ),
            "putcall": _quality(
                value=raw.put_call_ratio,
                as_of=fear_greed.as_of if fear_greed else None,
                source="fear_greed_inputs.put_call_ratio",
                cadence="daily_after_close",
            ),
            "crowding": _quality(
                value=raw.factor_crowding_corr,
                as_of=crowding.as_of if crowding else None,
                source=f"factor_crowding.{crowding.source}" if crowding else "factor_crowding",
                cadence="weekly",
                reason=None if crowding else "No usable factor crowding observation available.",
            ),
        }
    }
    return CollectedSignals(raw=raw, metadata=metadata)


def collect_raw(snapshot_date: date | None = None) -> RawSignals:
    return collect_signals(snapshot_date=snapshot_date).raw


def run(snapshot_date: date | None = None, persist: bool = True) -> GateOutput | None:
    """Compute today's deployment zone and (optionally) persist the snapshot."""
    collected = collect_signals(snapshot_date=snapshot_date)
    raw = collected.raw
    if all(
        value is None
        for value in (
            raw.vix_close,
            raw.term_spread_bps,
            raw.breadth_pct,
            raw.hy_spread,
            raw.put_call_ratio,
            raw.factor_crowding_corr,
        )
    ):
        logger.warning("macro_gate_no_inputs")
        return None

    composite = build_composite(raw, metadata=collected.metadata)
    target_date = snapshot_date or _infer_snapshot_date(composite)

    if persist:
        repository.upsert_snapshot(target_date, composite)

    logger.info(
        "macro_gate_computed",
        snapshot_date=str(target_date),
        deployment_score=round(composite.deployment_score, 2),
        zone=composite.zone,
        coverage=round(composite.coverage, 2),
    )
    return GateOutput(
        snapshot_date=target_date,
        deployment_score=composite.deployment_score,
        zone=composite.zone,
        coverage=composite.coverage,
    )


def _infer_snapshot_date(_composite: CompositeResult) -> date:
    return date.today()
