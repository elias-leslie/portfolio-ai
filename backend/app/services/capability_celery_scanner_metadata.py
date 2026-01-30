"""Task metadata retrieval for Celery scanner."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


def get_task_metadata(
    conn_mgr: ConnectionManager,
    task_path: str,
    track_success_rate: bool,
    lookback_days: int,
) -> tuple[Any | None, Any | None, int, int, int | None, int | None, int | None]:
    """Get task execution metadata from celery_taskmeta table.

    Args:
        conn_mgr: ConnectionManager instance
        task_path: Task import path
        track_success_rate: Whether to track success rates
        lookback_days: Number of days to look back for metrics

    Returns:
        Tuple of (last_run_at, next_run_at, success_count_7d, failure_count_7d,
                 success_rate_pct, avg_duration_ms, max_duration_ms)
    """
    if not track_success_rate:
        return None, None, 0, 0, None, None, None

    try:
        with conn_mgr.connection() as conn:
            # Check if celery_taskmeta table exists
            check_table = conn.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'celery_taskmeta'
                )
                """
            )
            row = check_table.fetchone()
            table_exists = row[0] if row else False

            if not table_exists:
                return None, None, 0, 0, None, None, None

            # Query last 7 days of task execution
            result = conn.execute(
                f"""
                SELECT
                    MAX(date_done) as last_run,
                    COUNT(*) FILTER (WHERE status = 'SUCCESS') as success_count,
                    COUNT(*) FILTER (WHERE status = 'FAILURE') as failure_count
                FROM celery_taskmeta
                WHERE name = %s
                AND date_done >= NOW() - INTERVAL '{lookback_days} days'
                """,
                [task_path],
            )

            row = result.fetchone()

            if row:
                last_run = row[0]
                success_count = int(row[1] or 0)
                failure_count = int(row[2] or 0)

                # Calculate success rate
                total = success_count + failure_count
                success_rate = int((success_count / total) * 100) if total > 0 else None

                # TODO: Calculate duration metrics (requires parsing result JSONB)
                avg_duration = None
                max_duration = None

                return (
                    last_run,
                    None,  # next_run_at (requires celerybeat schedule tracking)
                    success_count,
                    failure_count,
                    success_rate,
                    avg_duration,
                    max_duration,
                )

    except Exception as e:
        logger.warning("failed_to_query_task_metadata", task=task_path, error=str(e))

    return None, None, 0, 0, None, None, None
