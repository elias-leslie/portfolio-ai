"""Fear & Greed Index data models."""

from __future__ import annotations

from datetime import date as date_type
from typing import Literal

from pydantic import BaseModel, Field


class FearGreedReading(BaseModel):
    """Fear & Greed Index reading for a single date."""

    date: date_type = Field(..., description="Date of the reading")
    score: float = Field(
        ..., ge=0, le=100, description="Fear & Greed score (0=Extreme Fear, 100=Extreme Greed)"
    )
    label: Literal["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"] = Field(
        ..., description="Regime label based on score"
    )
    previous_score: float | None = Field(None, description="Previous trading day's score")
    score_change: float | None = Field(
        None, description="Change from previous score (positive = trending toward greed)"
    )
    signal_count: int = Field(default=5, description="Number of signals used in calculation")


class FearGreedComponent(BaseModel):
    """Component percentile breakdown for Fear & Greed Index."""

    date: date_type = Field(..., description="Date of the components")
    vix_pct: int | None = Field(
        None, ge=0, le=100, description="VIX percentile (inverted: low VIX = greed)"
    )
    momentum_pct: int | None = Field(
        None, ge=0, le=100, description="Momentum percentile (SPY vs SMA_200)"
    )
    rsi_pct: int | None = Field(
        None, ge=0, le=100, description="RSI percentile (high = overbought = greed)"
    )
    pcr_pct: int | None = Field(
        None, ge=0, le=100, description="Put/Call ratio percentile (inverted: low = greed)"
    )
    credit_pct: int | None = Field(
        None, ge=0, le=100, description="Credit spread percentile (inverted: low spread = greed)"
    )
    window_days: int = Field(default=252, description="Lookback window for percentile calculation")


class FearGreedResponse(BaseModel):
    """Complete Fear & Greed Index response with optional components."""

    reading: FearGreedReading = Field(..., description="Fear & Greed reading")
    components: FearGreedComponent | None = Field(
        None, description="Component breakdown (optional)"
    )
