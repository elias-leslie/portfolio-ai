"""Portfolio API request/response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# Request models
class AccountCreate(BaseModel):
    """Request model for creating an account."""

    name: str = Field(..., description="Account name")
    account_type: Literal["IRA", "Taxable", "401k", "Roth", "HSA", "paper"] = Field(
        ..., description="Account type"
    )


class PositionCreate(BaseModel):
    """Request model for creating/updating a position."""

    account_id: str = Field(..., description="Account ID")
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    shares: float = Field(..., description="Number of shares", gt=0)
    cost_basis: float = Field(..., description="Cost basis per share", gt=0)
    position_type: Literal["long", "short"] = Field(default="long", description="Position type")
    strategy_id: str | None = Field(
        default=None, description="Optional strategy ID to link this position to"
    )


# Response models
class AccountResponse(BaseModel):
    """Response model for account."""

    id: str
    name: str
    account_type: str
    created_at: str
    updated_at: str


class PositionResponse(BaseModel):
    """Response model for position."""

    id: str
    account_id: str
    symbol: str
    shares: float
    cost_basis: float
    position_type: str
    strategy_id: str | None = None
    strategy_name: str | None = None
    created_at: str
    updated_at: str
    current_price: float | None = None
    current_value: float | None = None
    gain: float | None = None
    gain_pct: float | None = None


class PortfolioResponse(BaseModel):
    """Response model for portfolio with positions and current values."""

    positions: list[PositionResponse]
    total_value: float
    total_cost_basis: float
    total_gain: float
    total_gain_pct: float


class PositionPerformanceResponse(BaseModel):
    """Response model for position performance."""

    symbol: str
    gain_pct: float
    gain_amount: float
    current_value: float
    weight_pct: float


class RiskProfileResponse(BaseModel):
    """Response model for risk profile."""

    level: str
    score: float
    factors: dict[str, str]


class DiversificationScoreResponse(BaseModel):
    """Response model for diversification score."""

    score: float
    level: str
    num_holdings: int
    num_sectors: int


class AnalyticsResponse(BaseModel):
    """Response model for portfolio analytics."""

    portfolio_value: dict[str, float]
    portfolio_beta: float | None
    portfolio_volatility: float | None
    sharpe_ratio: float | None
    sector_exposure: dict[str, float]
    concentration: dict[str, float]
    risk_profile: RiskProfileResponse | None
    diversification_score: DiversificationScoreResponse | None
    top_performers: list[PositionPerformanceResponse]
    bottom_performers: list[PositionPerformanceResponse]
    num_positions: int
    num_symbols: int
