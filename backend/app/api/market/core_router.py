"""Core market data endpoints (conditions, intelligence, trends, status, prices, movers)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, TypedDict, cast

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.market_data_sources import (
    fetch_sector_data_with_changes,
    get_actual_data_dates,
    get_market_data_timestamp,
    get_options_activity_metrics,
    get_put_call_ratio_data,
)
from app.api.market_responses import (
    MarketConditionsResponse,
    MarketMoverItem,
    MarketMoversResponse,
    MarketStatusResponse,
    PriceResponse,
    PricesResponse,
)
from app.api.market_transformers import (
    enrich_indicator_with_history,
    get_sector_symbols,
)
from app.logging_config import get_logger
from app.market import intelligence
from app.market.fear_greed_stub import get_fear_greed_score
from app.market.options_context import PutCallContext, calculate_putcall_context
from app.market.sentiment import calculate_market_health
from app.middleware.cache import cache_response
from app.models.market_intelligence import (
    FearGreedScore,
    MarketIntelligenceResponse,
    MarketTrendsResponse,
    OptionsActivityMetrics,
    SectorRotationSummary,
)
from app.models.market_intelligence import (
    MarketHealthScore as MarketHealthScoreResponse,
)
from app.portfolio.price_fetcher import PriceDataFetcher
from app.repositories.market_repository import MarketRepository
from app.storage import get_storage
from app.utils.market_hours import (
    NY_TZ,
    get_expected_data_date,
    get_last_trading_day,
    get_market_status,
    get_next_trading_day,
    is_early_close_day,
    is_market_holiday,
)

router = APIRouter()
logger = get_logger(__name__)

# Initialize services
storage = get_storage()
market_repo = MarketRepository(storage)
price_fetcher = PriceDataFetcher(storage)

# Cache TTL constants (in seconds)
CACHE_TTL_SHORT = 60  # 1 minute
CACHE_TTL_MEDIUM = 300  # 5 minutes
CACHE_TTL_LONG = 900  # 15 minutes

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
INDICATOR_ENRICH_FUNCS: dict[str, Any] = {
    "vix": intelligence.enrich_vix_indicator,
    "sp500": intelligence.enrich_sp500_indicator,
    "tnx": intelligence.enrich_tnx_indicator,
    "dxy": intelligence.enrich_dxy_indicator,
}

# Historical data limits
MAX_SYMBOLS_PER_REQUEST = 50  # Prevent DoS with large symbol lists


# Helper functions for price/timestamp extraction
def _extract_price(data: Any | None) -> float | None:
    """Extract price from PriceData object, returning None if data is None."""
    return data.price if data else None


def _extract_price_timestamp(data: Any | None) -> str | None:
    """Extract timestamp from PriceData object, returning None if data is None."""
    return data.cached_at.isoformat() if data else None


@dataclass
class CoreMarketData:
    """Core market indicators fetched from price service."""

    sp500_data: Any | None
    vix_data: Any | None
    tnx_data: Any | None
    dxy_data: Any | None
    sector_data: dict[str, tuple[float | None, float | None, str | None]]
    current_timestamp: str


def _fetch_core_market_data() -> CoreMarketData:
    """Fetch core market indicators used by multiple endpoints.

    Returns:
        CoreMarketData with sp500, vix, tnx, dxy, sector data, and timestamp
    """
    # Fetch market indicators
    price_data = price_fetcher.fetch_price_data(CORE_MARKET_SYMBOLS)

    sp500_data = price_data.get("^GSPC")
    vix_data = price_data.get("^VIX")
    tnx_data = price_data.get("^TNX")
    dxy_data = price_data.get("DX-Y.NYB")

    # Get actual timestamp from fetched data (respects 15-min cache)
    current_timestamp = (
        sp500_data.cached_at.isoformat() if sp500_data else datetime.now(UTC).isoformat()
    )

    # Fetch sector ETF data
    sector_symbols = get_sector_symbols()
    sector_price_data = price_fetcher.fetch_price_data(sector_symbols)

    # Get sector data with changes using batch query (avoiding N+1 query problem)
    sector_data = fetch_sector_data_with_changes(storage, sector_symbols, sector_price_data)

    return CoreMarketData(
        sp500_data=sp500_data,
        vix_data=vix_data,
        tnx_data=tnx_data,
        dxy_data=dxy_data,
        sector_data=sector_data,
        current_timestamp=current_timestamp,
    )


def _build_market_health_response(health_score_data: Any) -> MarketHealthScoreResponse:
    """Build MarketHealthScoreResponse from health score data.

    Args:
        health_score_data: Market health score with components

    Returns:
        MarketHealthScoreResponse for API response
    """
    return MarketHealthScoreResponse(
        overall_score=health_score_data.overall_score,
        overall_label=health_score_data.overall_label,
        last_updated=health_score_data.last_updated,
        trend=None,
        trend_change=None,
    )


def _build_fear_greed_response(fg_reading: Any) -> FearGreedScore:
    """Build FearGreedScore response from fear/greed reading.

    Args:
        fg_reading: Fear/greed reading from get_fear_greed_score()

    Returns:
        FearGreedScore for API response
    """
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


def _build_sector_rotation_response(
    leading_sectors: list[Any],
    neutral_sectors: list[Any],
    lagging_sectors: list[Any],
) -> SectorRotationSummary:
    """Build SectorRotationSummary from grouped sectors.

    Args:
        leading_sectors: List of leading sector data
        neutral_sectors: List of neutral sector data
        lagging_sectors: List of lagging sector data

    Returns:
        SectorRotationSummary for API response
    """
    return SectorRotationSummary(
        leading=leading_sectors,
        neutral=neutral_sectors,
        lagging=lagging_sectors,
        leading_count=len(leading_sectors),
        neutral_count=len(neutral_sectors),
        lagging_count=len(lagging_sectors),
    )


def _build_enriched_indicators(
    indicator_data: dict[str, Any],
    health_score_data: Any,
    actual_data_dates: dict[str, Any],
    putcall_data: tuple[float, str] | None,
) -> dict[str, Any]:
    """Build enriched indicators dict with plain-language labels.

    Args:
        indicator_data: Dict with vix, sp500, tnx, dxy price data objects
        health_score_data: Market health score with components
        actual_data_dates: Mapping of symbols to actual data timestamps
        putcall_data: Optional tuple of (put_call_ratio, timestamp)

    Returns:
        Dict of enriched indicators keyed by indicator name
    """
    enriched_indicators: dict[str, Any] = {}

    # Enrich core indicators (VIX, S&P 500, TNX, DXY)
    for key, symbol in INDICATOR_SYMBOLS.items():
        data = indicator_data.get(key)
        if data:
            enriched_indicators[key] = enrich_indicator_with_history(
                data,
                symbol,
                INDICATOR_ENRICH_FUNCS[key],
                storage,
                health_score_data,
                actual_data_dates,
            )

    # Add Put/Call Ratio if available
    if putcall_data:
        put_call_ratio, putcall_timestamp = putcall_data
        putcall_date = date.fromisoformat(putcall_timestamp[:10])

        putcall_context: PutCallContext = calculate_putcall_context(
            put_call_ratio, putcall_date, storage
        )

        enriched_indicators["putcall"] = intelligence.enrich_putcall_indicator(
            put_call_ratio,
            putcall_timestamp,
            context=cast(dict[str, Any], putcall_context),
        )

    return enriched_indicators


def _validate_and_build_options_activity(options_data_raw: Any) -> OptionsActivityMetrics | None:
    """Validate raw options data and build OptionsActivityMetrics.

    Args:
        options_data_raw: Raw options data from get_options_activity_metrics

    Returns:
        OptionsActivityMetrics if data is valid, None otherwise
    """

    class OptionsActivityData(TypedDict):
        """Return type for get_options_activity_metrics."""

        near_term_pct: float
        concentration_pct: float
        near_term_signal: str
        concentration_signal: str
        top_sectors: list[dict[str, Any]]
        last_updated: str

    if not options_data_raw:
        return None

    # Cast to our TypedDict for proper type checking
    options_data: OptionsActivityData = cast(OptionsActivityData, options_data_raw)

    # Type narrowing with validation (get_options_activity_metrics already validates types)
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


# API endpoints
@router.get("/conditions", response_model=MarketConditionsResponse)
@cache_response(ttl=CACHE_TTL_MEDIUM)
async def get_market_conditions(request: Request) -> MarketConditionsResponse:
    """Get current market conditions with health scoring.

    Returns:
        Market indicators with overall health score and component breakdown
    """
    # Use shared helper to fetch core market data
    market_data = _fetch_core_market_data()

    # Calculate market health score with sector data
    health_score = calculate_market_health(
        vix_price=_extract_price(market_data.vix_data),
        sp500_price=_extract_price(market_data.sp500_data),
        tnx_yield=_extract_price(market_data.tnx_data),
        dxy_price=_extract_price(market_data.dxy_data),
        sector_data=market_data.sector_data,
        current_timestamp=market_data.current_timestamp,
    )

    return MarketConditionsResponse(
        sp500={
            "price": _extract_price(market_data.sp500_data),
            "change_pct": None,  # Would need historical data
            "last_updated": _extract_price_timestamp(market_data.sp500_data),
        },
        vix={
            "price": _extract_price(market_data.vix_data),
            "level": None,
            "last_updated": _extract_price_timestamp(market_data.vix_data),
        },
        tnx={
            "yield": _extract_price(market_data.tnx_data),
            "last_updated": _extract_price_timestamp(market_data.tnx_data),
        },
        dxy={
            "price": _extract_price(market_data.dxy_data),
            "last_updated": _extract_price_timestamp(market_data.dxy_data),
        },
        health=health_score,
    )


@router.get("/prices", response_model=PricesResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_prices(
    request: Request,
    symbols: str = Query(..., description="Comma-separated symbols"),
) -> PricesResponse:
    """Get current prices for stock symbols."""

    # Parse symbols and filter empty strings
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    # Validate non-empty list
    if not symbol_list:
        raise HTTPException(status_code=400, detail="No valid symbols provided")

    # Validate symbol count to prevent DoS
    if len(symbol_list) > MAX_SYMBOLS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_SYMBOLS_PER_REQUEST} symbols allowed, got {len(symbol_list)}",
        )

    # Fetch price data
    price_data = price_fetcher.fetch_price_data(symbol_list)

    # Build response
    prices = {}
    for symbol, data in price_data.items():
        prices[symbol] = PriceResponse(
            symbol=data.symbol,
            price=data.price,
            beta=data.beta,
            volatility=data.volatility,
            sector=data.sector,
        )

    return PricesResponse(prices=prices, count=len(prices))


@router.get("/intelligence", response_model=MarketIntelligenceResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_market_intelligence(_request: Request) -> MarketIntelligenceResponse:
    """Get unified market intelligence with narrative, dual scoring, and sector rotation.

    This endpoint combines:
    - Market Health score (4 indicators: VIX, S&P 500, Treasury, Dollar)
    - Fear & Greed Index (5 signals: VIX, Momentum, RSI, Credit, Put/Call)
    - Plain-language narrative with actionable recommendations
    - Enriched indicators with educational tooltips
    - Sector rotation summary (Leading/Neutral/Lagging)

    Returns:
        MarketIntelligenceResponse with all market intelligence data
    """
    # Use shared helper to fetch core market data
    market_data = _fetch_core_market_data()

    # Get ACTUAL data dates from day_bars (not cache timestamps)
    # This shows when the market data was created, not when we fetched it
    actual_data_dates = get_actual_data_dates(storage, CORE_MARKET_SYMBOLS)

    # Get the actual market data date from Fear & Greed (most accurate source)
    # This represents when the underlying market data is from, not when we cached it
    current_timestamp = get_market_data_timestamp(storage)
    if not current_timestamp:
        # Fallback to cache timestamp from shared helper
        current_timestamp = market_data.current_timestamp

    # Convert sector data to list format for intelligence helper
    sector_symbols = get_sector_symbols()
    sector_data_list = [(symbol, *market_data.sector_data[symbol]) for symbol in sector_symbols]

    # Calculate market health score (existing logic)
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

    # Get Fear & Greed score (stub for now - local agent will implement)
    fg_reading = get_fear_greed_score()

    # Group sectors by performance using intelligence helper
    leading_sectors, neutral_sectors, lagging_sectors = intelligence.group_sectors_by_performance(
        sector_data_list
    )

    # Build enriched indicators using helper
    indicator_data = {
        "vix": market_data.vix_data,
        "sp500": market_data.sp500_data,
        "tnx": market_data.tnx_data,
        "dxy": market_data.dxy_data,
    }
    putcall_data = get_put_call_ratio_data(storage)
    enriched_indicators = _build_enriched_indicators(
        indicator_data, health_score_data, actual_data_dates, putcall_data
    )

    # Get Options Activity metrics from options_market_metrics table
    options_activity = _validate_and_build_options_activity(get_options_activity_metrics(storage))

    # Build response using helpers
    return MarketIntelligenceResponse(
        market_health=_build_market_health_response(health_score_data),
        fear_greed=_build_fear_greed_response(fg_reading),
        indicators=enriched_indicators,
        sector_rotation=_build_sector_rotation_response(
            leading_sectors, neutral_sectors, lagging_sectors
        ),
        options_activity=options_activity,
        last_updated=current_timestamp,
    )


@router.get("/trends", response_model=MarketTrendsResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_market_trends(
    request: Request,
    days: int = Query(30, ge=1, le=365, description="Number of days of historical data"),
) -> MarketTrendsResponse:
    """Get market trends for sparkline charts.

    Returns historical Fear & Greed scores and Market Health scores (if available).
    Market Health scores are not stored historically, so will be empty array.

    Args:
        days: Number of days of historical data (default: 30)

    Returns:
        MarketTrendsResponse with dates and scores
    """
    # Use repository for data access
    rows = market_repo.get_market_trends_data(days)

    # Build response
    dates: list[str] = []
    fear_greed_scores_list: list[float] = []
    for row in rows:
        date_val = row[0]
        score_val = row[1]
        # Type narrowing: ensure proper types
        if isinstance(date_val, (date, datetime)) and isinstance(score_val, (int, float)):
            dates.append(date_val.isoformat())
            fear_greed_scores_list.append(float(score_val))

    # Market Health scores not stored historically
    # Return empty array (frontend will handle gracefully)
    market_health_scores: list[float] = []

    return MarketTrendsResponse(
        dates=dates,
        fear_greed_scores=fear_greed_scores_list,
        market_health_scores=market_health_scores,
    )


@router.get("/status", response_model=MarketStatusResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_market_status_endpoint(request: Request) -> MarketStatusResponse:
    """Get current market status and trading day information.

    Returns:
        MarketStatusResponse with current status, open/closed state,
        last and next trading days, and holiday information.
    """
    now = datetime.now(NY_TZ)
    today = now.date()

    # Get market status
    status = get_market_status(now)

    # Get trading days
    last_trading = get_last_trading_day(today)
    next_trading = get_next_trading_day(today)

    # Check holiday status
    is_holiday, holiday_name = is_market_holiday(today)
    is_early, early_name = is_early_close_day(today)

    # Get expected data date (for staleness detection)
    expected_data = get_expected_data_date(now)

    return MarketStatusResponse(
        status=status,
        is_open=status == "open",
        last_trading_day=last_trading.isoformat(),
        next_trading_day=next_trading.isoformat(),
        current_time_et=now.strftime("%Y-%m-%d %H:%M:%S ET"),
        expected_data_date=expected_data.isoformat(),
        is_holiday=is_holiday,
        holiday_name=holiday_name,
        is_early_close=is_early,
        early_close_name=early_name,
    )


@router.get("/movers", response_model=MarketMoversResponse)
@cache_response(ttl=CACHE_TTL_LONG)
async def get_market_movers(
    request: Request,
    count: int = Query(10, ge=1, le=25, description="Number of gainers/losers to return"),
) -> MarketMoversResponse:
    """Get top market movers (gainers and losers).

    Uses yahooquery (Yahoo Finance) as primary source with Alpaca as fallback.
    Data is cached for 15 minutes.

    Args:
        count: Number of gainers and losers to return (1-25)

    Returns:
        MarketMoversResponse with top gainers and losers
    """
    from app.sources.market_movers_source import MarketMover, fetch_market_movers  # noqa: PLC0415

    result = fetch_market_movers(storage, count=count)

    def to_item(m: MarketMover) -> MarketMoverItem:
        return MarketMoverItem(
            symbol=m.symbol,
            name=m.name,
            price=m.price,
            change_pct=m.change_pct,
            volume=m.volume,
            market_cap=m.market_cap,
            avg_volume=m.avg_volume,
            rvol=m.rvol,
            sector=m.sector,
        )

    return MarketMoversResponse(
        gainers=[to_item(m) for m in result.gainers],
        losers=[to_item(m) for m in result.losers],
        most_active=[to_item(m) for m in result.most_active],
        top_rvol=[to_item(m) for m in result.top_rvol],
        source=result.source,
        last_updated=result.last_updated,
    )
