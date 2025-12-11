"""Market data API router."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

import yfinance as yf
from fastapi import APIRouter, Query, Request

from app.api.market_data_sources import (
    calculate_daily_change_pct,
    calculate_weekly_change_pct,
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
from app.market import intelligence, narrative_generator
from app.market.fear_greed_stub import get_fear_greed_score
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
from app.storage import get_storage
from app.utils.market_hours import (
    NY_TZ,
    get_last_trading_day,
    get_market_status,
    get_next_trading_day,
    is_early_close_day,
    is_market_holiday,
)

router = APIRouter(prefix="/api/market", tags=["market"])
logger = get_logger(__name__)

# Initialize services
storage = get_storage()
price_fetcher = PriceDataFetcher(storage)


# API endpoints
@router.get("/conditions", response_model=MarketConditionsResponse)
@cache_response(ttl=300)  # 5 minutes cache
async def get_market_conditions(request: Request) -> MarketConditionsResponse:
    """Get current market conditions with health scoring.

    Returns:
        Market indicators with overall health score and component breakdown
    """
    # Fetch market indicators
    # Using ^GSPC for S&P 500, ^VIX for VIX, ^TNX for 10Y yield, DX-Y.NYB for USD
    symbols = ["^GSPC", "^VIX", "^TNX", "DX-Y.NYB"]
    price_data = price_fetcher.fetch_price_data(symbols)

    sp500_data = price_data.get("^GSPC")
    vix_data = price_data.get("^VIX")
    tnx_data = price_data.get("^TNX")
    dxy_data = price_data.get("DX-Y.NYB")

    # Get actual timestamp from fetched data (respects 15-min cache)
    # Note: cached_at already has timezone info, isoformat() includes it
    current_timestamp = (
        sp500_data.cached_at.isoformat() if sp500_data else datetime.utcnow().isoformat() + "Z"
    )

    # Fetch sector ETF data
    sector_symbols = get_sector_symbols()
    sector_price_data = price_fetcher.fetch_price_data(sector_symbols)

    # Get sector data with changes using batch query (avoiding N+1 query problem)
    sector_data = fetch_sector_data_with_changes(storage, sector_symbols, sector_price_data)

    # Calculate market health score with sector data
    health_score = calculate_market_health(
        vix_price=vix_data.price if vix_data else None,
        sp500_price=sp500_data.price if sp500_data else None,
        tnx_yield=tnx_data.price if tnx_data else None,
        dxy_price=dxy_data.price if dxy_data else None,
        sector_data=sector_data,
        current_timestamp=current_timestamp,
    )

    return MarketConditionsResponse(
        sp500={
            "price": sp500_data.price if sp500_data else None,
            "change_pct": None,  # Would need historical data
            "last_updated": sp500_data.cached_at.isoformat() if sp500_data else None,
        },
        vix={
            "price": vix_data.price if vix_data else None,
            "level": None,
            "last_updated": vix_data.cached_at.isoformat() if vix_data else None,
        },
        tnx={
            "yield": tnx_data.price if tnx_data else None,
            "last_updated": tnx_data.cached_at.isoformat() if tnx_data else None,
        },
        dxy={
            "price": dxy_data.price if dxy_data else None,
            "last_updated": dxy_data.cached_at.isoformat() if dxy_data else None,
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
    # Fetch market indicators
    symbols = ["^GSPC", "^VIX", "^TNX", "DX-Y.NYB"]
    price_data = price_fetcher.fetch_price_data(symbols)

    sp500_data = price_data.get("^GSPC")
    vix_data = price_data.get("^VIX")
    tnx_data = price_data.get("^TNX")
    dxy_data = price_data.get("DX-Y.NYB")

    # Get ACTUAL data dates from day_bars (not cache timestamps)
    # This shows when the market data was created, not when we fetched it
    actual_data_dates = get_actual_data_dates(storage, symbols)

    # Get the actual market data date from Fear & Greed (most accurate source)
    # This represents when the underlying market data is from, not when we cached it
    current_timestamp = get_market_data_timestamp(storage)
    if not current_timestamp:
        # Fallback to cache timestamp if no Fear & Greed data
        current_timestamp = (
            sp500_data.cached_at.isoformat() if sp500_data else datetime.utcnow().isoformat() + "Z"
        )

    # Fetch sector ETF data
    sector_symbols = get_sector_symbols()
    sector_price_data = price_fetcher.fetch_price_data(sector_symbols)

    # Get sector data with changes using batch query (avoiding N+1 query problem)
    sector_data_dict = fetch_sector_data_with_changes(storage, sector_symbols, sector_price_data)

    # Convert to list format for intelligence helper
    sector_data_list = [(symbol, *sector_data_dict[symbol]) for symbol in sector_symbols]

    # Calculate market health score (existing logic)
    health_score_data = calculate_market_health(
        vix_price=vix_data.price if vix_data else None,
        sp500_price=sp500_data.price if sp500_data else None,
        tnx_yield=tnx_data.price if tnx_data else None,
        dxy_price=dxy_data.price if dxy_data else None,
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

    # Extract leading sector names for narrative
    leading_sector_names = [s.name for s in leading_sectors[:3]]  # Top 3

    # Calculate weekly changes for dynamic narrative
    weekly_changes = narrative_generator.WeeklyChanges(
        vix=calculate_weekly_change_pct(storage, "^VIX", vix_data.price) if vix_data else None,
        sp500=calculate_weekly_change_pct(storage, "^GSPC", sp500_data.price)
        if sp500_data
        else None,
        tnx=calculate_weekly_change_pct(storage, "^TNX", tnx_data.price) if tnx_data else None,
        dxy=calculate_weekly_change_pct(storage, "DX-Y.NYB", dxy_data.price) if dxy_data else None,
    )

    # Build sector weekly changes with friendly names (all sectors, sorted by perf)
    all_sectors = leading_sectors + neutral_sectors + lagging_sectors
    sector_changes = [
        narrative_generator.SectorWeeklyChange(
            name=s.name,
            change_pct=calculate_weekly_change_pct(storage, s.symbol, s.price) if s.price else None,
        )
        for s in all_sectors
    ]

    # Generate narrative with dynamic weekly data
    narrative = narrative_generator.generate_market_narrative(
        health_score=health_score_data.overall_score,
        fg_score=int(fg_reading.score),
        vix_price=vix_data.price if vix_data else None,
        sp500_price=sp500_data.price if sp500_data else None,
        tnx_yield=tnx_data.price if tnx_data else None,
        dxy_price=dxy_data.price if dxy_data else None,
        leading_sectors=leading_sector_names,
        weekly_changes=weekly_changes,
        sector_changes=sector_changes,
    )

    # Enrich indicators with plain-language labels using intelligence helpers
    # Calculate daily change percentages from day_bars historical data
    # Use actual data timestamps (from day_bars) instead of cache timestamps
    enriched_indicators = {}
    if vix_data:
        vix_change = calculate_daily_change_pct(storage, "^VIX", vix_data.price)
        vix_timestamp = actual_data_dates.get("^VIX")
        # Temporarily override cached_at with actual data date
        if vix_timestamp:
            vix_data.cached_at = vix_timestamp
        enriched_indicators["vix"] = intelligence.enrich_vix_indicator(
            vix_data, health_score_data, change_pct=vix_change
        )
    if sp500_data:
        sp500_change = calculate_daily_change_pct(storage, "^GSPC", sp500_data.price)
        sp500_timestamp = actual_data_dates.get("^GSPC")
        if sp500_timestamp:
            sp500_data.cached_at = sp500_timestamp
        enriched_indicators["sp500"] = intelligence.enrich_sp500_indicator(
            sp500_data, health_score_data, change_pct=sp500_change
        )
    if tnx_data:
        tnx_change = calculate_daily_change_pct(storage, "^TNX", tnx_data.price)
        tnx_timestamp = actual_data_dates.get("^TNX")
        if tnx_timestamp:
            tnx_data.cached_at = tnx_timestamp
        enriched_indicators["tnx"] = intelligence.enrich_tnx_indicator(
            tnx_data, health_score_data, change_pct=tnx_change
        )
    if dxy_data:
        dxy_change = calculate_daily_change_pct(storage, "DX-Y.NYB", dxy_data.price)
        dxy_timestamp = actual_data_dates.get("DX-Y.NYB")
        if dxy_timestamp:
            dxy_data.cached_at = dxy_timestamp
        enriched_indicators["dxy"] = intelligence.enrich_dxy_indicator(
            dxy_data, health_score_data, change_pct=dxy_change
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
        # Type narrowing for mypy
        near_term = options_data["near_term_pct"]
        concentration = options_data["concentration_pct"]
        assert isinstance(near_term, (int, float))
        assert isinstance(concentration, (int, float))
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
        narrative=narrative,
        market_health=MarketHealthScoreResponse(
            overall_score=health_score_data.overall_score,
            overall_label=health_score_data.overall_label,
            last_updated=health_score_data.last_updated,
            trend=None,  # TODO: Calculate from historical data
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
    # Query fear_greed_daily table for historical data
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT as_of_date, score
            FROM fear_greed_daily
            ORDER BY as_of_date DESC
            LIMIT %s
            """,
            [days],
        )
        rows = result.fetchall()

    # Reverse to get chronological order (oldest first)
    rows = list(reversed(rows))

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

    return MarketStatusResponse(
        status=status,
        is_open=status == "open",
        last_trading_day=last_trading.isoformat(),
        next_trading_day=next_trading.isoformat(),
        current_time_et=now.strftime("%Y-%m-%d %H:%M:%S ET"),
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
    with storage.connection() as conn:
        # Join with fear_greed_inputs to get put_call_ratio
        result = conn.execute(
            """
            SELECT d.as_of_date, d.score, d.label, i.put_call_ratio
            FROM fear_greed_daily d
            LEFT JOIN fear_greed_inputs i ON d.as_of_date = i.as_of_date
            WHERE d.as_of_date >= CURRENT_DATE - %s
            ORDER BY d.as_of_date ASC
            """,
            [days],
        )
        rows = result.fetchall()

    dates: list[str] = []
    scores: list[float] = []
    labels: list[str] = []
    put_call_ratios: list[float | None] = []
    for row in rows:
        if row[0] and row[1] is not None:
            # row[0] is date from SQL - handle as datetime/date object
            date_val = row[0]
            if isinstance(date_val, (datetime, date)):
                dates.append(date_val.isoformat())
            elif isinstance(date_val, str):
                dates.append(date_val)
            else:
                continue  # Skip if not a valid date type
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
    with storage.connection() as conn:
        if granularity == "hourly":
            # Hourly aggregation - useful for intraday view
            result = conn.execute(
                """
                SELECT
                    DATE_TRUNC('hour', window_end) as period,
                    AVG(sentiment_score) as avg_score,
                    SUM(positive_count) as pos_count,
                    SUM(negative_count) as neg_count,
                    SUM(article_count) as total_count
                FROM news_summary_log
                WHERE symbol = '__MARKET__'
                  AND window_end >= NOW() - INTERVAL '%s days'
                GROUP BY DATE_TRUNC('hour', window_end)
                ORDER BY period ASC
                """,
                [days],
            )
        else:
            # Daily aggregation - use last reading per day for consistency
            result = conn.execute(
                """
                SELECT DISTINCT ON (DATE(window_end))
                    DATE(window_end) as period,
                    sentiment_score as avg_score,
                    positive_count as pos_count,
                    negative_count as neg_count,
                    article_count as total_count
                FROM news_summary_log
                WHERE symbol = '__MARKET__'
                  AND window_end >= NOW() - INTERVAL '%s days'
                ORDER BY DATE(window_end), window_end DESC
                """,
                [days],
            )
        rows = result.fetchall()

    dates: list[str] = []
    scores: list[float] = []
    positive_counts: list[int] = []
    negative_counts: list[int] = []
    article_counts: list[int] = []

    for row in rows:
        period, avg_score, pos_count, neg_count, total_count = row
        if period and avg_score is not None:
            if isinstance(period, (datetime, date)):
                dates.append(period.isoformat())
            else:
                dates.append(str(period))
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
        with storage.connection() as conn:
            query_result = conn.execute(
                """
                SELECT date, close
                FROM day_bars
                WHERE symbol = %s AND date >= CURRENT_DATE - %s
                ORDER BY date ASC
                """,
                [symbol, days],
            )
            rows = query_result.fetchall()

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

    sql = """
        SELECT symbol, action_type, action_date, repurchase_amount,
               shares_repurchased, dividend_amount, source, updated_at
        FROM corporate_actions
        WHERE action_type = %s
    """
    params: list[Any] = [action_type]

    if symbol:
        sql += " AND symbol = %s"
        params.append(symbol.upper())

    sql += " ORDER BY action_date DESC LIMIT %s"
    params.append(limit)

    with storage.connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    actions = []
    for row in rows:
        actions.append(
            {
                "symbol": row[0],
                "action_type": row[1],
                "action_date": row[2].isoformat() if isinstance(row[2], (date, datetime)) else None,
                "repurchase_amount": float(row[3]) if row[3] else None,
                "shares_repurchased": row[4],
                "dividend_amount": float(row[5]) if row[5] else None,
                "source": row[6],
                "updated_at": row[7].isoformat() if isinstance(row[7], (date, datetime)) else None,
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

    sql = """
        SELECT symbol,
               COUNT(*) FILTER (WHERE action_type = 'buyback') as buyback_count,
               SUM(repurchase_amount) FILTER (WHERE action_type = 'buyback') as total_buybacks,
               MAX(action_date) FILTER (WHERE action_type = 'buyback') as latest_buyback
        FROM corporate_actions
    """
    params: list[Any] = []

    if symbol:
        sql += " WHERE symbol = %s"
        params.append(symbol.upper())

    sql += " GROUP BY symbol ORDER BY total_buybacks DESC NULLS LAST"

    with storage.connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    summaries = []
    for row in rows:
        summaries.append(
            {
                "symbol": row[0],
                "buyback_count": row[1] or 0,
                "total_buybacks": float(row[2]) if row[2] else 0,
                "latest_buyback": row[3].isoformat()
                if isinstance(row[3], (date, datetime))
                else None,
            }
        )

    return {
        "summaries": summaries,
        "total_symbols": len(summaries),
    }
