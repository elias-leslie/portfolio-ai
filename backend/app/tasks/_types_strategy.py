"""Strategy task result TypedDict definitions and builder functions.

Typed result dictionaries and builder helpers for watchlist, strategy
monitoring, and strategy trigger tasks.
"""

from __future__ import annotations

from typing import TypedDict

from app.tasks._types_base import TaskResultDict


class WatchlistResultDict(TaskResultDict, total=False):
    """Result from watchlist refresh task."""

    task_id: str
    skipped: bool
    reason: str
    minutes_since_refresh: float
    refresh_interval_minutes: int
    duration_seconds: float
    items_refreshed: int
    scores_updated: int
    processed: int
    failed: int
    markets_open: bool


class StrategyMonitoringResultDict(TypedDict, total=False):
    """Result from strategy monitoring and evaluation tasks.

    Uses 'completed'/'failed' status to match existing task contracts.
    """

    status: str  # "completed" or "failed"
    strategies_evaluated: int
    strategies_archived: int
    strategies_promoted: int
    strategies_generated: int
    strategies_evolved: int
    symbols_evaluated: int
    details: list[str]
    error: str


class StrategyTriggerResultDict(TypedDict, total=False):
    """Result from strategy trigger tasks (trigger_strategies_for_top_watchlist, etc.)."""

    status: str  # "completed", "failed", "rate_limited", "rejected"
    generated: int
    checked: int
    reason: str
    details: list[str]
    seed_id: str
    strategy_id: str
    symbol: str
    message: str
    error: str


def build_strategy_success(
    *,
    strategies_evaluated: int = 0,
    strategies_archived: int = 0,
    strategies_promoted: int = 0,
    strategies_generated: int = 0,
    strategies_evolved: int = 0,
    symbols_evaluated: int = 0,
    details: list[str] | None = None,
) -> StrategyMonitoringResultDict:
    """Build a standardized strategy monitoring success result.

    Args:
        strategies_evaluated: Number of strategies evaluated
        strategies_archived: Number of strategies archived
        strategies_promoted: Number of strategies promoted
        strategies_generated: Number of strategies generated
        strategies_evolved: Number of strategies evolved
        symbols_evaluated: Number of symbols evaluated
        details: List of result messages

    Returns:
        StrategyMonitoringResultDict with status="completed"
    """
    result: StrategyMonitoringResultDict = {"status": "completed"}
    if strategies_evaluated:
        result["strategies_evaluated"] = strategies_evaluated
    if strategies_archived:
        result["strategies_archived"] = strategies_archived
    if strategies_promoted:
        result["strategies_promoted"] = strategies_promoted
    if strategies_generated:
        result["strategies_generated"] = strategies_generated
    if strategies_evolved:
        result["strategies_evolved"] = strategies_evolved
    if symbols_evaluated:
        result["symbols_evaluated"] = symbols_evaluated
    if details is not None:
        result["details"] = details
    return result


def build_strategy_failure(error: Exception | str) -> StrategyMonitoringResultDict:
    """Build a standardized strategy monitoring failure result.

    Args:
        error: Exception or error message

    Returns:
        StrategyMonitoringResultDict with status="failed"
    """
    return {
        "status": "failed",
        "error": str(error),
    }
