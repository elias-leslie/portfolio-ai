"""Type definitions for analytics module.

This module defines TypedDict models for analytics data structures,
providing proper type hints and eliminating dict[str, Any] usage.
"""

from datetime import date, datetime
from typing import TypedDict


class PaperTradeDict(TypedDict, total=False):
    """Paper trade record from database."""

    idea_id: str
    agent_run_id: str
    symbol: str
    idea_type: str
    entry_price: float
    entry_date: date
    target_price: float | None
    stop_loss_price: float | None
    current_price: float
    current_return_pct: float
    status: str
    exit_price: float | None
    exit_date: date | None
    exit_reason: str | None
    realized_return_pct: float | None
    holding_days: int
    max_favorable_pct: float
    max_adverse_pct: float
    created_at: datetime  # datetime from database
    updated_at: datetime  # datetime from database
    strategy_id: str | None  # Optional - links to strategies table
    # Backtest metrics from strategy
    backtest_sharpe: float | None
    backtest_win_rate: float | None
    backtest_max_drawdown: float | None
    backtest_run_id: str | None  # Links to backtest that validated this trade
    # Position sizing (optional - for strategy-based paper trades)
    shares: int | None
    entry_amount: float | None
