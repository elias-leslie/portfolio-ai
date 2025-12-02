"""
Backtesting Framework - Phase A MVP

Simple event replay backtest engine that validates trading strategies using historical data.

Key Components:
- replay.py: Event-driven date loop replay engine
- strategies.py: Strategy interface + SignalStrategy (wraps signal_classifier.py)
- metrics.py: Performance calculations (Sharpe, drawdown, win rate)
- storage.py: Database operations for backtest_runs/trades/equity tables
- models.py: Pydantic models for API/DB serialization
- costs.py: Slippage and commission modeling for realistic P&L

Architecture Principles:
- Reuse 60% existing code (signal_classifier, indicators, performance metrics)
- Simple date loop (no complex event bus for MVP)
- Single-symbol backtests (no portfolio correlation effects)
- Realistic cost modeling (slippage + commissions)
- Store all results in DB for agent access

Phase A Limitations:
- No walk-forward validation or parameter optimization
- No benchmark comparison (SPY buy-and-hold)
- No frontend visualization (API only)
- Technical indicators only (no news sentiment backfilling)

Dependencies:
- Existing: signal_classifier.py, analytics/indicators.py, analytics_risk.py
- New: backtest_runs/trades/equity tables (migration required)
"""

from app.backtest.costs import (
    CommissionModel,
    SlippageModel,
    TradingCosts,
    apply_costs_to_trade,
    calculate_commission,
    calculate_slippage,
    calculate_trade_costs,
    get_default_costs,
    get_institutional_costs,
    get_zero_costs,
)
from app.backtest.models import (
    BacktestEquity,
    BacktestResult,
    BacktestRun,
    BacktestTrade,
    StrategyConfig,
)

__all__ = [
    "BacktestEquity",
    "BacktestResult",
    "BacktestRun",
    "BacktestTrade",
    "CommissionModel",
    "SlippageModel",
    "StrategyConfig",
    "TradingCosts",
    "apply_costs_to_trade",
    "calculate_commission",
    "calculate_slippage",
    "calculate_trade_costs",
    "get_default_costs",
    "get_institutional_costs",
    "get_zero_costs",
]
