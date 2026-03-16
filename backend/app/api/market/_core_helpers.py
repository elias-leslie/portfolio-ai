"""Helper functions and data structures for core market endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TypedDict, cast

from app.api.market_data_sources import (
    fetch_sector_data_with_changes,
    get_actual_data_dates,
    get_options_activity_metrics,
    get_put_call_ratio_data,
)
from app.api.market_transformers import (
    enrich_indicator_with_history,
    get_sector_symbols,
)
from app.market import intelligence
from app.market.fear_greed_stub import get_fear_greed_score
from app.market.options_context import PutCallContext, calculate_putcall_context
from app.market.sentiment import calculate_market_health
from app.models.market_intelligence import (
    FearGreedScore,
    OptionsActivityMetrics,
    SectorRotationSummary,
)
from app.models.market_intelligence import (
    MarketHealthScore as MarketHealthScoreResponse,
)
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

_state: dict[str, PriceDataFetcher] = {}


def _get_price_fetcher() -> PriceDataFetcher:
    """Lazy singleton to avoid DB connection at import time."""
    if "svc" not in _state:
        _state["svc"] = PriceDataFetcher(get_storage())
    return _state["svc"]

# Market indicator symbols
CORE_MARKET_SYMBOLS = ["^GSPC", "^VIX", "^TNX", "DX-Y.NYB"]

# Indicator symbol to key mapping
INDICATOR_SYMBOLS: dict[str, str] = {
    "vix": "^VIX",
    "sp500": "^GSPC",
    "tnx": "^TNX",
    "dxy": "DX-Y.NYB",
}

# Enrichment functions by indicator key
INDICATOR_ENRICH_FUNCS: dict[str, object] = {
    "vix": intelligence.enrich_vix_indicator,
    "sp500": intelligence.enrich_sp500_indicator,
    "tnx": intelligence.enrich_tnx_indicator,
    "dxy": intelligence.enrich_dxy_indicator,
}


class OptionsActivityData(TypedDict):
    """Return type for get_options_activity_metrics."""

    near_term_pct: float
    concentration_pct: float
    near_term_signal: str
    concentration_signal: str
    top_sectors: list[dict[str, object]]
    last_updated: str


@dataclass
class CoreMarketData:
    """Core market indicators fetched from price service."""

    sp500_data: object | None
    vix_data: object | None
    tnx_data: object | None
    dxy_data: object | None
    sector_data: dict[str, tuple[float | None, float | None, str | None]]
    current_timestamp: str


def _extract_price(data: object | None) -> float | None:
    """Extract price from PriceData object, returning None if data is None."""
    return data.price if data else None


def _extract_price_timestamp(data: object | None) -> str | None:
    """Extract timestamp from PriceData object, returning None if data is None."""
    return data.cached_at.isoformat() if data else None


def fetch_core_market_data() -> CoreMarketData:
    """Fetch core market indicators used by multiple endpoints.

    Returns:
        CoreMarketData with sp500, vix, tnx, dxy, sector data, and timestamp
    """
    price_data = _get_price_fetcher().fetch_price_data(CORE_MARKET_SYMBOLS)

    sp500_data = price_data.get("^GSPC")
    vix_data = price_data.get("^VIX")
    tnx_data = price_data.get("^TNX")
    dxy_data = price_data.get("DX-Y.NYB")

    current_timestamp = (
        sp500_data.cached_at.isoformat() if sp500_data else datetime.now(UTC).isoformat()
    )

    sector_symbols = get_sector_symbols()
    sector_price_data = _get_price_fetcher().fetch_price_data(sector_symbols)
    sector_data = fetch_sector_data_with_changes(get_storage(), sector_symbols, sector_price_data)

    return CoreMarketData(
        sp500_data=sp500_data,
        vix_data=vix_data,
        tnx_data=tnx_data,
        dxy_data=dxy_data,
        sector_data=sector_data,
        current_timestamp=current_timestamp,
    )


def build_market_health_response(health_score_data: object) -> MarketHealthScoreResponse:
    """Build MarketHealthScoreResponse from health score data."""
    return MarketHealthScoreResponse(
        overall_score=health_score_data.overall_score,
        overall_label=health_score_data.overall_label,
        last_updated=health_score_data.last_updated,
        trend=None,
        trend_change=None,
    )


def build_fear_greed_response(fg_reading: object) -> FearGreedScore:
    """Build FearGreedScore response from fear/greed reading."""
    return FearGreedScore(
        score=int(fg_reading.score),
        label=fg_reading.label,
        score_change=fg_reading.score_change,
        signal_count=fg_reading.signal_count,
        last_updated=fg_reading.date,
        is_stale=fg_reading.is_stale,
        age_days=fg_reading.age_days,
        trend=fg_reading.trend,
        trend_change=fg_reading.trend_change,
    )


def build_sector_rotation_response(
    leading_sectors: list[object],
    neutral_sectors: list[object],
    lagging_sectors: list[object],
) -> SectorRotationSummary:
    """Build SectorRotationSummary from grouped sectors."""
    return SectorRotationSummary(
        leading=leading_sectors,
        neutral=neutral_sectors,
        lagging=lagging_sectors,
        leading_count=len(leading_sectors),
        neutral_count=len(neutral_sectors),
        lagging_count=len(lagging_sectors),
    )


def build_enriched_indicators(
    indicator_data: dict[str, object | None],
    health_score_data: object,
    actual_data_dates: dict[str, object],
    putcall_data: tuple[float, str] | None,
) -> dict[str, object]:
    """Build enriched indicators dict with plain-language labels.

    Args:
        indicator_data: Dict with vix, sp500, tnx, dxy price data objects
        health_score_data: Market health score with components
        actual_data_dates: Mapping of symbols to actual data timestamps
        putcall_data: Optional tuple of (put_call_ratio, timestamp)

    Returns:
        Dict of enriched indicators keyed by indicator name
    """
    enriched_indicators: dict[str, object] = {}

    for key, symbol in INDICATOR_SYMBOLS.items():
        data = indicator_data.get(key)
        if data:
            enriched_indicators[key] = enrich_indicator_with_history(
                data,
                symbol,
                INDICATOR_ENRICH_FUNCS[key],
                get_storage(),
                health_score_data,
                actual_data_dates,
            )

    if not putcall_data:
        return enriched_indicators

    put_call_ratio, putcall_timestamp = putcall_data
    putcall_date = date.fromisoformat(putcall_timestamp[:10])
    putcall_context: PutCallContext = calculate_putcall_context(put_call_ratio, putcall_date, get_storage())

    enriched_indicators["putcall"] = intelligence.enrich_putcall_indicator(
        put_call_ratio,
        putcall_timestamp,
        context=cast(dict[str, object], putcall_context),
    )

    return enriched_indicators


def validate_and_build_options_activity(options_data_raw: object | None) -> OptionsActivityMetrics | None:
    """Validate raw options data and build OptionsActivityMetrics.

    Args:
        options_data_raw: Raw options data from get_options_activity_metrics

    Returns:
        OptionsActivityMetrics if data is valid, None otherwise
    """
    if not options_data_raw:
        return None

    options_data: OptionsActivityData = cast(OptionsActivityData, options_data_raw)

    near_term = options_data["near_term_pct"]
    concentration = options_data["concentration_pct"]

    if not isinstance(near_term, (int, float)) or not isinstance(concentration, (int, float)):
        return None

    return OptionsActivityMetrics(
        near_term_pct=float(near_term),
        near_term_signal=str(options_data["near_term_signal"]),
        concentration_pct=float(concentration),
        concentration_signal=str(options_data["concentration_signal"]),
        top_sectors=options_data["top_sectors"],
        last_updated=str(options_data["last_updated"]),
    )


def build_intelligence_response_data(
    market_data: CoreMarketData,
    current_timestamp: str,
) -> dict[str, object]:
    """Assemble all data needed for the market intelligence response.

    Args:
        market_data: Core market indicators
        current_timestamp: Authoritative data timestamp

    Returns:
        Dict with health_score_data, fg_reading, sector groups, enriched indicators, options_activity
    """
    sector_symbols = get_sector_symbols()
    sector_data_list = [(symbol, *market_data.sector_data[symbol]) for symbol in sector_symbols]

    health_score_data = calculate_market_health(
        vix_price=_extract_price(market_data.vix_data),
        sp500_price=_extract_price(market_data.sp500_data),
        tnx_yield=_extract_price(market_data.tnx_data),
        dxy_price=_extract_price(market_data.dxy_data),
        sector_data={
            symbol: (price, change_pct, timestamp)
            for symbol, price, change_pct, timestamp in sector_data_list
        },
        current_timestamp=current_timestamp,
    )

    fg_reading = get_fear_greed_score()
    leading_sectors, neutral_sectors, lagging_sectors = intelligence.group_sectors_by_performance(
        sector_data_list
    )

    actual_data_dates = get_actual_data_dates(get_storage(), CORE_MARKET_SYMBOLS)
    indicator_data: dict[str, object | None] = {
        "vix": market_data.vix_data,
        "sp500": market_data.sp500_data,
        "tnx": market_data.tnx_data,
        "dxy": market_data.dxy_data,
    }
    putcall_data = get_put_call_ratio_data(get_storage())
    enriched_indicators = build_enriched_indicators(
        indicator_data, health_score_data, actual_data_dates, putcall_data
    )

    options_activity = validate_and_build_options_activity(get_options_activity_metrics(get_storage()))

    return {
        "health_score_data": health_score_data,
        "fg_reading": fg_reading,
        "leading_sectors": leading_sectors,
        "neutral_sectors": neutral_sectors,
        "lagging_sectors": lagging_sectors,
        "enriched_indicators": enriched_indicators,
        "options_activity": options_activity,
    }
