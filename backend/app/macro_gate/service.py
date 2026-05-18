"""Macro deployment gate service.

Pulls today's raw signal values from existing sources, builds the
composite, persists the snapshot, and returns the result for callers that
need it directly (the workflow + the read API).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..logging_config import get_logger
from . import repository
from .scoring import CompositeResult, RawSignals, build_composite
from .signals import factor_crowding, fear_greed_components, spx_breadth_200d, term_structure

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class GateOutput:
    snapshot_date: date
    deployment_score: float
    zone: str
    coverage: float


def collect_raw(snapshot_date: date | None = None) -> RawSignals:
    """Gather raw signal values for today (or a backtest date)."""
    fear_greed = (
        fear_greed_components.fetch_on(snapshot_date)
        if snapshot_date is not None
        else fear_greed_components.fetch_latest()
    )
    term_obs = term_structure.fetch_latest()  # FRED is point-in-time stable enough for live use
    breadth_obs = spx_breadth_200d.compute_breadth(as_of=snapshot_date)
    crowding_obs = factor_crowding.compute_crowding()

    return RawSignals(
        vix_close=fear_greed.vix_close if fear_greed else None,
        term_spread_bps=term_obs.spread_bps if term_obs else None,
        breadth_pct=breadth_obs.pct_above_200dma if breadth_obs else None,
        hy_spread=fear_greed.hy_spread if fear_greed else None,
        put_call_ratio=fear_greed.put_call_ratio if fear_greed else None,
        factor_crowding_corr=crowding_obs.momentum_value_corr if crowding_obs else None,
    )


def run(snapshot_date: date | None = None, persist: bool = True) -> GateOutput | None:
    """Compute today's deployment zone and (optionally) persist the snapshot."""
    raw = collect_raw(snapshot_date=snapshot_date)
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

    composite = build_composite(raw)
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
