"""Market data API router."""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime
from typing import cast

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.market import intelligence, narrative_generator
from app.market.fear_greed_stub import get_fear_greed_score
from app.market.sentiment import MarketHealthScore, calculate_market_health
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
from app.portfolio.models import PriceData
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage
from app.utils.market_hours import (
    NY_TZ,
    MarketStatus,
    get_last_trading_day,
    get_market_status,
    get_next_trading_day,
    is_early_close_day,
    is_market_holiday,
)

router = APIRouter(prefix="/api/market", tags=["market"])

# Initialize services
storage = get_storage()
price_fetcher = PriceDataFetcher(storage)


# Response models (sentiment models imported from app.market.sentiment)
class MarketConditionsResponse(BaseModel):
    """Response model for market conditions."""

    sp500: dict[str, float | None | str] = Field(..., description="S&P 500 data")
    vix: dict[str, float | None | str] = Field(..., description="VIX volatility index")
    tnx: dict[str, float | None | str] = Field(..., description="10-Year Treasury yield")
    dxy: dict[str, float | None | str] = Field(..., description="US Dollar Index")
    health: MarketHealthScore = Field(..., description="Market health scoring")


class PriceResponse(BaseModel):
    """Response model for price data."""

    symbol: str
    price: float
    beta: float | None
    volatility: float | None
    sector: str | None


class PricesResponse(BaseModel):
    """Response model for multiple prices."""

    prices: dict[str, PriceResponse]
    count: int


# Helper functions
def calculate_daily_change_pct(
    ticker: str,
    current_price: float,
) -> float | None:
    """Calculate daily change percentage from day_bars historical data.

    Args:
        ticker: Symbol to calculate change for
        current_price: Current price

    Returns:
        Daily change percentage, or None if no historical data
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT close
            FROM day_bars
            WHERE ticker = %s
            ORDER BY date DESC
            LIMIT 1 OFFSET 1
            """,
            [ticker],
        )
        row = result.fetchone()
        if row and row[0]:
            prev_close = float(row[0])
            return ((current_price - prev_close) / prev_close) * 100
    return None


def calculate_weekly_change_pct(
    ticker: str,
    current_price: float,
) -> float | None:
    """Calculate week-over-week change: current price vs last week's close.

    Finds the last trading day of the previous calendar week (typically Friday,
    but could be Thursday if Friday was a holiday) and compares current price to that.

    This answers: "How are we doing this week compared to where we ended last week?"

    Args:
        ticker: Symbol to calculate change for
        current_price: Current price

    Returns:
        Week-over-week change percentage, or None if no historical data
    """
    with storage.connection() as conn:
        # Find last week's close: the most recent trading day before this week started
        # This week started on the most recent Monday (or today if today is Monday)
        result = conn.execute(
            """
            SELECT close, date
            FROM day_bars
            WHERE ticker = %s
              AND date < date_trunc('week', CURRENT_DATE)::date
            ORDER BY date DESC
            LIMIT 1
            """,
            [ticker],
        )
        row = result.fetchone()
        if row and row[0]:
            last_week_close = float(row[0])
            return ((current_price - last_week_close) / last_week_close) * 100
    return None


