"""Pydantic models for portfolio data structures.

This module defines data models for portfolio entities and analytics.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Account(BaseModel):
    """Portfolio account model."""

    id: str
    name: str
    account_type: Literal["IRA", "Taxable", "401k", "Roth", "HSA"]
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Position(BaseModel):
    """Portfolio position model."""

    id: str
    account_id: str
    symbol: str
    shares: float
    cost_basis: float
    position_type: Literal["long", "short"]
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class PriceData(BaseModel):
    """Price and analytics data for a symbol."""

    symbol: str
    price: float
    beta: float | None = None
    volatility: float | None = None
    sector: str | None = None
    cached_at: datetime = Field(default_factory=datetime.now)
    source: str = "yfinance"


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


class PortfolioAnalytics(BaseModel):
    """Complete portfolio analytics."""

    portfolio_value: PortfolioValue
    portfolio_beta: float | None = None
    portfolio_volatility: float | None = None
    sector_exposure: dict[str, float] = Field(default_factory=dict)
    concentration_metrics: ConcentrationMetrics
    num_positions: int
    num_symbols: int
