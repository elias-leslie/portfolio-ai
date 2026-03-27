"""TypedDict definitions for task result dictionaries.

Standardized result types for all scheduled and triggered tasks.
Replaces loose dict[str, Any] with properly typed result dictionaries.

This module re-exports all types from focused sub-modules:
- _types_base: TaskResultDict, build_task_success, build_task_failure
- _types_market: GapAnalysisResultDict, NewsProfilingResultDict,
                 FearGreedPipelineResultDict, FearGreedCalculationDict,
                 TechnicalIndicatorResultDict
- _types_strategy: WatchlistResultDict, StrategyMonitoringResultDict,
                   StrategyTriggerResultDict, build_strategy_success,
                   build_strategy_failure
"""

from __future__ import annotations

from app.tasks._types_base import (
    TaskResultDict,
    build_task_failure,
    build_task_success,
)
from app.tasks._types_market import (
    FearGreedCalculationDict,
    FearGreedPipelineResultDict,
    GapAnalysisResultDict,
    NewsProfilingResultDict,
    TechnicalIndicatorResultDict,
)
from app.tasks._types_strategy import (
    StrategyMonitoringResultDict,
    StrategyTriggerResultDict,
    WatchlistResultDict,
    build_strategy_failure,
    build_strategy_success,
)

__all__ = [
    "FearGreedCalculationDict",
    "FearGreedPipelineResultDict",
    "GapAnalysisResultDict",
    "NewsProfilingResultDict",
    "StrategyMonitoringResultDict",
    "StrategyTriggerResultDict",
    "TaskResultDict",
    "TechnicalIndicatorResultDict",
    "WatchlistResultDict",
    "build_strategy_failure",
    "build_strategy_success",
    "build_task_failure",
    "build_task_success",
]