def fetch_sector_data_with_changes(
    sector_symbols: list[str],
    sector_price_data: dict[str, PriceData],
) -> dict[str, tuple[float | None, float | None, str | None]]:
    """Fetch sector data with daily change percentages using batch query.

    IMPORTANT: Uses ONLY day_bars historical data for change calculation.
    Never uses cache-to-cache comparison as cache timestamps are unreliable
    (cache may be refreshed without market data actually changing).

    Args:
        sector_symbols: List of sector ETF symbols
        sector_price_data: Dict of current price data by symbol

    Returns:
        Dict mapping symbol to (price, change_pct, timestamp) tuple
    """
    sector_data: dict[str, tuple[float | None, float | None, str | None]] = {}

    # Get previous closes in a single batch query (avoiding N+1 query problem)
    # Using window function to get second-most-recent close for each ticker
    # This ensures we calculate change from actual market closes, not cache timestamps
    with storage.connection() as conn:
        # Cast list[str] to expected parameter type for ANY operator compatibility
        params: list[
            str | int | float | bool | datetime | list[str | int | float | bool | None] | None
        ] = [cast(list[str | int | float | bool | None], sector_symbols)]

        result = conn.execute(
            """
            SELECT ticker, close
            FROM (
                SELECT ticker, close, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
                FROM day_bars
                WHERE ticker = ANY(%s)
            ) ranked
            WHERE rn = 2
            """,
            params,
        )
        prev_closes: dict[str, float] = {}
        for row in result.fetchall():
            ticker_val = row[0]
            close_val = row[1]
            if isinstance(ticker_val, str) and isinstance(close_val, (int, float)):
                prev_closes[ticker_val] = float(close_val)

    # Calculate change percentages
    for symbol in sector_symbols:
        current_price = sector_price_data.get(symbol)
        if not current_price:
            sector_data[symbol] = (None, None, None)
            continue

        prev_close = prev_closes.get(symbol)
        if prev_close:
            change_pct = ((current_price.price - prev_close) / prev_close) * 100
            sector_timestamp = current_price.cached_at.isoformat()
            sector_data[symbol] = (current_price.price, change_pct, sector_timestamp)
        else:
            # No historical data, just use current price
            sector_timestamp = current_price.cached_at.isoformat()
            sector_data[symbol] = (current_price.price, None, sector_timestamp)

    return sector_data


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
    sector_symbols = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLRE", "XLB", "XLC"]
    sector_price_data = price_fetcher.fetch_price_data(sector_symbols)

    # Get sector data with changes using batch query (avoiding N+1 query problem)
    sector_data = fetch_sector_data_with_changes(sector_symbols, sector_price_data)

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
@cache_response(ttl=300)
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
    actual_data_dates: dict[str, dt.datetime] = {}
    with storage.connection() as conn:
        for symbol in symbols:
            result = conn.execute("SELECT MAX(date) FROM day_bars WHERE ticker = %s", [symbol])
            row = result.fetchone()
            if row and row[0]:
                # Convert date to timestamp at market close (21:00 UTC = 4:00 PM ET)
                data_date = row[0]
                if isinstance(data_date, date):
                    data_timestamp = dt.datetime.combine(
                        data_date, dt.time(21, 0, 0), tzinfo=dt.UTC
                    )
                    actual_data_dates[symbol] = data_timestamp

    # Get Fear & Greed date to determine actual data freshness
    # (This represents when the market data was created, not when we cached it)
    # Get the actual market data date from Fear & Greed (most accurate source)
    # This represents when the underlying market data is from, not when we cached it
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT as_of_date FROM fear_greed_daily ORDER BY as_of_date DESC LIMIT 1"
        )
        row = result.fetchone()
        if row and row[0]:
            # Use the actual market data date (as_of_date) for the timestamp
            # This shows users the age of the underlying market data, not the cache
            market_data_date = row[0]
            # Set time to market close (4:00 PM ET = 21:00 UTC) for consistency
            if isinstance(market_data_date, date):
                market_close_time = dt.datetime.combine(
                    market_data_date, dt.time(21, 0, 0), tzinfo=dt.UTC
                )
                current_timestamp = market_close_time.isoformat()
            else:
                current_timestamp = (
                    sp500_data.cached_at.isoformat()
                    if sp500_data
                    else datetime.utcnow().isoformat() + "Z"
                )
        else:
            # Fallback to cache timestamp if no Fear & Greed data
            # This is less ideal but better than nothing
            current_timestamp = (
                sp500_data.cached_at.isoformat()
                if sp500_data
                else datetime.utcnow().isoformat() + "Z"
            )

    # Fetch sector ETF data
    sector_symbols = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLRE", "XLB", "XLC"]
    sector_price_data = price_fetcher.fetch_price_data(sector_symbols)

    # Get sector data with changes using batch query (avoiding N+1 query problem)
    sector_data_dict = fetch_sector_data_with_changes(sector_symbols, sector_price_data)

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
        vix=calculate_weekly_change_pct("^VIX", vix_data.price) if vix_data else None,
        sp500=calculate_weekly_change_pct("^GSPC", sp500_data.price) if sp500_data else None,
        tnx=calculate_weekly_change_pct("^TNX", tnx_data.price) if tnx_data else None,
        dxy=calculate_weekly_change_pct("DX-Y.NYB", dxy_data.price) if dxy_data else None,
    )

    # Build sector weekly changes with friendly names (all sectors, sorted by perf)
    all_sectors = leading_sectors + neutral_sectors + lagging_sectors
    sector_changes = [
        narrative_generator.SectorWeeklyChange(
            name=s.name,
            change_pct=calculate_weekly_change_pct(s.symbol, s.price) if s.price else None,
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
        vix_change = calculate_daily_change_pct("^VIX", vix_data.price)
        vix_timestamp = actual_data_dates.get("^VIX")
        # Temporarily override cached_at with actual data date
        if vix_timestamp:
            vix_data.cached_at = vix_timestamp
        enriched_indicators["vix"] = intelligence.enrich_vix_indicator(
            vix_data, health_score_data, change_pct=vix_change
        )
    if sp500_data:
        sp500_change = calculate_daily_change_pct("^GSPC", sp500_data.price)
        sp500_timestamp = actual_data_dates.get("^GSPC")
        if sp500_timestamp:
            sp500_data.cached_at = sp500_timestamp
        enriched_indicators["sp500"] = intelligence.enrich_sp500_indicator(
            sp500_data, health_score_data, change_pct=sp500_change
        )
    if tnx_data:
        tnx_change = calculate_daily_change_pct("^TNX", tnx_data.price)
        tnx_timestamp = actual_data_dates.get("^TNX")
        if tnx_timestamp:
            tnx_data.cached_at = tnx_timestamp
        enriched_indicators["tnx"] = intelligence.enrich_tnx_indicator(
            tnx_data, health_score_data, change_pct=tnx_change
        )
    if dxy_data:
        dxy_change = calculate_daily_change_pct("DX-Y.NYB", dxy_data.price)
        dxy_timestamp = actual_data_dates.get("DX-Y.NYB")
        if dxy_timestamp:
            dxy_data.cached_at = dxy_timestamp
        enriched_indicators["dxy"] = intelligence.enrich_dxy_indicator(
            dxy_data, health_score_data, change_pct=dxy_change
        )

    # Get Put/Call Ratio from fear_greed_inputs
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT put_call_ratio, as_of_date FROM fear_greed_inputs WHERE put_call_ratio IS NOT NULL ORDER BY as_of_date DESC LIMIT 1"
        )
        row = result.fetchone()
        if row and row[0]:
            put_call_ratio_val = row[0]
            putcall_date_val = row[1]
            # Type narrowing: ensure put_call_ratio is float and putcall_date is date
            if isinstance(put_call_ratio_val, (int, float)) and isinstance(putcall_date_val, date):
                put_call_ratio = float(put_call_ratio_val)
                putcall_date = putcall_date_val
                # Set time to market close (4:00 PM ET = 21:00 UTC) for consistency
                putcall_timestamp = dt.datetime.combine(
                    putcall_date, dt.time(21, 0, 0), tzinfo=dt.UTC
                ).isoformat()

                # Calculate historical context
                from app.market.options_context import calculate_putcall_context  # noqa: PLC0415

                putcall_context = calculate_putcall_context(put_call_ratio, putcall_date, storage)

                enriched_indicators["putcall"] = intelligence.enrich_putcall_indicator(
                    put_call_ratio, putcall_timestamp, context=putcall_context
                )

    # Get Options Activity metrics from options_market_metrics table
    options_activity = None
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT near_term_pct, concentration_pct, sector_weights, source_timestamp
            FROM options_market_metrics
            ORDER BY as_of_date DESC
            LIMIT 1
            """
        )
        row = result.fetchone()
        if row:
            near_term_val = row[0]
            concentration_val = row[1]
            sector_weights_val = row[2]  # JSONB
            source_timestamp_val = row[3]

            # Type narrowing: ensure proper types
            if isinstance(near_term_val, (int, float)) and isinstance(
                concentration_val, (int, float)
            ):
                near_term_pct = float(near_term_val)
                concentration_pct = float(concentration_val)

                # Calculate signals based on thresholds
                # Near-term: >65% = High (event-driven), 45-65% = Normal, <45% = Low
                if near_term_pct > 65:
                    near_term_signal = "High"
                elif near_term_pct >= 45:
                    near_term_signal = "Normal"
                else:
                    near_term_signal = "Low"

                # Concentration: >80% = Focused, 50-80% = Balanced, <50% = Dispersed
                if concentration_pct > 80:
                    concentration_signal = "Focused"
                elif concentration_pct >= 50:
                    concentration_signal = "Balanced"
                else:
                    concentration_signal = "Dispersed"

                # Get top 3 sectors by weight - ensure sector_weights is dict-like
                if isinstance(sector_weights_val, dict):
                    sector_items = sorted(
                        sector_weights_val.items(), key=lambda x: x[1], reverse=True
                    )[:3]
                    top_sectors = [
                        {"sector": sector, "weight_pct": weight} for sector, weight in sector_items
                    ]

                    # Ensure source_timestamp has isoformat method
                    if hasattr(source_timestamp_val, "isoformat"):
                        options_activity = OptionsActivityMetrics(
                            near_term_pct=near_term_pct,
                            near_term_signal=near_term_signal,
                            concentration_pct=concentration_pct,
                            concentration_signal=concentration_signal,
                            top_sectors=top_sectors,
                            last_updated=source_timestamp_val.isoformat(),
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
@cache_response(ttl=300)
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


class MarketStatusResponse(BaseModel):
    """Response model for market status endpoint."""

    status: MarketStatus = Field(..., description="Current market status")
    is_open: bool = Field(..., description="Whether market is currently open for regular trading")
    last_trading_day: str = Field(..., description="Most recent trading day (ISO format)")
    next_trading_day: str = Field(..., description="Next trading day (ISO format)")
    current_time_et: str = Field(..., description="Current time in Eastern Time")
    is_holiday: bool = Field(False, description="Whether today is a market holiday")
    holiday_name: str | None = Field(None, description="Holiday name if today is a holiday")
    is_early_close: bool = Field(False, description="Whether today is an early close day")
    early_close_name: str | None = Field(None, description="Early close day name if applicable")


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


class FearGreedHistoryResponse(BaseModel):
    """Response model for Fear & Greed history."""

    dates: list[str] = Field(..., description="ISO date strings")
    scores: list[float] = Field(..., description="Fear & Greed scores (0-100)")
    labels: list[str] = Field(..., description="Labels (Extreme Fear, Fear, etc.)")


@router.get("/fear-greed-history", response_model=FearGreedHistoryResponse)
@cache_response(ttl=300)
async def get_fear_greed_history(
    request: Request,
    days: int = Query(365, ge=7, le=730, description="Number of days of history"),
) -> FearGreedHistoryResponse:
    """Get Fear & Greed historical data for trend charts."""
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT as_of_date, score, label
            FROM fear_greed_daily
            WHERE as_of_date >= CURRENT_DATE - %s
            ORDER BY as_of_date ASC
            """,
            [days],
        )
        rows = result.fetchall()

    dates: list[str] = []
    scores: list[float] = []
    labels: list[str] = []
    for row in rows:
        if row[0] and row[1] is not None:
            dates.append(row[0].isoformat())
            scores.append(float(row[1]))
            labels.append(str(row[2]) if row[2] else "Unknown")

    return FearGreedHistoryResponse(dates=dates, scores=scores, labels=labels)


