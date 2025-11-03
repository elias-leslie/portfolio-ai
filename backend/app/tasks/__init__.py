"""Celery tasks for background execution.

This package contains task modules organized by function:
- agent_tasks: AI agent execution and paper trading
- watchlist_tasks: Watchlist score refresh
- data_ingestion_tasks: Historical OHLCV data ingestion
- indicator_tasks: Technical indicator calculations

For backward compatibility, all tasks are re-exported from this __init__.py.
"""

from __future__ import annotations

# Agent and paper trading tasks
from .agent_tasks import (
    run_discovery_agent,
    run_portfolio_analyzer,
    update_paper_trades_task,
)

# Data ingestion tasks
from .data_ingestion_tasks import ingest_historical_ohlcv

# Indicator tasks
from .indicator_tasks import update_technical_indicators

# Watchlist tasks
from .watchlist_tasks import refresh_watchlist_scores_task

__all__ = [
    "ingest_historical_ohlcv",
    "refresh_watchlist_scores_task",
    "run_discovery_agent",
    "run_portfolio_analyzer",
    "update_paper_trades_task",
    "update_technical_indicators",
]
