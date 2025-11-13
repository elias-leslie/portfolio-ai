"""Market sentiment scoring and health calculation.

This module provides functions for calculating market health scores based on
various market indicators (VIX, S&P 500, Treasury yields, Dollar Index).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# Response models for sentiment calculations
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


def calculate_vix_score(vix_price: float, timestamp: str | None) -> ComponentScore:
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


def calculate_sp500_score(sp500_price: float, timestamp: str | None) -> ComponentScore:
    """Calculate S&P 500 level component score.

    Thresholds updated for 2025 market levels (current S&P ~6000-6800).
    Based on historical ranges and current market environment.

    Note: Consider future enhancement using percentile-based scoring
    with 252-day rolling window for dynamic threshold adjustment.
    """
    # Normalize around 6000-6800 range (2025 levels)
    if sp500_price > 6800:
        score, signal, interp = 75, "Bullish", "Strong market levels"
    elif sp500_price > 6400:
        score, signal, interp = 60, "Bullish", "Healthy market levels"
    elif sp500_price > 6000:
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


def calculate_tnx_score(tnx_yield: float, timestamp: str | None) -> ComponentScore:
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


def calculate_dxy_score(dxy_price: float, timestamp: str | None) -> ComponentScore:
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


def calculate_sector_scores(
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
        components.append(calculate_vix_score(vix_price, current_timestamp))

    if sp500_price is not None:
        components.append(calculate_sp500_score(sp500_price, current_timestamp))

    if tnx_yield is not None:
        components.append(calculate_tnx_score(tnx_yield, current_timestamp))

    if dxy_price is not None:
        components.append(calculate_dxy_score(dxy_price, current_timestamp))

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
    sectors = calculate_sector_scores(sector_data) if sector_data else []

    return MarketHealthScore(
        overall_score=overall_score,
        overall_label=label,
        components=components,
        sectors=sectors,
        last_updated=datetime.utcnow().isoformat(),
    )