class IndicatorDataPoint(BaseModel):
    """Single data point for an indicator."""

    date: str
    close: float
    pct_change: float = Field(..., description="% change from period start")


class IndicatorHistoryResponse(BaseModel):
    """Response model for indicator history."""

    sp500: list[IndicatorDataPoint] = Field(default_factory=list)
    vix: list[IndicatorDataPoint] = Field(default_factory=list)
    tnx: list[IndicatorDataPoint] = Field(default_factory=list)
    dxy: list[IndicatorDataPoint] = Field(default_factory=list)
    period_start: str
    period_end: str


@router.get("/indicator-history", response_model=IndicatorHistoryResponse)
@cache_response(ttl=300)
async def get_indicator_history(
    request: Request,
    days: int = Query(365, ge=7, le=730, description="Number of days of history"),
) -> IndicatorHistoryResponse:
    """Get key indicator historical data for trend charts."""
    indicators = {
        "sp500": "^GSPC",
        "vix": "^VIX",
        "tnx": "^TNX",
        "dxy": "DX-Y.NYB",
    }

    result_data: dict[str, list[IndicatorDataPoint]] = {}
    period_start = ""
    period_end = ""

    for key, ticker in indicators.items():
        with storage.connection() as conn:
            query_result = conn.execute(
                """
                SELECT date, close
                FROM day_bars
                WHERE ticker = %s AND date >= CURRENT_DATE - %s
                ORDER BY date ASC
                """,
                [ticker, days],
            )
            rows = query_result.fetchall()

        data_points: list[IndicatorDataPoint] = []
        base_price: float | None = None
        for row in rows:
            if row[0] and row[1] is not None:
                close = float(row[1])
                if base_price is None:
                    base_price = close
                    if not period_start:
                        period_start = row[0].isoformat()
                pct_change = ((close - base_price) / base_price * 100) if base_price else 0
                data_points.append(
                    IndicatorDataPoint(
                        date=row[0].isoformat(),
                        close=close,
                        pct_change=round(pct_change, 2),
                    )
                )
                period_end = row[0].isoformat()
        result_data[key] = data_points

    return IndicatorHistoryResponse(
        sp500=result_data.get("sp500", []),
        vix=result_data.get("vix", []),
        tnx=result_data.get("tnx", []),
        dxy=result_data.get("dxy", []),
        period_start=period_start,
        period_end=period_end,
    )


