"""Market data API router."""

from __future__ import annotations

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


class MarketHealthScore(BaseModel):
    """Overall market health scoring."""

    overall_score: int = Field(..., ge=0, le=100, description="Overall market health 0-100")
    overall_label: str = Field(..., description="Extreme Fear/Fear/Neutral/Bullish/Very Bullish")
    components: list[ComponentScore] = Field(..., description="Individual component scores")
    last_updated: str = Field(..., description="Last update timestamp")


class MarketConditionsResponse(BaseModel):
    """Response model for market conditions."""

    sp500: dict[str, float | None] = Field(..., description="S&P 500 data")
    vix: dict[str, float | None] = Field(..., description="VIX volatility index")
    tnx: dict[str, float | None] = Field(..., description="10-Year Treasury yield")
    dxy: dict[str, float | None] = Field(..., description="US Dollar Index")
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


def calculate_market_health(
    vix_price: float | None,
    sp500_price: float | None,
    tnx_yield: float | None,
    dxy_price: float | None,
) -> MarketHealthScore:
    """Calculate overall market health score from indicators.

    Scoring philosophy:
    - VIX: Lower = bullish (less fear), Higher = bearish (more fear)
    - S&P 500: Use absolute level as proxy for sentiment
    - Treasury yield: Moderate yields = healthy, extremes = concern
    - Dollar: Stable/slightly weak = bullish for stocks

    Returns:
        MarketHealthScore with overall score and component breakdown
    """
    from datetime import datetime

    components: list[ComponentScore] = []
    total_score = 0
    component_count = 0

    # VIX Scoring (0-100, inverted: low VIX = high score)
    if vix_price is not None:
        # VIX ranges: <15 = complacent, 15-20 = normal, 20-30 = elevated, >30 = fear
        if vix_price < 15:
            vix_score = 85  # Very bullish (low fear)
            vix_signal = "Bullish"
            vix_interp = "Low volatility suggests market complacency"
        elif vix_price < 20:
            vix_score = 65  # Bullish (normal fear)
            vix_signal = "Bullish"
            vix_interp = "Normal volatility levels"
        elif vix_price < 25:
            vix_score = 45  # Neutral
            vix_signal = "Neutral"
            vix_interp = "Elevated volatility, some concern"
        elif vix_price < 30:
            vix_score = 30  # Bearish
            vix_signal = "Bearish"
            vix_interp = "High volatility, increased fear"
        else:
            vix_score = 15  # Very bearish
            vix_signal = "Bearish"
            vix_interp = "Extreme volatility, market panic"

        components.append(
            ComponentScore(
                name="Volatility (VIX)",
                score=vix_score,
                value=vix_price,
                interpretation=vix_interp,
                signal=vix_signal,
            )
        )
        total_score += vix_score
        component_count += 1

    # S&P 500 Momentum (use absolute level as proxy)
    if sp500_price is not None:
        # Simple heuristic: higher = more bullish sentiment
        # Normalize around 4000-5000 range
        if sp500_price > 4800:
            sp_score = 75
            sp_signal = "Bullish"
            sp_interp = "Strong market levels"
        elif sp500_price > 4400:
            sp_score = 60
            sp_signal = "Bullish"
            sp_interp = "Healthy market levels"
        elif sp500_price > 4000:
            sp_score = 50
            sp_signal = "Neutral"
            sp_interp = "Moderate market levels"
        else:
            sp_score = 40
            sp_signal = "Bearish"
            sp_interp = "Below average levels"

        components.append(
            ComponentScore(
                name="S&P 500 Level",
                score=sp_score,
                value=sp500_price,
                interpretation=sp_interp,
                signal=sp_signal,
            )
        )
        total_score += sp_score
        component_count += 1

    # Treasury Yield (Goldilocks: not too hot, not too cold)
    if tnx_yield is not None:
        # 10Y yield ranges: <3% = dovish, 3-4.5% = neutral, >4.5% = hawkish
        if 3.5 <= tnx_yield <= 4.5:
            tnx_score = 60
            tnx_signal = "Neutral"
            tnx_interp = "Yields in healthy range"
        elif tnx_yield < 3.0:
            tnx_score = 45
            tnx_signal = "Neutral"
            tnx_interp = "Low yields, recession concerns"
        elif tnx_yield < 3.5:
            tnx_score = 55
            tnx_signal = "Neutral"
            tnx_interp = "Moderate yields"
        elif tnx_yield < 5.0:
            tnx_score = 45
            tnx_signal = "Bearish"
            tnx_interp = "Rising yields, tightening concerns"
        else:
            tnx_score = 35
            tnx_signal = "Bearish"
            tnx_interp = "High yields, aggressive tightening"

        components.append(
            ComponentScore(
                name="10Y Treasury Yield",
                score=tnx_score,
                value=tnx_yield,
                interpretation=tnx_interp,
                signal=tnx_signal,
            )
        )
        total_score += tnx_score
        component_count += 1

    # Dollar Strength (moderate strength = bullish for stocks)
    if dxy_price is not None:
        # DXY ranges: <100 = weak, 100-105 = normal, >105 = strong
        if dxy_price < 100:
            dxy_score = 65
            dxy_signal = "Bullish"
            dxy_interp = "Weak dollar supports stocks"
        elif dxy_price < 105:
            dxy_score = 55
            dxy_signal = "Neutral"
            dxy_interp = "Dollar at moderate levels"
        else:
            dxy_score = 45
            dxy_signal = "Bearish"
            dxy_interp = "Strong dollar headwind"

        components.append(
            ComponentScore(
                name="US Dollar (DXY)",
                score=dxy_score,
                value=dxy_price,
                interpretation=dxy_interp,
                signal=dxy_signal,
            )
        )
        total_score += dxy_score
        component_count += 1

    # Calculate overall score (average of components)
    overall_score = int(total_score / component_count) if component_count > 0 else 50

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

    return MarketHealthScore(
        overall_score=overall_score,
        overall_label=label,
        components=components,
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

    # Calculate market health score
    health_score = calculate_market_health(
        vix_price=vix_data.price if vix_data else None,
        sp500_price=sp500_data.price if sp500_data else None,
        tnx_yield=tnx_data.price if tnx_data else None,
        dxy_price=dxy_data.price if dxy_data else None,
    )

    return MarketConditionsResponse(
        sp500={
            "price": sp500_data.price if sp500_data else None,
            "change_pct": None,  # Would need historical data
        },
        vix={
            "price": vix_data.price if vix_data else None,
            "level": None,
        },
        tnx={
            "yield": tnx_data.price if tnx_data else None,
        },
        dxy={
            "price": dxy_data.price if dxy_data else None,
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
