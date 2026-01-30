"""Health status calculation for Celery scanner."""

from __future__ import annotations

from typing import Any


def calculate_celery_health_status(
    populates_tables: list[str],
    depends_on_tasks: list[str],
    called_by: list[str],
    last_run_at: Any | None,
    success_rate_pct: int | None,
    schedule_interval_seconds: int | None,
) -> str:
    """Calculate health status for Celery task.

    Args:
        populates_tables: Tables this task populates
        depends_on_tasks: Tasks this task depends on
        called_by: Files/tasks that call this task
        last_run_at: Last execution timestamp
        success_rate_pct: Success rate over last 7 days
        schedule_interval_seconds: Schedule interval in seconds

    Returns:
        Health status: "active", "orphaned", "legacy", or "suspect"

    Celery health logic:
    - active: Has callers (other code calls this task) OR healthy execution
    - orphaned: Not in schedule AND no populates AND no depends_on AND no callers
    - legacy: Never run (last_run_at=None) OR success_rate=0% consistently
    - suspect: Low success rate (<50%) OR irregular execution
    """
    has_zero_success = success_rate_pct is not None and success_rate_pct == 0

    # If other code calls this task, it's active (suspect if failing)
    if called_by:
        return "suspect" if has_zero_success else "active"

    # Orphaned: Not scheduled and no dependencies and no callers
    is_isolated = (
        schedule_interval_seconds is None and not populates_tables and not depends_on_tasks
    )
    if is_isolated:
        return "orphaned"

    # Legacy: Never executed OR complete failure (0% success rate)
    if last_run_at is None or has_zero_success:
        return "legacy"

    # Suspect: Low success rate (<50%)
    has_low_success = success_rate_pct is not None and success_rate_pct < 50
    return "suspect" if has_low_success else "active"
