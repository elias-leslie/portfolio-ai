"""Service for tracking maintenance runs and statistics.

This module provides functions to:
- Record maintenance task start/completion
- Store maintenance statistics
- Query last run times
- Get cleanup trends

Used by maintenance tasks to track execution history and metrics.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)


def record_maintenance_start(task_name: str, dry_run: bool = False) -> int:
    """Record the start of a maintenance task.

    Args:
        task_name: Name of the maintenance task
        dry_run: Whether task is running in dry-run mode

    Returns:
        ID of the created maintenance_log entry
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        result = conn.execute(
            """
            INSERT INTO maintenance_log (task_name, started_at, status, dry_run)
            VALUES (%s, %s, 'running', %s)
            RETURNING id
            """,
            [task_name, dt.datetime.now(dt.UTC), dry_run],
        ).fetchone()
        conn.commit()

        if not result:
            raise RuntimeError("Failed to create maintenance_log entry")

        log_id_value = result[0]
        if not isinstance(log_id_value, int):
            raise RuntimeError(f"Invalid log_id type: {type(log_id_value)}")
        log_id: int = log_id_value
        logger.info(
            "maintenance_start_recorded",
            task_name=task_name,
            log_id=log_id,
            dry_run=dry_run,
        )
        return log_id


def record_maintenance_completion(
    log_id: int,
    status: str,
    summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """Record the completion of a maintenance task.

    Args:
        log_id: ID from record_maintenance_start()
        status: Final status ('success' or 'error')
        summary: Dict with task execution summary
        error_message: Error message if status is 'error'
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE maintenance_log
            SET completed_at = %s,
                status = %s,
                summary = %s,
                error_message = %s
            WHERE id = %s
            """,
            [
                dt.datetime.now(dt.UTC),
                status,
                json.dumps(summary) if summary else None,
                error_message,
                log_id,
            ],
        )
        conn.commit()

    logger.info(
        "maintenance_completion_recorded",
        log_id=log_id,
        status=status,
        has_summary=summary is not None,
    )


def save_maintenance_stat(
    metric_name: str,
    metric_value: float,
    metric_unit: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Save a maintenance statistic for trend tracking.

    Args:
        metric_name: Name of the metric (e.g., 'database_size_bytes')
        metric_value: Numeric value of the metric
        metric_unit: Unit of measurement (e.g., 'bytes', 'count')
        metadata: Additional context as JSON
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit, metadata)
            VALUES (%s, %s, %s, %s)
            """,
            [
                metric_name,
                metric_value,
                metric_unit,
                json.dumps(metadata) if metadata else None,
            ],
        )
        conn.commit()

    logger.info(
        "maintenance_stat_saved",
        metric_name=metric_name,
        metric_value=metric_value,
        metric_unit=metric_unit,
    )


def get_last_run_time(task_name: str) -> dt.datetime | None:
    """Get the last successful run time for a maintenance task.

    Args:
        task_name: Name of the maintenance task

    Returns:
        Datetime of last successful run, or None if never run
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT completed_at
            FROM maintenance_log
            WHERE task_name = %s
              AND status = 'success'
            ORDER BY completed_at DESC
            LIMIT 1
            """,
            [task_name],
        ).fetchone()

        if result and isinstance(result[0], dt.datetime):
            return result[0]
        return None


def get_last_run_summary(task_name: str) -> dict[str, Any] | None:
    """Get the summary from the last run of a maintenance task.

    Args:
        task_name: Name of the maintenance task

    Returns:
        Summary dict from last run, or None if never run
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT summary
            FROM maintenance_log
            WHERE task_name = %s
              AND status = 'success'
              AND summary IS NOT NULL
            ORDER BY completed_at DESC
            LIMIT 1
            """,
            [task_name],
        ).fetchone()

        if result and result[0]:
            summary_value = result[0]
            if isinstance(summary_value, str):
                parsed: dict[str, Any] = json.loads(summary_value)
                return parsed
        return None


def get_maintenance_history(
    task_name: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get maintenance execution history.

    Args:
        task_name: Filter by task name (None = all tasks)
        limit: Maximum number of results (default: 50, max: 200)

    Returns:
        List of maintenance run records
    """
    if limit < 1 or limit > 200:
        limit = 50

    storage = get_connection_manager()

    with storage.connection() as conn:
        if task_name:
            result = conn.execute(
                """
                SELECT id, task_name, started_at, completed_at, status, dry_run, summary, error_message
                FROM maintenance_log
                WHERE task_name = %s
                ORDER BY started_at DESC
                LIMIT %s
                """,
                [task_name, limit],
            ).fetchall()
        else:
            result = conn.execute(
                """
                SELECT id, task_name, started_at, completed_at, status, dry_run, summary, error_message
                FROM maintenance_log
                ORDER BY started_at DESC
                LIMIT %s
                """,
                [limit],
            ).fetchall()

        history: list[dict[str, Any]] = []
        for row in result:
            started_at_value = row[2]
            completed_at_value = row[3]
            summary_value = row[6]

            started_at_str = (
                started_at_value.isoformat() if isinstance(started_at_value, dt.datetime) else None
            )
            completed_at_str = (
                completed_at_value.isoformat()
                if isinstance(completed_at_value, dt.datetime)
                else None
            )
            summary_dict = json.loads(summary_value) if isinstance(summary_value, str) else None

            history.append(
                {
                    "id": row[0],
                    "task_name": row[1],
                    "started_at": started_at_str,
                    "completed_at": completed_at_str,
                    "status": row[4],
                    "dry_run": row[5],
                    "summary": summary_dict,
                    "error_message": row[7],
                }
            )
        return history


