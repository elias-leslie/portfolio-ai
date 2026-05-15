"""Data models for unified market intelligence API.

Combines Market Health + Fear & Greed + Narrative into single response.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.market.sentiment import MarketHealthScore


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
    context: dict[str, Any] | None = Field(
        None, description="Optional historical context (trend, percentiles, etc.)"
    )


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


class FearGreedScore(BaseModel):
    """Fear & Greed Index scoring from 5 signals with staleness tracking and 7-day trend."""

    score: int = Field(..., ge=0, le=100, description="Fear & Greed score 0-100")
    label: str = Field(..., description="Extreme Fear | Fear | Neutral | Greed | Extreme Greed")
    score_change: float | None = Field(None, description="Change from previous day")
    signal_count: int = Field(..., description="Number of signals used (4-5)")
    last_updated: str = Field(..., description="Last update timestamp")
    is_stale: bool = Field(False, description="True if data is >2 days old")
    age_days: int = Field(0, description="Age of data in days")
    trend: Literal["up", "down", "flat"] | None = Field(
        None, description="7-day trend: up (more greedy), down (more fearful), flat (unchanged)"
    )
    trend_change: int | None = Field(None, description="Point change over 7 days")


class MarketTrendsResponse(BaseModel):
    """Market trends response with historical data for sparkline charts."""

    dates: list[str] = Field(..., description="List of dates (ISO 8601 format)")
    fear_greed_scores: list[float] = Field(..., description="Historical Fear & Greed scores")
    market_health_scores: list[float] = Field(
        ..., description="Historical Market Health scores (empty if not available)"
    )


class OptionsActivityMetrics(BaseModel):
    """Options market positioning metrics from CBOE Most Active."""

    near_term_pct: float = Field(..., description="% of top 25 options expiring ≤30 days")
    near_term_signal: str = Field(..., description="High | Normal | Low")
    concentration_pct: float = Field(..., description="% of volume in top 5 contracts")
    concentration_signal: str = Field(..., description="Focused | Balanced | Dispersed")
    top_sectors: list[dict[str, Any]] = Field(
        ..., description="Top 3 sectors by options activity weight"
    )
    last_updated: str = Field(..., description="Last update timestamp (ISO 8601)")


class MarketIntelligenceResponse(BaseModel):
    """Unified market intelligence response.

    Combines Market Health, Fear & Greed, Indicators, Sector Rotation, and Options Activity.
    """

    # Dual scoring
    market_health: MarketHealthScore = Field(..., description="Market Health score (4 indicators)")
    fear_greed: FearGreedScore = Field(..., description="Fear & Greed Index (5 signals)")

    # Key indicators (enriched with labels)
    indicators: dict[str, EnrichedIndicator] = Field(
        ..., description="5 key indicators: vix, sp500, tnx, dxy, putcall"
    )

    # Sector rotation (grouped)
    sector_rotation: SectorRotationSummary = Field(
        ..., description="Sectors grouped by performance"
    )

    # Options market positioning (from CBOE Most Active)
    options_activity: OptionsActivityMetrics | None = Field(
        None, description="Options activity metrics (aggregated from CBOE Most Active)"
    )

    # Metadata
    last_updated: str | None = Field(
        None,
        description=(
            "Last update timestamp (ISO 8601). Null when no underlying indicator carries"
            " a timestamp; the UI renders 'Update time unavailable' in that case."
        ),
    )
