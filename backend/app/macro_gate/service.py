"""Macro deployment gate service.

Pulls today's raw signal values from existing sources, builds the
composite, persists the snapshot, and returns the result for callers that
need it directly (the workflow + the read API).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Any

from ..logging_config import get_logger
from ..portfolio.models import PriceData
from ..portfolio.price_fetcher import PriceDataFetcher
from ..storage.facade import get_storage
from ..utils.market_hours import NY_TZ
from . import repository
from .scoring import CompositeResult, RawSignals, build_composite, classify_zone
from .signals import factor_crowding, fear_greed_components, spx_breadth_200d, term_structure

logger = get_logger(__name__)
CROWDING_CACHE_MAX_DAYS = 10
CURRENT_QUOTE_MAX_AGE_MINUTES = 5
VIX_SYMBOL = "^VIX"


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


def _current_market_date() -> date:
    return datetime.now(NY_TZ).date()


def _quality(
    *,
    value: float | None,
    as_of: date | datetime | None,
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
    if _current_market_date() - as_of > timedelta(days=CROWDING_CACHE_MAX_DAYS):
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


def _current_quote(
    symbol: str,
    *,
    force_refresh: bool = False,
    max_age_minutes: int | None = CURRENT_QUOTE_MAX_AGE_MINUTES,
) -> PriceData | None:
    try:
        quote = PriceDataFetcher(get_storage()).fetch_price_data(
            [symbol],
            force_refresh=force_refresh,
            max_age_minutes=max_age_minutes,
        ).get(symbol)
    except Exception as exc:
        logger.warning("macro_gate_current_quote_unavailable", symbol=symbol, error=str(exc))
        return None

    if quote is None or quote.error or quote.price <= 0:
        logger.warning(
            "macro_gate_current_quote_invalid",
            symbol=symbol,
            error=getattr(quote, "error", None),
        )
        return None
    # A carried-forward prior-day close must never be treated as a live quote.
    # Reject it so collect_signals falls back to the honest "stale / carried
    # forward" path instead of stamping yesterday's close as a fresh value.
    if quote.price_session == "previous_close":
        logger.warning(
            "macro_gate_current_quote_not_live",
            symbol=symbol,
            price_session=quote.price_session,
        )
        return None
    return quote


def _vix_value(
    *,
    snapshot_date: date | None,
    force_quote_refresh: bool,
    max_age_minutes: int | None,
) -> PriceData | None:
    if snapshot_date is not None:
        return None
    return _current_quote(
        VIX_SYMBOL,
        force_refresh=force_quote_refresh,
        max_age_minutes=max_age_minutes,
    )


def collect_signals(
    snapshot_date: date | None = None,
    *,
    force_quote_refresh: bool = False,
    current_quote_max_age_minutes: int | None = CURRENT_QUOTE_MAX_AGE_MINUTES,
) -> CollectedSignals:
    """Gather raw signal values for today (or a backtest date)."""
    fear_greed = (
        fear_greed_components.fetch_on(snapshot_date)
        if snapshot_date is not None
        else fear_greed_components.fetch_latest()
    )
    current_vix = _vix_value(
        snapshot_date=snapshot_date,
        force_quote_refresh=force_quote_refresh,
        max_age_minutes=current_quote_max_age_minutes,
    )
    term_obs = term_structure.fetch_latest()  # FRED is point-in-time stable enough for live use
    breadth_obs = spx_breadth_200d.compute_breadth(as_of=snapshot_date)
    crowding = _collect_crowding(snapshot_date=snapshot_date)

    raw = RawSignals(
        vix_close=current_vix.price if current_vix else fear_greed.vix_close if fear_greed else None,
        term_spread_bps=term_obs.spread_bps if term_obs else None,
        breadth_pct=breadth_obs.pct_above_200dma if breadth_obs else None,
        hy_spread=fear_greed.hy_spread if fear_greed else None,
        put_call_ratio=fear_greed.put_call_ratio if fear_greed else None,
        factor_crowding_corr=crowding.value if crowding else None,
    )
    vix_source = (
        f"price_cache.{VIX_SYMBOL} via {current_vix.source}"
        if current_vix
        else "fear_greed_inputs.vix_close"
    )
    vix_cadence = "intraday_current" if current_vix else "daily_after_close"
    vix_reason = (
        "Canonical current quote; historical daily close remains in fear_greed_inputs."
        if current_vix
        else "Carried forward from the last trading day's close."
        if fear_greed and fear_greed.vix_stale
        else None
    )
    metadata = {
        "component_quality": {
            "vix": _quality(
                value=raw.vix_close,
                as_of=(current_vix.quote_time or current_vix.cached_at)
                if current_vix
                else fear_greed.vix_as_of
                if fear_greed
                else None,
                source=vix_source,
                cadence=vix_cadence,
                stale=False if current_vix else fear_greed.vix_stale if fear_greed else False,
                reason=vix_reason,
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
        },
        "current_quote_overlays": {
            "vix": {
                "symbol": VIX_SYMBOL,
                "price": current_vix.price,
                "cached_at": current_vix.cached_at.isoformat(),
                "source": current_vix.source,
            }
            if current_vix
            else None,
        },
    }
    return CollectedSignals(raw=raw, metadata=metadata)


def collect_raw(snapshot_date: date | None = None) -> RawSignals:
    return collect_signals(snapshot_date=snapshot_date).raw


def run(
    snapshot_date: date | None = None,
    persist: bool = True,
    *,
    force_quote_refresh: bool = False,
    current_quote_max_age_minutes: int | None = CURRENT_QUOTE_MAX_AGE_MINUTES,
) -> GateOutput | None:
    """Compute today's deployment zone and (optionally) persist the snapshot."""
    collected = collect_signals(
        snapshot_date=snapshot_date,
        force_quote_refresh=force_quote_refresh,
        current_quote_max_age_minutes=current_quote_max_age_minutes,
    )
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

    # Stale carried-forward inputs are excluded from the trusted score (drops
    # coverage) and clamped below so a degraded reading can never look calmer
    # than the last fully-trusted gate. Backtests pass snapshot_date and never
    # mark staleness, so historical replay is unaffected.
    stale_keys = _stale_component_keys(collected.metadata) if snapshot_date is None else frozenset()
    composite = build_composite(raw, metadata=collected.metadata, stale_keys=stale_keys)
    target_date = snapshot_date or _infer_snapshot_date(composite)
    if stale_keys:
        composite = _clamp_degraded_to_known_good(composite, target_date)

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


