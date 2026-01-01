"""Celery tasks for background execution.

This package contains task modules organized by function:
- agent_tasks: AI agent execution and paper trading
- watchlist_tasks: Watchlist score refresh
- ingestion: Data ingestion tasks (OHLCV, analytics)
- indicators: Technical indicator calculations (package)

For backward compatibility, all tasks are re-exported from this __init__.py.
Additionally, modules are exposed for Celery task registration.
"""

from __future__ import annotations

# Import task modules (needed for Celery task registration in celery_app.py)
from . import (
    agent_tasks,
    artifact_tasks,  # Evidence capture cleanup
    capability_tasks,
    cleanup,  # Cleanup tasks (log rotation, temp files, artifacts, disk monitoring)
    # file_scan removed - use SummitFlow for file browsing
    ingestion,
    maintenance_tasks,
    ml_training_tasks,
    news_profiling_tasks,
    news_tasks,
    reference_tasks,
    strategy_monitoring_tasks,
    watchlist_tasks,
    workflow_tasks,
)

# For backward compatibility, also import specific tasks
from .agent_tasks import (
    run_discovery_agent,
    run_portfolio_analyzer,
    update_paper_trades_task,
)
from .indicators import (
    backfill_technical_indicators,
    calculate_fear_greed,
    update_technical_indicators,
)
from .ingestion import ingest_historical_ohlcv
from .watchlist_tasks import refresh_single_symbol_scores_task, refresh_watchlist_scores_task

__all__ = [
    # Modules
    "agent_tasks",
    "artifact_tasks",
    # Individual tasks (backward compatibility)
    "backfill_technical_indicators",
    "calculate_fear_greed",
    "capability_tasks",
    "cleanup",
    # file_scan removed - use SummitFlow for file browsing
    "ingest_historical_ohlcv",
    "ingestion",
    "maintenance_tasks",
    "ml_training_tasks",
    "news_profiling_tasks",
    "news_tasks",
    "reference_tasks",
    "refresh_single_symbol_scores_task",
    "refresh_watchlist_scores_task",
    "run_discovery_agent",
    "run_portfolio_analyzer",
    "strategy_monitoring_tasks",
    "update_paper_trades_task",
    "update_technical_indicators",
    "watchlist_tasks",
    "workflow_tasks",
]
