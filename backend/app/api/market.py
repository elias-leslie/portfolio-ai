"""Market data API router."""

from __future__ import annotations

import datetime as dt
from datetime import datetime

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.market import intelligence, narrative_generator
from app.market.fear_greed_stub import get_fear_greed_score
from app.market.sentiment import MarketHealthScore, calculate_market_health
from app.middleware.cache import cache_response
from app.models.market_intelligence import (
    FearGreedScore,
    MarketIntelligenceResponse,
    SectorRotationSummary,
)
from app.models.market_intelligence import (
    MarketHealthScore as MarketHealthScoreResponse,
)
from app.portfolio.models import PriceData
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

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
            (sector_symbols,),
        )
        prev_closes = {row[0]: float(row[1]) for row in result.fetchall()}

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
            market_close_time = dt.datetime.combine(
                market_data_date, dt.time(21, 0, 0), tzinfo=dt.UTC
            )
            current_timestamp = market_close_time.isoformat()
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

    # Generate narrative
    narrative = narrative_generator.generate_market_narrative(
        health_score=health_score_data.overall_score,
        fg_score=int(fg_reading.score),
        vix_price=vix_data.price if vix_data else None,
        sp500_price=sp500_data.price if sp500_data else None,
        tnx_yield=tnx_data.price if tnx_data else None,
        dxy_price=dxy_data.price if dxy_data else None,
        leading_sectors=leading_sector_names,
    )

    # Enrich indicators with plain-language labels using intelligence helpers
    # Calculate daily change percentages from day_bars historical data
    enriched_indicators = {}
    if vix_data:
        vix_change = calculate_daily_change_pct("^VIX", vix_data.price)
        enriched_indicators["vix"] = intelligence.enrich_vix_indicator(
            vix_data, health_score_data, change_pct=vix_change
        )
    if sp500_data:
        sp500_change = calculate_daily_change_pct("^GSPC", sp500_data.price)
        enriched_indicators["sp500"] = intelligence.enrich_sp500_indicator(
            sp500_data, health_score_data, change_pct=sp500_change
        )
    if tnx_data:
        tnx_change = calculate_daily_change_pct("^TNX", tnx_data.price)
        enriched_indicators["tnx"] = intelligence.enrich_tnx_indicator(
            tnx_data, health_score_data, change_pct=tnx_change
        )
    if dxy_data:
        dxy_change = calculate_daily_change_pct("DX-Y.NYB", dxy_data.price)
        enriched_indicators["dxy"] = intelligence.enrich_dxy_indicator(
            dxy_data, health_score_data, change_pct=dxy_change
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
        last_updated=current_timestamp,
    )