# Only components for which we expect an intraday-current value can "degrade"
# the gate when carried forward. The daily/weekly inputs (term, breadth, credit,
# put/call, crowding) legitimately lag by a session — that is their cadence, not
# staleness — so a one-day-old HY spread must not drop coverage or flag degraded.
# A genuinely stuck daily feed is caught separately by the fear_greed_inputs
# freshness monitor, not here.
_INTRADAY_COMPONENTS = frozenset({"vix"})


def _stale_component_keys(metadata: dict[str, Any]) -> frozenset[str]:
    quality = metadata.get("component_quality", {})
    if not isinstance(quality, dict):
        return frozenset()
    return frozenset(
        key
        for key, q in quality.items()
        if key in _INTRADAY_COMPONENTS and isinstance(q, dict) and q.get("status") == "stale"
    )


def _clamp_degraded_to_known_good(composite: CompositeResult, target_date: date) -> CompositeResult:
    """Hold a degraded reading to the last fully-trusted score if it reads greener.

    Higher deployment score == more risk-on. A snapshot computed off stale
    inputs must never report a calmer/greener regime than the last known-good
    gate, so we clamp it down (and re-classify the zone) when it would.
    """
    known_good = repository.get_last_known_good_score(target_date)
    metadata = {**composite.metadata, "known_good_score": known_good}
    if known_good is None or composite.deployment_score <= known_good:
        return replace(composite, metadata=metadata)
    metadata["clamped_to_known_good"] = True
    metadata["raw_deployment_score"] = composite.deployment_score
    logger.info(
        "macro_gate_degraded_clamped",
        raw_deployment_score=round(composite.deployment_score, 2),
        known_good_score=round(known_good, 2),
        stale_components=composite.metadata.get("stale_components"),
    )
    return replace(
        composite,
        deployment_score=known_good,
        zone=classify_zone(known_good),
        metadata=metadata,
    )


def _infer_snapshot_date(_composite: CompositeResult) -> date:
    return _current_market_date()
