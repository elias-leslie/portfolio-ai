"""
Backtesting Framework - Phase A MVP

Simple event replay backtest engine that validates trading strategies using historical data.

Key Components:
- replay.py: Event-driven date loop replay engine
- strategies.py: Strategy interface + SignalStrategy (wraps signal_classifier.py)
- metrics.py: Performance calculations (Sharpe, drawdown, win rate)
- storage.py: Database operations for backtest_runs/trades/equity tables
- models.py: Pydantic models for API/DB serialization

Architecture Principles:
- Reuse 60% existing code (signal_classifier, indicators, performance metrics)
- Simple date loop (no complex event bus for MVP)
- Single-symbol backtests (no portfolio correlation effects)
- Use closing prices only (no slippage modeling)
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
    "StrategyConfig",
]
