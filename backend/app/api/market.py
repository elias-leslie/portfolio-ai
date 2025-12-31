"""Market data API router."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, cast

import yfinance as yf
from fastapi import APIRouter, HTTPException, Query, Request

from app.api.market_data_sources import (
    calculate_daily_change_pct,
    fetch_sector_data_with_changes,
    get_actual_data_dates,
    get_market_data_timestamp,
    get_options_activity_metrics,
    get_put_call_ratio_data,
)
from app.api.market_responses import (
    FearGreedHistoryResponse,
    IndicatorDataPoint,
    IndicatorHistoryResponse,
    MarketConditionsResponse,
    MarketMoverItem,
    MarketMoversResponse,
    MarketStatusResponse,
    NewsSentimentHistoryResponse,
    PriceResponse,
    PricesResponse,
    SectorHistory,
    SectorHistoryResponse,
)
from app.api.market_transformers import (
    build_indicator_data_points,
    build_sector_history,
    get_sector_symbols,
    sort_sectors_by_performance,
)
from app.constants import SECTOR_ETFS
from app.logging_config import get_logger
from app.market import intelligence
from app.market.fear_greed_stub import get_fear_greed_score
from app.market.sentiment import calculate_market_health
from app.middleware.cache import cache_response
from app.models.market_events import MarketEventCreate, MarketEventType, MarketEventUpdate
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
from app.services.market_events_service import (
    create_market_event as svc_create_event,
)
from app.services.market_events_service import (
    get_event_type_info,
    get_events_for_chart,
    get_upcoming_events,
)
from app.services.market_events_service import (
    get_market_events as svc_get_events,
)
from app.services.market_events_service import (
    update_market_event as svc_update_event,
)
from app.storage import get_storage
from app.utils.formatters import format_db_date
from app.utils.market_hours import (
    NY_TZ,
    get_expected_data_date,
    get_last_trading_day,
    get_market_status,
    get_next_trading_day,
    is_early_close_day,
    is_market_holiday,
)

router = APIRouter(prefix="/api/market", tags=["market"])
logger = get_logger(__name__)

# Pseudo-symbol for market-wide events and readings (fear/greed history)
MARKET_SYMBOL = "__MARKET__"

# Initialize services
storage = get_storage()
market_repo = MarketRepository(storage)
price_fetcher = PriceDataFetcher(storage)

# Market indicator symbols
CORE_MARKET_SYMBOLS = ["^GSPC", "^VIX", "^TNX", "DX-Y.NYB"]

# Valid market event types (must match MarketEventType Literal)
VALID_EVENT_TYPES = {
    "fomc_decision", "cpi_release", "nfp_release", "fed_speech", "pce_release", "gdp_release"
}


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
        sp500_data.cached_at.isoformat() if sp500_data else datetime.utcnow().isoformat() + "Z"
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


# API endpoints
@router.get("/conditions", response_model=MarketConditionsResponse)
@cache_response(ttl=300)  # 5 minutes cache
async def get_market_conditions(request: Request) -> MarketConditionsResponse:
    """Get current market conditions with health scoring.

    Returns:
        Market indicators with overall health score and component breakdown
    """
    # Use shared helper to fetch core market data
    market_data = _fetch_core_market_data()

    # Calculate market health score with sector data
    health_score = calculate_market_health(
        vix_price=market_data.vix_data.price if market_data.vix_data else None,
        sp500_price=market_data.sp500_data.price if market_data.sp500_data else None,
        tnx_yield=market_data.tnx_data.price if market_data.tnx_data else None,
        dxy_price=market_data.dxy_data.price if market_data.dxy_data else None,
        sector_data=market_data.sector_data,
        current_timestamp=market_data.current_timestamp,
    )

    return MarketConditionsResponse(
        sp500={
            "price": market_data.sp500_data.price if market_data.sp500_data else None,
            "change_pct": None,  # Would need historical data
            "last_updated": market_data.sp500_data.cached_at.isoformat()
            if market_data.sp500_data
            else None,
        },
        vix={
            "price": market_data.vix_data.price if market_data.vix_data else None,
            "level": None,
            "last_updated": market_data.vix_data.cached_at.isoformat()
            if market_data.vix_data
            else None,
        },
        tnx={
            "yield": market_data.tnx_data.price if market_data.tnx_data else None,
            "last_updated": market_data.tnx_data.cached_at.isoformat()
            if market_data.tnx_data
            else None,
        },
        dxy={
            "price": market_data.dxy_data.price if market_data.dxy_data else None,
            "last_updated": market_data.dxy_data.cached_at.isoformat()
            if market_data.dxy_data
            else None,
        },
        health=health_score,
    )


@router.get("/prices", response_model=PricesResponse)
@cache_response(ttl=60)  # 1 minute cache
async def get_prices(
    request: Request,
    symbols: str = Query(..., description="Comma-separated symbols"),
) -> PricesResponse:
    """Get current prices for stock symbols."""
    # Parse symbols
    symbol_list = [s.strip().upper() for s in symbols.split(",")]

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
@cache_response(ttl=60)  # 1 minute cache for fresh data
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
        vix_price=market_data.vix_data.price if market_data.vix_data else None,
        sp500_price=market_data.sp500_data.price if market_data.sp500_data else None,
        tnx_yield=market_data.tnx_data.price if market_data.tnx_data else None,
        dxy_price=market_data.dxy_data.price if market_data.dxy_data else None,
        sector_data={
            symbol: (price, change_pct, timestamp)
            for symbol, price, change_pct, timestamp in sector_data_list
        },
        current_timestamp=current_timestamp,
    )

    # Extract data references for rest of function
    vix_data = market_data.vix_data
    sp500_data = market_data.sp500_data
    tnx_data = market_data.tnx_data
    dxy_data = market_data.dxy_data

    # Get Fear & Greed score (stub for now - local agent will implement)
    fg_reading = get_fear_greed_score()

    # Group sectors by performance using intelligence helper
    leading_sectors, neutral_sectors, lagging_sectors = intelligence.group_sectors_by_performance(
        sector_data_list
    )

    def _enrich_indicator_with_history(
        indicator_data: Any,
        symbol: str,
        enrich_func: Any,
    ) -> dict[str, Any]:
        """Enrich indicator data with historical change and actual timestamp.

        Args:
            indicator_data: Raw indicator data from price fetcher
            symbol: Market symbol (e.g., "^VIX", "^GSPC")
            enrich_func: Intelligence function to enrich the indicator

        Returns:
            Enriched indicator dict with history
        """
        # Calculate daily change percentage from day_bars historical data
        change_pct = calculate_daily_change_pct(storage, symbol, indicator_data.price)

        # Get actual data timestamp (from day_bars) instead of cache timestamp
        actual_timestamp = actual_data_dates.get(symbol)
        if actual_timestamp:
            # Temporarily override cached_at with actual data date
            indicator_data.cached_at = actual_timestamp

        # Call the appropriate enrich function
        return enrich_func(indicator_data, health_score_data, change_pct=change_pct)

    # Enrich indicators with plain-language labels using intelligence helpers
    # Calculate daily change percentages from day_bars historical data
    # Use actual data timestamps (from day_bars) instead of cache timestamps
    enriched_indicators = {}
    if vix_data:
        enriched_indicators["vix"] = _enrich_indicator_with_history(
            vix_data, "^VIX", intelligence.enrich_vix_indicator
        )
    if sp500_data:
        enriched_indicators["sp500"] = _enrich_indicator_with_history(
            sp500_data, "^GSPC", intelligence.enrich_sp500_indicator
        )
    if tnx_data:
        enriched_indicators["tnx"] = _enrich_indicator_with_history(
            tnx_data, "^TNX", intelligence.enrich_tnx_indicator
        )
    if dxy_data:
        enriched_indicators["dxy"] = _enrich_indicator_with_history(
            dxy_data, "DX-Y.NYB", intelligence.enrich_dxy_indicator
        )

    # Get Put/Call Ratio from fear_greed_inputs
    putcall_data = get_put_call_ratio_data(storage)
    if putcall_data:
        put_call_ratio, putcall_timestamp = putcall_data
        # Extract date from timestamp for context calculation
        putcall_date = date.fromisoformat(putcall_timestamp[:10])

        # Calculate historical context
        from app.market.options_context import calculate_putcall_context  # noqa: PLC0415

        putcall_context = calculate_putcall_context(put_call_ratio, putcall_date, storage)

        enriched_indicators["putcall"] = intelligence.enrich_putcall_indicator(
            put_call_ratio,
            putcall_timestamp,
            context=putcall_context,  # type: ignore[arg-type]
        )

    # Get Options Activity metrics from options_market_metrics table
    options_activity = None
    options_data = get_options_activity_metrics(storage)
    if options_data:
        # Type narrowing with validation (get_options_activity_metrics already validates types)
        near_term = options_data["near_term_pct"]
        concentration = options_data["concentration_pct"]
        if isinstance(near_term, (int, float)) and isinstance(concentration, (int, float)):
            options_activity = OptionsActivityMetrics(
                near_term_pct=float(near_term),
                near_term_signal=str(options_data["near_term_signal"]),
                concentration_pct=float(concentration),
                concentration_signal=str(options_data["concentration_signal"]),
                top_sectors=options_data["top_sectors"],  # type: ignore[arg-type]
                last_updated=str(options_data["last_updated"]),
            )

    # Build response
    return MarketIntelligenceResponse(
        market_health=MarketHealthScoreResponse(
            overall_score=health_score_data.overall_score,
            overall_label=health_score_data.overall_label,
            last_updated=health_score_data.last_updated,
            trend=None,
            trend_change=None,
        ),
        fear_greed=FearGreedScore(
            score=int(fg_reading.score),
            label=fg_reading.label,
            score_change=fg_reading.score_change,
            signal_count=fg_reading.signal_count,
            last_updated=fg_reading.date,
            is_stale=fg_reading.is_stale,
            age_days=fg_reading.age_days,
            trend=fg_reading.trend,
            trend_change=fg_reading.trend_change,
        ),
        indicators=enriched_indicators,
        sector_rotation=SectorRotationSummary(
            leading=leading_sectors,
            neutral=neutral_sectors,
            lagging=lagging_sectors,
            leading_count=len(leading_sectors),
            neutral_count=len(neutral_sectors),
            lagging_count=len(lagging_sectors),
        ),
        options_activity=options_activity,
        last_updated=current_timestamp,
    )


@router.get("/trends", response_model=MarketTrendsResponse)
@cache_response(ttl=60)  # 1 minute cache for fresh data
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
@cache_response(ttl=60)  # Cache for 1 minute
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


# ============================================================================
# Historical Data Endpoints for Market Conditions Card Redesign
# ============================================================================


@router.get("/fear-greed-history", response_model=FearGreedHistoryResponse)
@cache_response(ttl=60)  # 1 minute cache for fresh data
async def get_fear_greed_history(
    request: Request,
    days: int = Query(
        365, ge=30, le=1825, description="Number of days of history (30-1825, ~5 years max)"
    ),
) -> FearGreedHistoryResponse:
    """Get Fear & Greed historical data for trend charts.

    Includes put/call ratio overlay data when available.
    """
    # Use repository for data access
    rows = market_repo.get_fear_greed_history_data(days)

    dates: list[str] = []
    scores: list[float] = []
    labels: list[str] = []
    put_call_ratios: list[float | None] = []
    for row in rows:
        if row[0] and row[1] is not None:
            formatted_date = format_db_date(row[0])
            if formatted_date is None:
                continue  # Skip if not a valid date type
            dates.append(formatted_date)
            scores.append(float(row[1]))
            labels.append(str(row[2]) if row[2] else "Unknown")
            # P/C ratio may be null for dates before we started collecting
            put_call_ratios.append(float(row[3]) if row[3] is not None else None)

    return FearGreedHistoryResponse(
        dates=dates, scores=scores, labels=labels, put_call_ratios=put_call_ratios
    )


@router.get("/news-sentiment-history", response_model=NewsSentimentHistoryResponse)
@cache_response(ttl=60)  # 1 minute cache
async def get_news_sentiment_history(
    request: Request,
    days: int = Query(
        30, ge=1, le=1825, description="Number of days of history (1-1825, ~5 years max)"
    ),
    granularity: str = Query(
        "daily",
        description="Data granularity: 'daily' for day-level, 'hourly' for hour-level",
    ),
) -> NewsSentimentHistoryResponse:
    """Get news sentiment historical data for trend charts.

    Returns daily or hourly aggregated sentiment scores from news_summary_log.
    Scores range from -1 (very negative) to +1 (very positive).
    """
    if granularity == "hourly":
        rows = market_repo.get_news_sentiment_hourly(days)
    else:
        rows = market_repo.get_news_sentiment_daily(days)

    dates: list[str] = []
    scores: list[float] = []
    positive_counts: list[int] = []
    negative_counts: list[int] = []
    article_counts: list[int] = []

    for row in rows:
        period, avg_score, pos_count, neg_count, total_count = row
        if period and avg_score is not None:
            formatted_date = format_db_date(period)
            if formatted_date is None:
                continue
            dates.append(formatted_date)
            scores.append(float(avg_score))
            positive_counts.append(int(pos_count) if pos_count else 0)
            negative_counts.append(int(neg_count) if neg_count else 0)
            article_counts.append(int(total_count) if total_count else 0)

    return NewsSentimentHistoryResponse(
        dates=dates,
        scores=scores,
        positive_counts=positive_counts,
        negative_counts=negative_counts,
        article_counts=article_counts,
    )


@router.get("/indicator-history", response_model=IndicatorHistoryResponse)
@cache_response(ttl=60)  # 1 minute cache for fresh data
async def get_indicator_history(
    request: Request,
    days: int = Query(
        365, ge=30, le=1825, description="Number of days of history (30-1825, ~5 years max)"
    ),
) -> IndicatorHistoryResponse:
    """Get key indicator historical data for trend charts."""
    indicators = {
        "sp500": "^GSPC",
        "vix": "^VIX",
        "tnx": "^TNX",
        "dxy": "DX-Y.NYB",
    }

    result_data: dict[str, list[dict[str, Any]]] = {}
    period_start = ""
    period_end = ""

    for key, symbol in indicators.items():
        # Use repository for data access
        rows = market_repo.get_indicator_history_data(symbol, days)

        data_points, period_start, period_end = build_indicator_data_points(
            rows, period_start, period_end
        )
        result_data[key] = data_points

    return IndicatorHistoryResponse(
        sp500=[IndicatorDataPoint(**dp) for dp in result_data.get("sp500", [])],
        vix=[IndicatorDataPoint(**dp) for dp in result_data.get("vix", [])],
        tnx=[IndicatorDataPoint(**dp) for dp in result_data.get("tnx", [])],
        dxy=[IndicatorDataPoint(**dp) for dp in result_data.get("dxy", [])],
        period_start=period_start,
        period_end=period_end,
    )


@router.get("/sector-history", response_model=SectorHistoryResponse)
@cache_response(ttl=300)  # 5 minute cache (fetches from yfinance which is slower)
async def get_sector_history(
    request: Request,
    days: int = Query(
        365, ge=30, le=1825, description="Number of days of history (30-1825, ~5 years max)"
    ),
) -> SectorHistoryResponse:
    """Get sector ETF historical data for performance charts.

    Uses yfinance directly to ensure adjusted prices (accounting for splits/dividends).
    This is necessary because DB stores prices at ingestion time which become stale
    after corporate actions like stock splits.
    """
    sectors: list[SectorHistory] = []
    period_start = ""
    period_end = ""

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    for symbol, name in SECTOR_ETFS.items():
        try:
            # Fetch fresh adjusted prices from yfinance
            ticker = yf.Ticker(symbol)
            hist = ticker.history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                auto_adjust=True,  # Critical: get split/dividend adjusted prices
            )

            if hist.empty:
                logger.warning("sector_history_no_data", symbol=symbol)
                continue

            # Convert to list of tuples (date, close) for build_sector_history
            rows = [
                (row.Index.date(), row.Close)
                for row in hist.itertuples()
                if row.Index is not None and row.Close is not None
            ]

            if not rows:
                continue

            # Validate: reject if pct change is unrealistic (> 60% loss or > 200% gain)
            if len(rows) >= 2:
                first_close = rows[0][1]
                last_close = rows[-1][1]
                pct_change = ((last_close - first_close) / first_close) * 100
                if pct_change < -60 or pct_change > 200:
                    logger.error(
                        "sector_history_unrealistic_change",
                        symbol=symbol,
                        first_close=first_close,
                        last_close=last_close,
                        pct_change=pct_change,
                    )
                    # Skip this sector rather than show bad data
                    continue

            sector_history, period_start, period_end = build_sector_history(
                symbol, name, rows, period_start, period_end
            )
            sectors.append(sector_history)

        except Exception as e:
            logger.error(
                "sector_history_fetch_error",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            continue

    # Sort by current performance descending
    sectors = sort_sectors_by_performance(sectors)

    return SectorHistoryResponse(
        sectors=sectors,
        period_start=period_start,
        period_end=period_end,
    )


# =============================================================================
# CORPORATE ACTIONS (FEAT-175)
# =============================================================================


@router.get("/corporate-actions")
async def get_corporate_actions(
    symbol: str | None = Query(None, description="Filter by symbol"),
    action_type: str = Query("buyback", description="Action type: buyback, dividend, split"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """
    Get corporate actions (buybacks, dividends, splits).

    Returns:
        List of corporate actions with amounts and dates.
    """
    # Use repository for data access
    rows = market_repo.get_corporate_actions(action_type, symbol, limit)

    actions = []
    for row in rows:
        actions.append(
            {
                "symbol": row[0],
                "action_type": row[1],
                "action_date": format_db_date(row[2]),
                "repurchase_amount": float(row[3]) if row[3] else None,
                "shares_repurchased": row[4],
                "dividend_amount": float(row[5]) if row[5] else None,
                "source": row[6],
                "updated_at": format_db_date(row[7]),
            }
        )

    return {
        "actions": actions,
        "total": len(actions),
        "action_type": action_type,
    }


@router.get("/corporate-actions/summary")
async def get_corporate_actions_summary(
    symbol: str | None = Query(None, description="Filter by symbol"),
) -> dict[str, Any]:
    """
    Get summary of corporate actions by symbol.

    Returns:
        Aggregated buyback totals and counts.
    """
    # Use repository for data access
    rows = market_repo.get_corporate_actions_summary(symbol)

    summaries = []
    for row in rows:
        summaries.append(
            {
                "symbol": row[0],
                "buyback_count": row[1] or 0,
                "total_buybacks": float(row[2]) if row[2] else 0,
                "latest_buyback": format_db_date(row[3]),
            }
        )

    return {
        "summaries": summaries,
        "total_symbols": len(summaries),
    }


@router.get("/movers", response_model=MarketMoversResponse)
@cache_response(ttl=900)  # 15 minute cache
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


# =============================================================================
# MARKET EVENTS (FOMC, CPI, NFP)
# =============================================================================


@router.get("/events")
async def get_market_events(
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    event_types: str | None = Query(None, description="Comma-separated event types"),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    """Get market events (FOMC, CPI, NFP, etc.) with optional filtering.

    Args:
        start_date: Filter events from this date (inclusive)
        end_date: Filter events until this date (inclusive)
        event_types: Comma-separated list of event types to filter
        limit: Maximum number of events to return

    Returns:
        MarketEventsResponse with list of events
    """
    # Parse dates
    start = date.fromisoformat(start_date) if start_date else None
    end = date.fromisoformat(end_date) if end_date else None

    # Parse and validate event types
    types_list = None
    if event_types:
        parsed_types = [t.strip() for t in event_types.split(",")]
        invalid_types = [t for t in parsed_types if t not in VALID_EVENT_TYPES]
        if invalid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid event type(s): {', '.join(invalid_types)}. Valid types: {', '.join(sorted(VALID_EVENT_TYPES))}"
            )
        types_list = cast(list[MarketEventType], parsed_types)

    response = svc_get_events(
        start_date=start,
        end_date=end,
        event_types=types_list,
        limit=limit,
    )

    return response.model_dump()


@router.get("/events/chart")
@cache_response(ttl=300)  # 5 minutes cache
async def get_market_events_for_chart(
    request: Request,
    days: int = Query(365, ge=7, le=730, description="Number of days of history"),
) -> dict[str, Any]:
    """Get market events formatted for chart overlay.

    Returns events with UI metadata (color, label) for display on sentiment charts.

    Args:
        days: Number of days of history to return

    Returns:
        List of events with UI metadata
    """
    end = date.today()
    start = end - timedelta(days=days)

    events = get_events_for_chart(start_date=start, end_date=end)

    return {
        "events": events,
        "total": len(events),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
    }


@router.get("/events/types")
async def get_market_event_types() -> dict[str, Any]:
    """Get metadata for all market event types.

    Returns:
        List of event types with labels, colors, and frequency info
    """
    types = get_event_type_info()
    return {
        "types": [t.model_dump() for t in types],
    }


@router.get("/events/upcoming")
async def get_upcoming_market_events(
    days: int = Query(30, ge=1, le=90, description="Days to look ahead"),
) -> dict[str, Any]:
    """Get upcoming market events.

    Args:
        days: Number of days to look ahead

    Returns:
        List of upcoming events
    """
    events = get_upcoming_events(days=days)
    return {
        "events": [e.model_dump() for e in events],
        "total": len(events),
        "days_ahead": days,
    }


@router.post("/events")
async def create_market_event(
    event_type: str = Query(..., description="Event type"),
    event_date: str = Query(..., description="Event date (YYYY-MM-DD)"),
    title: str = Query(..., description="Event title"),
    event_time: str | None = Query(None, description="Event time (HH:MM:SS)"),
    description: str | None = Query(None, description="Event description"),
    expected_value: float | None = Query(None, description="Expected/consensus value"),
    actual_value: float | None = Query(None, description="Actual released value"),
    prior_value: float | None = Query(None, description="Prior period value"),
    impact_score: int | None = Query(None, ge=-5, le=5, description="Impact score"),
    source: str = Query("manual", description="Data source"),
) -> dict[str, Any]:
    """Create a new market event.

    Returns:
        Created event with ID
    """
    # Validate event type
    if event_type not in VALID_EVENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid event_type: {event_type}. Valid types: {', '.join(sorted(VALID_EVENT_TYPES))}"
        )

    event = MarketEventCreate(
        event_type=cast(MarketEventType, event_type),
        event_date=event_date,
        event_time=event_time,
        title=title,
        description=description,
        expected_value=expected_value,
        actual_value=actual_value,
        prior_value=prior_value,
        impact_score=impact_score,
        source=source,
    )

    created = svc_create_event(event)
    return created.model_dump()


@router.patch("/events/{event_id}")
async def update_market_event(
    event_id: int,
    actual_value: float | None = Query(None, description="Actual released value"),
    surprise_pct: float | None = Query(None, description="Surprise percentage"),
    impact_score: int | None = Query(None, ge=-5, le=5, description="Impact score"),
    spy_change_1h: float | None = Query(None, description="SPY % change 1 hour after"),
    spy_change_1d: float | None = Query(None, description="SPY % change end of day"),
) -> dict[str, Any]:
    """Update a market event with actual values and market reaction.

    Returns:
        Updated event or 404 if not found
    """
    update = MarketEventUpdate(
        actual_value=actual_value,
        surprise_pct=surprise_pct,
        impact_score=impact_score,
        spy_change_1h=spy_change_1h,
        spy_change_1d=spy_change_1d,
    )

    updated = svc_update_event(event_id, update)
    if not updated:
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    return updated.model_dump()
