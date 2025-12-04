"""Type definitions for analytics module.

This module defines TypedDict models for analytics data structures,
providing proper type hints and eliminating dict[str, Any] usage.
"""

from datetime import date, datetime
from typing import TypedDict


class TradeRecordDict(TypedDict, total=False):
    """Database trade record from idea_outcomes table."""

    idea_id: str
    symbol: str
    idea_type: str
    entry_price: float
    entry_date: date | None
    exit_price: float | None
    exit_date: date | None
    status: str
    realized_return_pct: float | None
    current_return_pct: float
    holding_days: int
    target_price: float | None
    stop_loss_price: float | None
    current_price: float
    max_favorable_pct: float
    max_adverse_pct: float
    created_at: datetime  # datetime from database
    updated_at: datetime  # datetime from database
    agent_run_id: str
    agent_type: str
    started_at: datetime  # datetime from database
    strategy_id: str | None  # Optional - links to strategies table
    backtest_run_id: str | None  # Optional - links to backtest that validated trade


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


class TradeDict(TypedDict, total=False):
    """Trade summary with key details (for best/worst trade display)."""

    symbol: str
    entry_date: str | None
    exit_date: str | None
    holding_days: int


class IdeaDetailsDict(TypedDict, total=False):
    """Agent idea details from database."""

    id: str
    agent_run_id: str
    idea_type: str
    title: str
    thesis: str
    action: str | None
    created_at: datetime  # datetime from database


class PerformanceMetricsDict(TypedDict, total=False):
    """Performance metrics calculated from trades."""

    win_rate: float
    average_return: float
    average_winner: float
    average_loser: float
    win_loss_ratio: float | None
    total_ideas: int
    open_ideas: int
    closed_ideas: int
    best_trade: dict[str, object] | None
    worst_trade: dict[str, object] | None


class AgentPerformanceDict(TypedDict):
    """Complete agent performance summary."""

    agent_type: str
    period_days: int
    metrics: PerformanceMetricsDict


class AgentPerformanceSummaryDict(TypedDict):
    """Summary of all agent performance data."""

    agents: list[dict[str, float | str | int]]
    period_days: int
    total_agents: int


class TransactionDict(TypedDict, total=False):
    """Transaction record from paper_trade_transactions table."""

    id: str | int
    trade_id: str
    transaction_type: str
    symbol: str
    shares: int
    price: float
    amount: float
    cash_before: float
    cash_after: float
    timestamp: datetime  # datetime from database
    notes: str | None


class PaperTradeStatsDict(TypedDict):
    """Statistics from paper trade updates."""

    trades_updated: int
    trades_closed: int
    target_hits: int
    stop_hits: int
    expired: int
