"""Maintenance logging utilities for scheduled tasks.

This module provides functions for tasks to log their execution
to the maintenance_log table, enabling unified tracking across all
maintenance operations (both script-based and Hatchet-based).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)


def log_maintenance_start(task_name: str, dry_run: bool = False) -> int:
    """Log the start of a maintenance task.

    Args:
        task_name: Name of the task (e.g., 'cleanup_old_logs_task')
        dry_run: Whether running in dry-run mode

    Returns:
        ID of the created log entry for later update
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            result = conn.execute(
                """
                INSERT INTO maintenance_log (task_name, started_at, status, dry_run)
                VALUES (%s, %s, 'running', %s)
                RETURNING id
                """,
                [task_name, datetime.now(UTC), dry_run],
            ).fetchone()
            conn.commit()

            if result and result[0] is not None:
                return int(result[0])
    except Exception as e:
        logger.warning("maintenance_log_start_failed", task_name=task_name, error=str(e))

    return 0  # Return 0 if logging fails - task should still proceed


def record_maintenance_metric(
    metric_name: str,
    metric_value: float | int,
    metric_unit: str,
    metadata: str | None = None,
) -> None:
    """Record a maintenance metric to maintenance_stats table.

    Args:
        metric_name: Name of the metric (e.g., 'log_cleanup_bytes_freed')
        metric_value: Numeric value of the metric
        metric_unit: Unit of measurement (e.g., 'bytes', 'percentage', 'count')
        metadata: Optional JSON string with additional context
    """
    conn_mgr = get_connection_manager()
    try:
        with conn_mgr.connection() as conn:
            if metadata:
                conn.execute(
                    """
                    INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit, metadata)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [metric_name, metric_value, metric_unit, metadata],
                )
            else:
                conn.execute(
                    """
                    INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit)
                    VALUES (%s, %s, %s)
                    """,
                    [metric_name, metric_value, metric_unit],
                )
            conn.commit()
    except Exception as e:
        logger.warning(
            "maintenance_metric_record_failed",
            metric_name=metric_name,
            error=str(e),
        )


def log_maintenance_complete(
    log_id: int,
    task_name: str,
    success: bool,
    summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """Log the completion of a maintenance task.

    Args:
        log_id: ID returned from log_maintenance_start (0 if start failed)
        task_name: Name of the task
        success: Whether task completed successfully
        summary: Task result summary dict
        error_message: Error message if failed
    """
    if log_id == 0:
        # Start logging failed, try to create a complete record instead
        conn_mgr = get_connection_manager()
        try:
            with conn_mgr.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO maintenance_log
                    (task_name, started_at, completed_at, status, dry_run, summary, error_message)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        task_name,
                        datetime.now(UTC),
                        datetime.now(UTC),
                        "success" if success else "error",
                        summary.get("dry_run", False) if summary else False,
                        json.dumps(summary) if summary else None,
                        error_message,
                    ],
                )
                conn.commit()
        except Exception as e:
            logger.warning(
                "maintenance_log_complete_insert_failed", task_name=task_name, error=str(e)
            )
        return

    conn_mgr = get_connection_manager()
    try:
        with conn_mgr.connection() as conn:
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
                    datetime.now(UTC),
                    "success" if success else "error",
                    json.dumps(summary) if summary else None,
                    error_message,
                    log_id,
                ],
            )
            conn.commit()
    except Exception as e:
        logger.warning(
            "maintenance_log_complete_failed", log_id=log_id, task_name=task_name, error=str(e)
        )
