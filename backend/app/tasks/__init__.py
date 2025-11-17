"""Celery tasks for background execution.

This package contains task modules organized by function:
- agent_tasks: AI agent execution and paper trading
- watchlist_tasks: Watchlist score refresh
- data_ingestion_tasks: Historical OHLCV data ingestion
- indicator_tasks: Technical indicator calculations

For backward compatibility, all tasks are re-exported from this __init__.py.
Additionally, modules are exposed for Celery task registration.
"""

from __future__ import annotations

# Import task modules (needed for Celery task registration in celery_app.py)
from . import (
    agent_tasks,
    capability_tasks,
    data_ingestion_tasks,
    indicator_tasks,
    log_cleanup_tasks,
    maintenance_tasks,
    ml_training_tasks,
    news_profiling_tasks,
    news_tasks,
    reference_tasks,
    watchlist_tasks,
    workflow_tasks,
)

# For backward compatibility, also import specific tasks
from .agent_tasks import (
    run_discovery_agent,
    run_portfolio_analyzer,
    update_paper_trades_task,
)
from .data_ingestion_tasks import ingest_historical_ohlcv
from .indicator_tasks import update_technical_indicators
from .watchlist_tasks import refresh_watchlist_scores_task

__all__ = [
    # Modules
    "agent_tasks",
    "capability_tasks",
    "data_ingestion_tasks",
    "indicator_tasks",
    "log_cleanup_tasks",
    "maintenance_tasks",
    "ml_training_tasks",
    "news_profiling_tasks",
    "news_tasks",
    "reference_tasks",
    "watchlist_tasks",
    "workflow_tasks",
    # Individual tasks (backward compatibility)
    "ingest_historical_ohlcv",
    "refresh_watchlist_scores_task",
    "run_discovery_agent",
    "run_portfolio_analyzer",
    "update_paper_trades_task",
    "update_technical_indicators",
]
