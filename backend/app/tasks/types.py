"""TypedDict definitions for Celery task result dictionaries.

Standardized result types for all scheduled and triggered tasks.
Replaces loose dict[str, Any] with properly typed result dictionaries.
"""

from __future__ import annotations

from typing import TypedDict


class TaskResultDict(TypedDict, total=False):
    """Standard task result dictionary returned by most Celery tasks.

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
    tickers_processed: int


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
