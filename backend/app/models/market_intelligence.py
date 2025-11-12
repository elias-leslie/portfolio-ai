"""Data models for unified market intelligence API.

Combines Market Health + Fear & Greed + Narrative into single response.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EnrichedIndicator(BaseModel):
    """Market indicator enriched with plain-language labels."""

    value: float = Field(..., description="Current value")
    change_pct: float | None = Field(None, description="Daily change percentage")
    label: str = Field(..., description="Plain-language label (e.g., 'Market Volatility')")
    short_label: str = Field(..., description="Short label (e.g., 'Volatility')")
    tooltip: str = Field(..., description="Educational tooltip explaining the indicator")
    signal: str = Field(..., description="Bullish | Neutral | Bearish")
    emoji: str = Field(..., description="Visual indicator: 🟢 🟡 🔴")
    last_updated: str | None = Field(None, description="Last update timestamp (ISO 8601)")


class SectorInfo(BaseModel):
    """Sector performance information with plain-language labels."""

    symbol: str = Field(..., description="Sector ETF symbol (e.g., XLK)")
    name: str = Field(..., description="Plain-language name (e.g., 'Technology')")
    description: str = Field(..., description="What companies (e.g., 'Apple, Microsoft, NVIDIA')")
    price: float | None = Field(None, description="Current price")
    change_pct: float | None = Field(None, description="Daily change percentage")
    signal: str = Field(..., description="Leading | Neutral | Lagging")
    last_updated: str | None = Field(None, description="Last update timestamp")


class SectorRotationSummary(BaseModel):
    """Sector rotation summary grouped by performance."""

    leading: list[SectorInfo] = Field(..., description="Top performing sectors")
    neutral: list[SectorInfo] = Field(..., description="Middle performing sectors")
    lagging: list[SectorInfo] = Field(..., description="Worst performing sectors")
    leading_count: int = Field(..., description="Number of leading sectors")
    neutral_count: int = Field(..., description="Number of neutral sectors")
    lagging_count: int = Field(..., description="Number of lagging sectors")


class MarketHealthScore(BaseModel):
    """Market health scoring from 4 indicators."""

    overall_score: int = Field(..., ge=0, le=100, description="Overall health score 0-100")
    overall_label: str = Field(..., description="Very Bullish | Bullish | Neutral | Bearish | Extreme Fear")
    last_updated: str = Field(..., description="Last update timestamp")


class FearGreedScore(BaseModel):
    """Fear & Greed Index scoring from 5 signals."""

    score: int = Field(..., ge=0, le=100, description="Fear & Greed score 0-100")
    label: str = Field(..., description="Extreme Fear | Fear | Neutral | Greed | Extreme Greed")
    score_change: float | None = Field(None, description="Change from previous day")
    signal_count: int = Field(..., description="Number of signals used (4-5)")
    last_updated: str = Field(..., description="Last update timestamp")


class MarketIntelligenceResponse(BaseModel):
    """Unified market intelligence response.

    Combines Market Health, Fear & Greed, Narrative, Indicators, and Sector Rotation.
    """

    # Narrative (top of UI)
    narrative: str = Field(..., description="Plain-language actionable narrative (3-4 sentences)")

    # Dual scoring
    market_health: MarketHealthScore = Field(..., description="Market Health score (4 indicators)")
    fear_greed: FearGreedScore = Field(..., description="Fear & Greed Index (5 signals)")

    # Key indicators (enriched with labels)
    indicators: dict[str, EnrichedIndicator] = Field(
        ..., description="4 key indicators: vix, sp500, tnx, dxy"
    )

    # Sector rotation (grouped)
    sector_rotation: SectorRotationSummary = Field(..., description="Sectors grouped by performance")

    # Metadata
    last_updated: str = Field(..., description="Last update timestamp (ISO 8601)")
