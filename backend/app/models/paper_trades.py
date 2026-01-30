"""Paper Trading API models.

Pydantic models for paper trading REST API endpoints.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PaperTradeResponse(BaseModel):
    """Response model for a single paper trade."""

    idea_id: str
    agent_run_id: str
    symbol: str
    idea_type: Literal["buy", "sell"]
    shares: int | None = None
    entry_price: float | None = None
    entry_amount: float | None = None
    entry_date: str | None = None
    target_price: float | None = None
    stop_loss_price: float | None = None
    current_price: float | None = None
    current_return_pct: float | None = None
    status: str
    exit_price: float | None = None
    exit_date: str | None = None
    exit_reason: str | None = None
    realized_return_pct: float | None = None
    holding_days: int | None = None
    max_favorable_pct: float | None = None
    max_adverse_pct: float | None = None
    # AI reasoning fields
    thesis: str | None = None
    confidence_score: float | None = None
    risk_level: str | None = None
    # Agent approval details
    workflow_id: str | None = None
    strategy_agent_approved: bool | None = None
    risk_agent_approved: bool | None = None
    backtest_sharpe: float | None = None
    backtest_win_rate: float | None = None
    backtest_max_drawdown: float | None = None
    # Strategy linkage
    strategy_id: str | None = None


class PaperTradesListResponse(BaseModel):
    """Response model for list of paper trades."""

    trades: list[PaperTradeResponse]
    total_count: int


class PaperTradeSummaryResponse(BaseModel):
    """Response model for paper trading summary statistics."""

    total_open: int
    total_closed: int
    win_rate: float
    avg_return_pct: float
    total_pnl_pct: float
    best_trade_pct: float | None = None
    worst_trade_pct: float | None = None
    # Paper trading account balances
    cash_balance: float | None = None
    starting_balance: float | None = None
    positions_value: float | None = None
    total_portfolio_value: float | None = None


class CloseTradeRequest(BaseModel):
    """Request model for manually closing a paper trade."""

    exit_price: float | None = Field(
        None, description="Optional exit price (uses current if not provided)"
    )
    exit_reason: str = Field(default="manual", description="Reason for closing (default: manual)")


class CloseTradeResponse(BaseModel):
    """Response model for close trade operation."""

    status: str
    trade_id: str
    symbol: str
    exit_price: float
    exit_date: str
    realized_return_pct: float
    message: str


class ResetAccountRequest(BaseModel):
    """Request model for resetting paper trading account."""

    new_starting_balance: float | None = Field(
        None, description="New starting balance (uses current initial_cash if not provided)"
    )
    close_open_trades: bool = Field(
        default=True, description="Whether to close all open trades before reset"
    )


class ResetAccountResponse(BaseModel):
    """Response model for reset account operation."""

    status: str
    previous_balance: float
    new_balance: float
    trades_closed: int
    message: str


class UpdateSettingsRequest(BaseModel):
    """Request model for updating paper trading settings."""

    starting_balance: float = Field(..., gt=0, description="New starting balance amount")


class UpdateSettingsResponse(BaseModel):
    """Response model for update settings operation."""

    status: str
    starting_balance: float
    cash_balance: float
    message: str