def get_cleanup_trends(
    metric_name: str,
    days: int = 30,
) -> list[dict[str, Any]]:
    """Get trend data for a maintenance metric.

    Args:
        metric_name: Name of the metric to retrieve
        days: Number of days of history (default: 30)

    Returns:
        List of metric values over time
    """
    storage = get_connection_manager()
    cutoff_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT recorded_at, metric_value, metric_unit, metadata
            FROM maintenance_stats
            WHERE metric_name = %s
              AND recorded_at >= %s
            ORDER BY recorded_at ASC
            """,
            [metric_name, cutoff_date],
        ).fetchall()

        trends: list[dict[str, Any]] = []
        for row in result:
            recorded_at_value = row[0]
            metric_value = row[1]
            metadata_value = row[3]

            recorded_at_str = (
                recorded_at_value.isoformat()
                if isinstance(recorded_at_value, dt.datetime)
                else None
            )
            metric_float: float | None = None
            if isinstance(metric_value, (int, float)):
                metric_float = float(metric_value)
            metadata_dict = json.loads(metadata_value) if isinstance(metadata_value, str) else None

            trends.append(
                {
                    "recorded_at": recorded_at_str,
                    "value": metric_float,
                    "unit": row[2],
                    "metadata": metadata_dict,
                }
            )
        return trends


def get_all_metrics_summary() -> dict[str, Any]:
    """Get summary of all maintenance metrics.

    Returns:
        Dict with latest values for all tracked metrics
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        # Get latest value for each metric
        result = conn.execute(
            """
            SELECT DISTINCT ON (metric_name)
                metric_name,
                metric_value,
                metric_unit,
                recorded_at
            FROM maintenance_stats
            ORDER BY metric_name, recorded_at DESC
            """
        ).fetchall()

        metrics: dict[str, Any] = {}
        for row in result:
            metric_name_value = row[0]
            metric_value = row[1]
            recorded_at_value = row[3]

            if isinstance(metric_name_value, str):
                metric_float: float | None = None
                if isinstance(metric_value, (int, float)):
                    metric_float = float(metric_value)

                recorded_at_str = (
                    recorded_at_value.isoformat()
                    if isinstance(recorded_at_value, dt.datetime)
                    else None
                )

                metrics[metric_name_value] = {
                    "value": metric_float,
                    "unit": row[2],
                    "recorded_at": recorded_at_str,
                }

        return metrics
