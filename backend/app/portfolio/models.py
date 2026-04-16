"""Pydantic models for portfolio data structures.

This module defines data models for portfolio entities and analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class Account(BaseModel):
    """Portfolio account model."""

    id: str
    name: str
    account_type: Literal["IRA", "Taxable", "401k", "Roth", "HSA", "paper"]
    household_account_id: str | None = None
    cash_balance: float = 0.0
    initial_cash: float = 0.0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    @field_validator("household_account_id", mode="before")
    @classmethod
    def _normalize_household_account_id(cls, value: object) -> object:
        if isinstance(value, UUID):
            return str(value)
        return value


class Position(BaseModel):
    """Portfolio position model."""

    id: str
    account_id: str
    symbol: str
    shares: float
    cost_basis: float
    position_type: Literal["long", "short"]
    strategy_id: str | None = None  # Optional - links to strategies table
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PriceData(BaseModel):
    """Price and analytics data for a symbol."""

    symbol: str
    price: float
    beta: float | None = None
    volatility: float | None = None
    sector: str | None = None
    bid: float | None = None  # Best bid price (GAP-029)
    ask: float | None = None  # Best ask price (GAP-029)
    bid_size: int | None = None  # Size at bid
    ask_size: int | None = None  # Size at ask
    cached_at: datetime = Field(default_factory=datetime.now)
    source: str = "yfinance"
    error: str | None = None

    @property
    def spread(self) -> float | None:
        """Calculate bid-ask spread."""
        if self.bid is not None and self.ask is not None:
            return self.ask - self.bid
        return None

    @property
    def spread_pct(self) -> float | None:
        """Calculate spread as percentage of mid-price."""
        if self.bid is not None and self.ask is not None and self.bid > 0:
            mid = (self.bid + self.ask) / 2
            return ((self.ask - self.bid) / mid) * 100 if mid > 0 else None
        return None


class PortfolioValue(BaseModel):
    """Portfolio valuation metrics."""

    total_value: float
    total_cost_basis: float
    total_gain: float
    total_gain_pct: float


class ConcentrationMetrics(BaseModel):
    """Portfolio concentration risk metrics."""

    top_holding_pct: float
    top_3_pct: float
    top_10_pct: float
    herfindahl_index: float
    method: Literal["line_item", "lookthrough"] = "line_item"
    top_holding_name: str | None = None
    vehicle_top_holding_pct: float = 0.0
    vehicle_top_3_pct: float = 0.0
    vehicle_top_10_pct: float = 0.0
    vehicle_herfindahl_index: float = 0.0
    vehicle_top_holding_name: str | None = None
    lookthrough_coverage_pct: float = 0.0


class PositionPerformance(BaseModel):
    """Performance data for a single position."""

    symbol: str
    gain_pct: float
    gain_amount: float
    current_value: float
    weight_pct: float


class RiskProfile(BaseModel):
    """Portfolio risk profile assessment."""

    level: Literal["Conservative", "Moderate", "Aggressive", "Very Aggressive"]
    score: float  # 0-100 scale
    factors: dict[str, str] = Field(default_factory=dict)


class DiversificationScore(BaseModel):
    """Portfolio diversification assessment."""

    score: float  # 0-100 scale (100 = perfectly diversified)
    level: Literal["Poor", "Fair", "Good", "Excellent"]
    num_holdings: int
    num_sectors: int
    method: Literal["line_item", "lookthrough"] = "line_item"
    lookthrough_coverage_pct: float = 0.0


class PortfolioAnalytics(BaseModel):
    """Complete portfolio analytics."""

    portfolio_value: PortfolioValue
    portfolio_beta: float | None = None
    portfolio_volatility: float | None = None
    sharpe_ratio: float | None = None
    sector_exposure: dict[str, float] = Field(default_factory=dict)
    concentration_metrics: ConcentrationMetrics
    risk_profile: RiskProfile | None = None
    diversification_score: DiversificationScore | None = None
    top_performers: list[PositionPerformance] = Field(default_factory=list)
    bottom_performers: list[PositionPerformance] = Field(default_factory=list)
    num_positions: int
    num_symbols: int
