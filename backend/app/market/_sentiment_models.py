"""Pydantic models for market sentiment scoring."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
