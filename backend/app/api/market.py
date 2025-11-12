"""Market data API router."""

from __future__ import annotations

import datetime as dt
from datetime import datetime

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from app.market import narrative_generator, plain_language
from app.market.fear_greed_stub import get_fear_greed_score
from app.middleware.cache import cache_response
from app.models.market_intelligence import (
    EnrichedIndicator,
    FearGreedScore,
    MarketIntelligenceResponse,
    SectorInfo,
    SectorRotationSummary,
)
from app.models.market_intelligence import (
    MarketHealthScore as MarketHealthScoreResponse,
)
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
async def get_market_intelligence() -> MarketIntelligenceResponse:
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
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT as_of_date FROM fear_greed_daily ORDER BY as_of_date DESC LIMIT 1"
        )
        row = result.fetchone()
        if row and row[0]:
            # Convert date to datetime at market close (4:00 PM ET = 21:00 UTC)
            market_data_date = row[0]
            market_close_time = dt.datetime.combine(
                market_data_date, dt.time(21, 0, 0), tzinfo=dt.UTC
            )
            current_timestamp = market_close_time.isoformat()
        else:
            # Fallback to cache timestamp if no Fear & Greed data
            current_timestamp = (
                sp500_data.cached_at.isoformat()
                if sp500_data
                else datetime.utcnow().isoformat() + "Z"
            )

    # Fetch sector ETF data
    sector_symbols = ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU", "XLRE", "XLB", "XLC"]
    sector_price_data = price_fetcher.fetch_price_data(sector_symbols)

    # Query OHLCV data for previous close to calculate daily change %
    sector_data_list: list[tuple[str, float | None, float | None, str | None]] = []
    with storage.connection() as conn:
        for symbol in sector_symbols:
            current_price = sector_price_data.get(symbol)
            if not current_price:
                sector_data_list.append((symbol, None, None, None))
                continue

            # Get previous close from OHLCV data
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
                sector_timestamp = current_price.cached_at.isoformat()
                sector_data_list.append((symbol, current_price.price, change_pct, sector_timestamp))
            else:
                # No historical data, just use current price
                sector_timestamp = current_price.cached_at.isoformat()
                sector_data_list.append((symbol, current_price.price, None, sector_timestamp))

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

    # Group sectors into Leading/Neutral/Lagging
    sectors_with_change = [
        (symbol, price, change_pct, timestamp)
        for symbol, price, change_pct, timestamp in sector_data_list
        if change_pct is not None
    ]
    sectors_with_change.sort(key=lambda x: x[2] if x[2] is not None else -999, reverse=True)

    # Calculate thresholds (top 33%, middle 34%, bottom 33%)
    total_count = len(sectors_with_change)
    leading_cutoff = int(total_count * 0.33)
    lagging_start = int(total_count * 0.67)

    leading_sectors: list[SectorInfo] = []
    neutral_sectors: list[SectorInfo] = []
    lagging_sectors: list[SectorInfo] = []

    for idx, (symbol, price, change_pct, timestamp) in enumerate(sectors_with_change):
        sector_label = plain_language.get_sector_label(symbol)

        sector_info = SectorInfo(
            symbol=symbol,
            name=sector_label["name"],
            description=sector_label["description"],
            price=price,
            change_pct=change_pct,
            signal="Leading"
            if idx < leading_cutoff
            else ("Lagging" if idx >= lagging_start else "Neutral"),
            last_updated=timestamp,
        )

        if idx < leading_cutoff:
            leading_sectors.append(sector_info)
        elif idx >= lagging_start:
            lagging_sectors.append(sector_info)
        else:
            neutral_sectors.append(sector_info)

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

    # Enrich indicators with plain-language labels
    def _get_signal_emoji(signal: str) -> str:
        if signal == "Bullish":
            return "🟢"
        if signal == "Bearish":
            return "🔴"
        return "🟡"

    enriched_indicators: dict[str, EnrichedIndicator] = {}

    # VIX
    if vix_data:
        vix_label = plain_language.get_indicator_label("vix")
        vix_component = next((c for c in health_score_data.components if "VIX" in c.name), None)
        enriched_indicators["vix"] = EnrichedIndicator(
            value=vix_data.price,
            change_pct=None,
            label=vix_label["label"],
            short_label=vix_label["short"],
            tooltip=vix_label["tooltip"],
            signal=vix_component.signal if vix_component else "Neutral",
            emoji=_get_signal_emoji(vix_component.signal if vix_component else "Neutral"),
            last_updated=vix_data.cached_at.isoformat(),
        )

    # S&P 500
    if sp500_data:
        sp500_label = plain_language.get_indicator_label("sp500")
        sp500_component = next((c for c in health_score_data.components if "S&P" in c.name), None)
        enriched_indicators["sp500"] = EnrichedIndicator(
            value=sp500_data.price,
            change_pct=None,
            label=sp500_label["label"],
            short_label=sp500_label["short"],
            tooltip=sp500_label["tooltip"],
            signal=sp500_component.signal if sp500_component else "Neutral",
            emoji=_get_signal_emoji(sp500_component.signal if sp500_component else "Neutral"),
            last_updated=sp500_data.cached_at.isoformat(),
        )

    # 10Y Treasury
    if tnx_data:
        tnx_label = plain_language.get_indicator_label("tnx")
        tnx_component = next(
            (c for c in health_score_data.components if "Treasury" in c.name), None
        )
        enriched_indicators["tnx"] = EnrichedIndicator(
            value=tnx_data.price,
            change_pct=None,
            label=tnx_label["label"],
            short_label=tnx_label["short"],
            tooltip=tnx_label["tooltip"],
            signal=tnx_component.signal if tnx_component else "Neutral",
            emoji=_get_signal_emoji(tnx_component.signal if tnx_component else "Neutral"),
            last_updated=tnx_data.cached_at.isoformat(),
        )

    # Dollar
    if dxy_data:
        dxy_label = plain_language.get_indicator_label("dxy")
        dxy_component = next((c for c in health_score_data.components if "Dollar" in c.name), None)
        enriched_indicators["dxy"] = EnrichedIndicator(
            value=dxy_data.price,
            change_pct=None,
            label=dxy_label["label"],
            short_label=dxy_label["short"],
            tooltip=dxy_label["tooltip"],
            signal=dxy_component.signal if dxy_component else "Neutral",
            emoji=_get_signal_emoji(dxy_component.signal if dxy_component else "Neutral"),
            last_updated=dxy_data.cached_at.isoformat(),
        )

    # Build response
    return MarketIntelligenceResponse(
        narrative=narrative,
        market_health=MarketHealthScoreResponse(
            overall_score=health_score_data.overall_score,
            overall_label=health_score_data.overall_label,
            last_updated=health_score_data.last_updated,
        ),
        fear_greed=FearGreedScore(
            score=int(fg_reading.score),
            label=fg_reading.label,
            score_change=fg_reading.score_change,
            signal_count=fg_reading.signal_count,
            last_updated=fg_reading.date,
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
