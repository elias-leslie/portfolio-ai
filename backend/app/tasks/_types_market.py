"""Market data task result TypedDict definitions.

Typed result dictionaries for gap analysis, news profiling,
fear & greed, and technical indicator tasks.
"""

from __future__ import annotations

from app.tasks._types_base import TaskResultDict


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
