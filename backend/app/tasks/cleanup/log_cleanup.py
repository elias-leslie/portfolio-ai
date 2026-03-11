"""Log file rotation and cleanup tasks.

This module provides automated log cleanup tasks for:
- Log file rotation (when files exceed size threshold)
- Old log file deletion (based on retention period)

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Non-destructive (respect retention periods)
- Scheduled via Hatchet cron workflows
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from app.logging_config import get_logger
from app.tasks.cleanup.log_cleanup_helpers import run_log_rotation, run_old_logs_cleanup
from app.tasks.maintenance_logging import (
    log_maintenance_complete,
    log_maintenance_start,
)
from app.utils.task_helpers import build_error_result, calculate_duration

logger = get_logger(__name__)


def _handle_task_error(
    task_id: str,
    error: Exception,
    start_time: dt.datetime,
    log_id: int,
    task_name: str,
    dry_run: bool,
) -> dict[str, Any]:
    """Log error and return standardized error result for a failed task."""
    duration = calculate_duration(start_time)
    logger.error(
        f"{task_name}_failed",
        task_id=task_id,
        error=str(error),
        error_type=type(error).__name__,
        duration_seconds=round(duration, 2),
    )
    error_result = build_error_result(task_id, error, duration, dry_run=dry_run)
    log_maintenance_complete(log_id, task_name, False, error_result, str(error))
    return error_result


def rotate_logs_task(dry_run: bool = False) -> dict[str, int | str | float | bool]:
    """Rotate logs in /tmp and /var/log/portfolio-ai directories.

    Args:
        dry_run: If True, only report what would be rotated

    Returns:
        Dict with task_id, files_rotated, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("rotate_logs_task", dry_run)

    logger.info("rotate_logs_started", task_id=task_id, dry_run=dry_run)

    try:
        result = run_log_rotation(task_id, dry_run)
        result["duration_seconds"] = round(calculate_duration(start_time), 2)
        logger.info(
            "rotate_logs_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "rotate_logs_task", True, result)
        return result

    except Exception as e:
        return _handle_task_error(task_id, e, start_time, log_id, "rotate_logs_task", dry_run)


def cleanup_old_logs_task(days: int = 7, dry_run: bool = False) -> dict[str, Any]:
    """Delete log files older than specified days.

    Args:
        days: Delete logs older than N days (default: 7)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_old_logs_task", dry_run)

    logger.info("cleanup_old_logs_started", task_id=task_id, days=days, dry_run=dry_run)

    try:
        result = run_old_logs_cleanup(task_id, dry_run, days)
        result["duration_seconds"] = round(calculate_duration(start_time), 2)
        logger.info(
            "cleanup_old_logs_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "cleanup_old_logs_task", True, result)
        return result

    except Exception as e:
        return _handle_task_error(
            task_id, e, start_time, log_id, "cleanup_old_logs_task", dry_run
        )
