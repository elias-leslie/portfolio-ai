"""Background tasks for asynchronous execution.

This package contains task modules organized by function:
- agent_tasks: AI agent execution
- watchlist_tasks: Watchlist score refresh
- ingestion: Data ingestion tasks (OHLCV, analytics)
- indicators: Technical indicator calculations (package)

For backward compatibility, all tasks are re-exported from this __init__.py.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from . import (
        agent_tasks,
        artifact_tasks,
        cleanup,
        ingestion,
        maintenance_tasks,
        ml_training_tasks,
        news_profiling_tasks,
        news_tasks,
        reference_tasks,
        strategy,
        watchlist_tasks,
    )
    from .agent_tasks import run_discovery_agent, run_portfolio_analyzer
    from .indicators import (
        backfill_technical_indicators,
        calculate_fear_greed,
        update_technical_indicators,
    )
    from .ingestion import ingest_historical_ohlcv
    from .watchlist_tasks import (
        refresh_single_symbol_scores_task,
        refresh_watchlist_scores_task,
    )

_MODULE_EXPORTS = {
    "agent_tasks": ".agent_tasks",
    "artifact_tasks": ".artifact_tasks",
    "cleanup": ".cleanup",
    "ingestion": ".ingestion",
    "maintenance_tasks": ".maintenance_tasks",
    "ml_training_tasks": ".ml_training_tasks",
    "news_profiling_tasks": ".news_profiling_tasks",
    "news_tasks": ".news_tasks",
    "reference_tasks": ".reference_tasks",
    "strategy": ".strategy",
    "watchlist_tasks": ".watchlist_tasks",
}

_ATTRIBUTE_EXPORTS = {
    "run_discovery_agent": (".agent_tasks", "run_discovery_agent"),
    "run_portfolio_analyzer": (".agent_tasks", "run_portfolio_analyzer"),
    "backfill_technical_indicators": (".indicators", "backfill_technical_indicators"),
    "calculate_fear_greed": (".indicators", "calculate_fear_greed"),
    "update_technical_indicators": (".indicators", "update_technical_indicators"),
    "ingest_historical_ohlcv": (".ingestion", "ingest_historical_ohlcv"),
    "refresh_single_symbol_scores_task": (
        ".watchlist_tasks",
        "refresh_single_symbol_scores_task",
    ),
    "refresh_watchlist_scores_task": (".watchlist_tasks", "refresh_watchlist_scores_task"),
}


def __getattr__(name: str) -> ModuleType | Any:
    """Lazily resolve task modules and re-exported task functions."""
    module_path = _MODULE_EXPORTS.get(name)
    if module_path is not None:
        module = import_module(module_path, __name__)
        globals()[name] = module
        return module

    export = _ATTRIBUTE_EXPORTS.get(name)
    if export is not None:
        module_name, attribute_name = export
        value = getattr(import_module(module_name, __name__), attribute_name)
        globals()[name] = value
        return value

    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)

__all__ = [
    # Modules
    "agent_tasks",
    "artifact_tasks",
    # Individual tasks (backward compatibility)
    "backfill_technical_indicators",
    "calculate_fear_greed",
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
    "strategy",
    "update_technical_indicators",
    "watchlist_tasks",
]
