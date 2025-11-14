"""
Pydantic models for backtesting framework.

Data Models:
- BacktestRun: Backtest execution metadata and results
- BacktestTrade: Individual trade entry/exit details
- BacktestEquity: Daily equity curve snapshots
- BacktestResult: Complete backtest summary for API responses
- StrategyConfig: Strategy configuration parameters
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrategyConfig(BaseModel):
    """Configuration for signal-based strategy.

    Phase A MVP: Simple configuration for SignalStrategy.
    Phase B: Expand for custom strategies with optimization parameters.
    """

    model_config = ConfigDict(frozen=True)

    strategy_name: Literal["signal_classifier"] = "signal_classifier"
    min_signal_strength: int = Field(default=7, ge=1, le=10)
    position_sizing_method: Literal["fixed_dollars", "fixed_shares"] = "fixed_dollars"
    position_size_value: Decimal = Field(default=Decimal("10000.00"), gt=0)
    max_holding_days: int = Field(default=60, gt=0)
    stop_loss_atr_multiplier: Decimal = Field(default=Decimal("2.0"), gt=0)
    use_trailing_stop: bool = False  # Phase B feature


class BacktestRun(BaseModel):
    """Backtest execution metadata and final results.

    Maps to backtest_runs table.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str  # UUID
    strategy_name: str  # e.g., "signal_classifier"
    symbol: str  # Single symbol for Phase A MVP
    start_date: date
    end_date: date
    initial_capital: Decimal
    final_equity: Decimal | None = None  # Null until backtest completes
    total_return_pct: Decimal | None = None
    sharpe_ratio: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    win_rate: Decimal | None = None
    num_trades: int | None = None
    profit_factor: Decimal | None = None  # Sum(wins) / Sum(losses)
    status: Literal["pending", "running", "completed", "failed"] = "pending"
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class BacktestTrade(BaseModel):
    """Individual trade entry/exit details.

    Maps to backtest_trades table.
    Reuses idea_outcomes schema patterns.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str  # UUID
    run_id: str  # Foreign key to backtest_runs
    symbol: str
    entry_date: date
    entry_price: Decimal
    exit_date: date | None = None  # Null if position still open at end of backtest
    exit_price: Decimal | None = None
    shares: int
    pnl: Decimal | None = None  # Profit/loss in dollars
    pnl_pct: Decimal | None = None  # Profit/loss percentage
    exit_reason: Literal["target", "stop", "signal", "time", "eod"] | None = None
    max_favorable_pct: Decimal = Decimal("0.0")  # Best return during trade
    max_adverse_pct: Decimal = Decimal("0.0")  # Worst return during trade
    created_at: datetime


class BacktestEquity(BaseModel):
    """Daily equity curve snapshot.

    Maps to backtest_equity table.
    Used for drawdown calculation and visualization.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str  # UUID
    run_id: str  # Foreign key to backtest_runs
    date: date
    equity: Decimal  # Total portfolio value (cash + positions)
    cash: Decimal
    position_value: Decimal  # Market value of open positions
    drawdown_pct: Decimal  # Current drawdown from peak equity
    created_at: datetime


class BacktestResult(BaseModel):
    """Complete backtest summary for API responses.

    Aggregates run + metrics + trades + equity curve.
    """

    model_config = ConfigDict(from_attributes=True)

    run: BacktestRun
    trades: list[BacktestTrade] = Field(default_factory=list)
    equity_curve: list[BacktestEquity] = Field(default_factory=list)

    # Additional computed metrics (not in DB)
    avg_win: Decimal | None = None
    avg_loss: Decimal | None = None
    win_loss_ratio: Decimal | None = None
    num_wins: int = 0
    num_losses: int = 0
    total_days: int = 0
