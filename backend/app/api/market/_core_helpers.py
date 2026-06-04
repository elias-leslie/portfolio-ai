"""Helper functions and data structures for core market endpoints."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import cast

from app.api.market._types import (
    CORE_MARKET_SYMBOLS,
    INDICATOR_ENRICH_FUNCS,
    INDICATOR_SYMBOLS,
    CoreMarketData,
    OptionsActivityData,
)
from app.api.market_data_sources import (
    fetch_sector_data_with_changes,
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
from app.models.market_intelligence import OptionsActivityMetrics
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

_state: dict[str, PriceDataFetcher] = {}


def _get_price_fetcher() -> PriceDataFetcher:
    """Lazy singleton to avoid DB connection at import time."""
    if "svc" not in _state:
        _state["svc"] = PriceDataFetcher(get_storage())
    return _state["svc"]


def _extract_price(data: object | None) -> float | None:
    """Extract price from PriceData object, returning None if data is None."""
    return data.price if data else None


def _extract_price_timestamp(data: object | None) -> str | None:
    """Extract the most honest quote timestamp from a PriceData object.

    Prefers the vendor's quote time (`quote_time`, e.g. CBOE last_trade_time /
    Yahoo regularMarketTime) so freshness reflects when the quote was actually
    produced, falling back to `cached_at` (cache-write time) only when the source
    did not supply a vendor timestamp.
    """
    if not data:
        return None
    quote_time = getattr(data, "quote_time", None)
    if quote_time is not None:
        return quote_time.isoformat()
    return data.cached_at.isoformat() if data.cached_at else None


def _latest_price_timestamp(*items: object | None) -> str | None:
    timestamps: list[datetime] = []
    for item in items:
        if not item:
            continue
        value = getattr(item, "quote_time", None) or getattr(item, "cached_at", None)
        if isinstance(value, datetime):
            timestamps.append(value if value.tzinfo else value.replace(tzinfo=UTC))
    if not timestamps:
        # Returning now() would let the page-level "last updated" label confidently
        # render "just now" while every indicator shows Unavailable. Surface None and
        # let the UI render an honest "Update time unavailable".
        return None
    return max(timestamps).isoformat()


def fetch_core_market_data() -> CoreMarketData:
    """Fetch core market indicators used by multiple endpoints.

    Uses fetch_price_data (cache + on-miss vendor fetch) for the small
    indicator + sector ETF universe. No background job warms these
    symbols, so a pure cache read silently goes stale.
    """
    fetcher = _get_price_fetcher()
    price_data = fetcher.fetch_price_data(CORE_MARKET_SYMBOLS)

    sp500_data = price_data.get("^GSPC")
    vix_data = price_data.get("^VIX")
    tnx_data = price_data.get("^TNX")
    dxy_data = price_data.get("DX-Y.NYB")

    current_timestamp = _latest_price_timestamp(sp500_data, vix_data, tnx_data, dxy_data)

    sector_symbols = get_sector_symbols()
    sector_price_data = fetcher.fetch_price_data(sector_symbols)
    sector_data = fetch_sector_data_with_changes(get_storage(), sector_symbols, sector_price_data)

    return CoreMarketData(
        sp500_data=sp500_data,
        vix_data=vix_data,
        tnx_data=tnx_data,
        dxy_data=dxy_data,
        sector_data=sector_data,
        current_timestamp=current_timestamp,
    )


def validate_and_build_options_activity(options_data_raw: object | None) -> OptionsActivityMetrics | None:
    """Validate raw options data and build OptionsActivityMetrics."""
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


def _enrich_putcall(
    put_call_ratio: float,
    putcall_timestamp: str,
) -> object:
    """Build enriched put/call indicator from ratio and timestamp."""
    putcall_date = date.fromisoformat(putcall_timestamp[:10])
    putcall_context: PutCallContext = calculate_putcall_context(put_call_ratio, putcall_date, get_storage())
    return intelligence.enrich_putcall_indicator(
        put_call_ratio,
        putcall_timestamp,
        context=cast(dict[str, object], putcall_context),
    )


def build_enriched_indicators(
    indicator_data: dict[str, object | None],
    health_score_data: object,
    putcall_data: tuple[float, str] | None,
) -> dict[str, object]:
    """Build enriched indicators dict with plain-language labels."""
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
            )

    if putcall_data:
        put_call_ratio, putcall_timestamp = putcall_data
        enriched_indicators["putcall"] = _enrich_putcall(put_call_ratio, putcall_timestamp)

    return enriched_indicators


def _build_health_score(
    market_data: CoreMarketData,
    sector_data_list: list[tuple[str, float | None, float | None, str | None]],
    current_timestamp: str | None,
) -> object:
    """Calculate market health score from core data."""
    return calculate_market_health(
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


def build_intelligence_response_data(
    market_data: CoreMarketData,
    current_timestamp: str | None,
) -> dict[str, object]:
    """Assemble all data needed for the market intelligence response."""
    sector_symbols = get_sector_symbols()
    sector_data_list = [(symbol, *market_data.sector_data[symbol]) for symbol in sector_symbols]

    health_score_data = _build_health_score(market_data, sector_data_list, current_timestamp)
    fg_reading = get_fear_greed_score()
    leading_sectors, neutral_sectors, lagging_sectors = intelligence.group_sectors_by_performance(
        sector_data_list
    )

    indicator_data: dict[str, object | None] = {
        "vix": market_data.vix_data,
        "sp500": market_data.sp500_data,
        "tnx": market_data.tnx_data,
        "dxy": market_data.dxy_data,
    }
    enriched_indicators = build_enriched_indicators(
        indicator_data, health_score_data, get_put_call_ratio_data(get_storage())
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