class SectorDataPoint(BaseModel):
    """Single data point for a sector."""

    date: str
    close: float
    pct_change: float = Field(..., description="% change from period start")


class SectorHistory(BaseModel):
    """History data for a single sector."""

    name: str
    symbol: str
    data: list[SectorDataPoint]
    current_pct: float = Field(..., description="Current % change from period start")


class SectorHistoryResponse(BaseModel):
    """Response model for sector history."""

    sectors: list[SectorHistory]
    period_start: str
    period_end: str


SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLC": "Communication Services",
}


@router.get("/sector-history", response_model=SectorHistoryResponse)
@cache_response(ttl=300)
async def get_sector_history(
    request: Request,
    days: int = Query(365, ge=7, le=730, description="Number of days of history"),
) -> SectorHistoryResponse:
    """Get sector ETF historical data for performance charts."""
    sectors: list[SectorHistory] = []
    period_start = ""
    period_end = ""

    for symbol, name in SECTOR_ETFS.items():
        with storage.connection() as conn:
            query_result = conn.execute(
                """
                SELECT date, close
                FROM day_bars
                WHERE ticker = %s AND date >= CURRENT_DATE - %s
                ORDER BY date ASC
                """,
                [symbol, days],
            )
            rows = query_result.fetchall()

        data_points: list[SectorDataPoint] = []
        base_price: float | None = None
        current_pct = 0.0
        for row in rows:
            if row[0] and row[1] is not None:
                close = float(row[1])
                if base_price is None:
                    base_price = close
                    if not period_start:
                        period_start = row[0].isoformat()
                pct_change = ((close - base_price) / base_price * 100) if base_price else 0
                data_points.append(
                    SectorDataPoint(
                        date=row[0].isoformat(),
                        close=close,
                        pct_change=round(pct_change, 2),
                    )
                )
                current_pct = round(pct_change, 2)
                period_end = row[0].isoformat()

        sectors.append(
            SectorHistory(
                name=name,
                symbol=symbol,
                data=data_points,
                current_pct=current_pct,
            )
        )

    # Sort by current performance descending
    sectors.sort(key=lambda s: s.current_pct, reverse=True)

    return SectorHistoryResponse(
        sectors=sectors,
        period_start=period_start,
        period_end=period_end,
    )
