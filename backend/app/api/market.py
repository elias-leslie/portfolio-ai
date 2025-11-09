"""Market data API router."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

router = APIRouter(prefix="/api/market", tags=["market"])

# Initialize services
storage = get_storage()
price_fetcher = PriceDataFetcher(storage)


# Response models
class ComponentScore(BaseModel):
    """Individual component score with details."""

    name: str
    score: int = Field(..., ge=0, le=100, description="Component score 0-100")
    value: float | None = Field(None, description="Raw metric value")
    interpretation: str = Field(..., description="Human-readable interpretation")
    signal: str = Field(..., description="Bullish/Neutral/Bearish")
    last_updated: str | None = Field(None, description="Last update timestamp (ISO 8601)")


class SectorScore(BaseModel):
    """Sector performance score."""

    symbol: str = Field(..., description="Sector ETF symbol (e.g., XLK)")
    name: str = Field(..., description="Sector name (e.g., Technology)")
    price: float | None = Field(None, description="Current price")
    change_pct: float | None = Field(None, description="Daily change percentage")
    signal: str = Field(..., description="Leading/Neutral/Lagging")
    last_updated: str | None = Field(None, description="Last update timestamp (ISO 8601)")


class MarketHealthScore(BaseModel):
    """Overall market health scoring."""

    overall_score: int = Field(..., ge=0, le=100, description="Overall market health 0-100")
    overall_label: str = Field(..., description="Extreme Fear/Fear/Neutral/Bullish/Very Bullish")
    components: list[ComponentScore] = Field(..., description="Individual component scores")
    sectors: list[SectorScore] = Field(
        default_factory=list, description="Sector performance breakdown"
    )
    last_updated: str = Field(..., description="Last update timestamp")


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


def _calculate_vix_score(vix_price: float, timestamp: str | None) -> ComponentScore:
    """Calculate VIX volatility component score (inverted: low VIX = high score)."""
    # VIX ranges: <15 = complacent, 15-20 = normal, 20-30 = elevated, >30 = fear
    if vix_price < 15:
        score, signal, interp = 85, "Bullish", "Low volatility suggests market complacency"
    elif vix_price < 20:
        score, signal, interp = 65, "Bullish", "Normal volatility levels"
    elif vix_price < 25:
        score, signal, interp = 45, "Neutral", "Elevated volatility, some concern"
    elif vix_price < 30:
        score, signal, interp = 30, "Bearish", "High volatility, increased fear"
    else:
        score, signal, interp = 15, "Bearish", "Extreme volatility, market panic"

    return ComponentScore(
        name="Volatility (VIX)",
        score=score,
        value=vix_price,
        interpretation=interp,
        signal=signal,
        last_updated=timestamp,
    )


def _calculate_sp500_score(sp500_price: float, timestamp: str | None) -> ComponentScore:
    """Calculate S&P 500 level component score."""
    # Normalize around 4000-5000 range
    if sp500_price > 4800:
        score, signal, interp = 75, "Bullish", "Strong market levels"
    elif sp500_price > 4400:
        score, signal, interp = 60, "Bullish", "Healthy market levels"
    elif sp500_price > 4000:
        score, signal, interp = 50, "Neutral", "Moderate market levels"
    else:
        score, signal, interp = 40, "Bearish", "Below average levels"

    return ComponentScore(
        name="S&P 500 Level",
        score=score,
        value=sp500_price,
        interpretation=interp,
        signal=signal,
        last_updated=timestamp,
    )


def _calculate_tnx_score(tnx_yield: float, timestamp: str | None) -> ComponentScore:
    """Calculate 10Y Treasury yield component score (Goldilocks: not too hot, not too cold)."""
    # 10Y yield ranges: <3% = dovish, 3-4.5% = neutral, >4.5% = hawkish
    if 3.5 <= tnx_yield <= 4.5:
        score, signal, interp = 60, "Neutral", "Yields in healthy range"
    elif tnx_yield < 3.0:
        score, signal, interp = 45, "Neutral", "Low yields, recession concerns"
    elif tnx_yield < 3.5:
        score, signal, interp = 55, "Neutral", "Moderate yields"
    elif tnx_yield < 5.0:
        score, signal, interp = 45, "Bearish", "Rising yields, tightening concerns"
    else:
        score, signal, interp = 35, "Bearish", "High yields, aggressive tightening"

    return ComponentScore(
        name="10Y Treasury Yield",
        score=score,
        value=tnx_yield,
        interpretation=interp,
        signal=signal,
        last_updated=timestamp,
    )


def _calculate_dxy_score(dxy_price: float, timestamp: str | None) -> ComponentScore:
    """Calculate US Dollar Index component score."""
    # DXY ranges: <100 = weak, 100-105 = normal, >105 = strong
    if dxy_price < 100:
        score, signal, interp = 65, "Bullish", "Weak dollar supports stocks"
    elif dxy_price < 105:
        score, signal, interp = 55, "Neutral", "Dollar at moderate levels"
    else:
        score, signal, interp = 45, "Bearish", "Strong dollar headwind"

    return ComponentScore(
        name="US Dollar (DXY)",
        score=score,
        value=dxy_price,
        interpretation=interp,
        signal=signal,
        last_updated=timestamp,
    )


def _calculate_sector_scores(
    sector_data: dict[str, tuple[float | None, float | None, str | None]],
) -> list[SectorScore]:
    """Calculate sector rotation scores with relative performance signals."""
    # Sector ETF mapping
    sector_names = {
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

    # Collect all valid change_pct values for relative comparison
    changes = [
        change_pct for _, (_, change_pct, _) in sector_data.items() if change_pct is not None
    ]

    # Calculate thresholds for Leading/Neutral/Lagging
    if changes:
        changes_sorted = sorted(changes)
        # Top 33% = Leading, Middle 34% = Neutral, Bottom 33% = Lagging
        top_threshold = (
            changes_sorted[int(len(changes_sorted) * 0.67)] if len(changes_sorted) > 2 else 0.5
        )
        bottom_threshold = (
            changes_sorted[int(len(changes_sorted) * 0.33)] if len(changes_sorted) > 2 else -0.5
        )
    else:
        top_threshold, bottom_threshold = 0.5, -0.5

    # Create sector scores
    sectors = []
    for symbol, (price, change_pct, timestamp) in sector_data.items():
        name = sector_names.get(symbol, symbol)

        # Determine signal based on change_pct
        if change_pct is not None:
            if change_pct >= top_threshold:
                signal = "Leading"
            elif change_pct <= bottom_threshold:
                signal = "Lagging"
            else:
                signal = "Neutral"
        else:
            signal = "Unknown"

        sectors.append(
            SectorScore(
                symbol=symbol,
                name=name,
                price=price,
                change_pct=change_pct,
                signal=signal,
                last_updated=timestamp,
            )
        )

    # Sort sectors by change_pct descending (best performers first)
    sectors.sort(
        key=lambda s: s.change_pct if s.change_pct is not None else -999,
        reverse=True,
    )

    return sectors


def calculate_market_health(
    vix_price: float | None,
    sp500_price: float | None,
    tnx_yield: float | None,
    dxy_price: float | None,
    sector_data: dict[str, tuple[float | None, float | None, str | None]] | None = None,
    current_timestamp: str | None = None,
) -> MarketHealthScore:
    """Calculate overall market health score from indicators.

    Scoring philosophy:
    - VIX: Lower = bullish (less fear), Higher = bearish (more fear)
    - S&P 500: Use absolute level as proxy for sentiment
    - Treasury yield: Moderate yields = healthy, extremes = concern
    - Dollar: Stable/slightly weak = bullish for stocks

    Args:
        vix_price: Current VIX price
        sp500_price: Current S&P 500 price
        tnx_yield: Current 10Y Treasury yield
        dxy_price: Current US Dollar Index price
        sector_data: Dict mapping sector ETF symbol to (price, change_pct, timestamp) tuple
        current_timestamp: Current fetch timestamp (ISO 8601) for real-time data

    Returns:
        MarketHealthScore with overall score and component breakdown
    """
    components: list[ComponentScore] = []

    # Calculate component scores using helper functions
    if vix_price is not None:
        components.append(_calculate_vix_score(vix_price, current_timestamp))

    if sp500_price is not None:
        components.append(_calculate_sp500_score(sp500_price, current_timestamp))

    if tnx_yield is not None:
        components.append(_calculate_tnx_score(tnx_yield, current_timestamp))

    if dxy_price is not None:
        components.append(_calculate_dxy_score(dxy_price, current_timestamp))

    # Calculate overall score (average of components)
    total_score = sum(c.score for c in components)
    overall_score = int(total_score / len(components)) if components else 50

    # Map to label
    if overall_score >= 75:
        label = "Very Bullish"
    elif overall_score >= 60:
        label = "Bullish"
    elif overall_score >= 45:
        label = "Neutral"
    elif overall_score >= 30:
        label = "Bearish"
    else:
        label = "Extreme Fear"

    # Calculate sector scores
    sectors = _calculate_sector_scores(sector_data) if sector_data else []

    return MarketHealthScore(
        overall_score=overall_score,
        overall_label=label,
        components=components,
        sectors=sectors,
        last_updated=datetime.utcnow().isoformat(),
    )


@router.get("/conditions", response_model=MarketConditionsResponse)
async def get_market_conditions() -> MarketConditionsResponse:
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

    # Query OHLCV data for previous close to calculate daily change %
    sector_data: dict[str, tuple[float | None, float | None, str | None]] = {}
    with storage.connection() as conn:
        for symbol in sector_symbols:
            current_price = sector_price_data.get(symbol)
            if not current_price:
                sector_data[symbol] = (None, None, None)
                continue

            # Get previous close from OHLCV data (for calculating daily change %)
            result = conn.execute(
                """
                SELECT close
                FROM day_bars
                WHERE ticker = %s
                ORDER BY date DESC
                LIMIT 1 OFFSET 1
                """,
                (symbol,),
            )
            row = result.fetchone()

            if row and row[0]:
                prev_close = float(row[0])
                change_pct = ((current_price.price - prev_close) / prev_close) * 100
                # Use actual cached_at timestamp from price data (respects 15-min cache)
                sector_timestamp = current_price.cached_at.isoformat()
                sector_data[symbol] = (current_price.price, change_pct, sector_timestamp)
            else:
                # No historical data, just use current price
                sector_timestamp = current_price.cached_at.isoformat()
                sector_data[symbol] = (current_price.price, None, sector_timestamp)

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
async def get_prices(
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
