"""Pydantic models for trade recommendations."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TradeRecommendation(BaseModel):
    """Single trade recommendation."""

    symbol: str
    strategy_id: str
    strategy_name: str
    strategy_type: str
    signal_strength: int = Field(ge=0, le=10)
    signal_type: Literal["BUY", "SELL", "HOLD"]
    signal_reasons: list[str]
    entry_price: float  # Price when signal was generated
    current_price: float  # Real-time current price
    price_change_pct: float  # % change since signal
    signal_status: Literal["valid", "better_entry", "caution", "invalidated"]
    stop_loss: float
    target_price: float
    position_size_dollars: float
    position_size_shares: int
    risk_reward_ratio: float
    expected_sharpe: float | None
    signal_date: str
    generated_at: str | None
    validation_type: Literal["thesis", "backtest", "both"] = Field(
        ..., description="Type of validation (thesis, backtest, or both)"
    )


class RecommendationsResponse(BaseModel):
    """Response containing trade recommendations."""

    recommendations: list[TradeRecommendation]
    total: int
    summary: dict[str, Any]
