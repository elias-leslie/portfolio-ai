"""TypedDict definitions for task result dictionaries.

Standardized result types for all scheduled and triggered tasks.
Replaces loose dict[str, Any] with properly typed result dictionaries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict


class TaskResultDict(TypedDict, total=False):
    """Standard task result dictionary returned by most tasks.

    Fields:
        status: Task status ("success", "error", "skipped", "completed", "insufficient_data")
        message: Human-readable status message
        data: Metadata about the task result
        errors: List of error messages (if any)
        timestamp: ISO format timestamp of task completion
        error: Error message (alternative field for backward compatibility)
    """

    status: str
    message: str
    data: dict[str, int | float | str | list[object] | None]
    errors: list[str]
    timestamp: str
    error: str


class GapAnalysisResultDict(TaskResultDict, total=False):
    """Result from gap analysis tasks (analyze_trading_gaps, track_gap_trends, alert_critical_gaps)."""

    total_gaps: int
    p0_gaps: int
    p1_gaps: int
    p2_gaps: int
    p3_gaps: int
    avg_coverage_pct: float
    current_gaps: int
    current_coverage_pct: float
    delta_24h: dict[str, float | int]
    delta_30d: dict[str, float | int]
    trend: str
    alerts_created: int


class NewsProfilingResultDict(TaskResultDict, total=False):
    """Result from news source profiling task."""

    task_id: str
    vendors_profiled: int
    total_vendors: int
    duration_seconds: float
    window_start: str
    window_end: str
    reason: str
    elapsed_hours: float
    interval_hours: int
    metrics_deleted: int
    feedback_deleted: int


class FearGreedPipelineResultDict(TaskResultDict, total=False):
    """Result from fear & greed pipeline tasks."""

    task_id: str
    updates_count: int
    date_range: str
    success: bool
    vix_close: float
    spy_close: float
    spy_sma_200: float
    rsi_14: float
    hy_spread: float
    breadth_pct: float | None


class FearGreedCalculationDict(TaskResultDict, total=False):
    """Result from calculate_fear_greed task."""

    success: bool
    date: str
    score: int
    label: str
    score_change: int
    components: dict[str, int]


class TechnicalIndicatorResultDict(TaskResultDict, total=False):
    """Result from technical indicator calculation tasks."""

    success: int
    failed: int
    symbols_processed: int


class CapabilityResultDict(TaskResultDict, total=False):
    """Result from capability scanning and analysis tasks."""

    db_tables_scanned: int
    celery_tasks_scanned: int
    api_endpoints_scanned: int
    total_capabilities: int
    scan_duration_seconds: float
    insights_generated: int
    insights_saved: int
    analysis_duration_seconds: float
    features_scanned: int
    needs_review_count: int
    total_features: int
    passes_breakdown: dict[str, int]


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


# Task result builder functions


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


def build_task_success(
    message: str = "Task completed successfully",
    *,
    evaluated: int | None = None,
    generated: int | None = None,
    promoted: int | None = None,
    archived: int | None = None,
    evolved: int | None = None,
    details: dict[str, int | float | str | list[object] | None] | None = None,
) -> TaskResultDict:
    """Build a standardized success result dictionary.

    Note: For strategy monitoring tasks, prefer build_strategy_success()
    which uses the correct 'completed'/'failed' status values.

    Args:
        message: Human-readable status message
        evaluated: Number of items evaluated (optional)
        generated: Number of items generated (optional)
        promoted: Number of items promoted (optional)
        archived: Number of items archived (optional)
        evolved: Number of items evolved (optional)
        details: Additional metadata (optional)

    Returns:
        TaskResultDict with status="success" and provided fields
    """
    result: TaskResultDict = {
        "status": "success",
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }

    # Add optional numeric fields if provided
    data: dict[str, int | float | str | list[object] | None] = {}
    if evaluated is not None:
        data["evaluated"] = evaluated
    if generated is not None:
        data["generated"] = generated
    if promoted is not None:
        data["promoted"] = promoted
    if archived is not None:
        data["archived"] = archived
    if evolved is not None:
        data["evolved"] = evolved

    # Merge additional details if provided
    if details:
        data.update(details)

    if data:
        result["data"] = data

    return result


def build_task_failure(error: Exception) -> TaskResultDict:
    """Build a standardized failure result dictionary.

    Note: For strategy monitoring tasks, prefer build_strategy_failure()
    which uses 'failed' status instead of 'error'.

    Args:
        error: Exception that caused the task failure

    Returns:
        TaskResultDict with status="error" and error message
    """
    return {
        "status": "error",
        "message": "Task failed",
        "error": str(error),
        "timestamp": datetime.now(UTC).isoformat(),
    }
