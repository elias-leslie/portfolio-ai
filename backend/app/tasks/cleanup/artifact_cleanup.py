"""Artifact cleanup tasks.

This module provides automated cleanup tasks for:
- Old backup files (SQL dumps)
- Old ML model versions

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Non-destructive (respect retention periods)
- Scheduled via Hatchet cron workflows
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.logging_config import get_logger
from app.tasks.cleanup.artifact_cleanup_helpers import (
    run_backups_cleanup,
    run_models_cleanup,
)
from app.tasks.maintenance_logging import (
    log_maintenance_complete,
    log_maintenance_start,
)
from app.utils.task_helpers import build_error_result, calculate_duration

logger = get_logger(__name__)

# Type alias for task result dicts
TaskResult = dict[str, int | float | str | bool | list[dict[str, int | float | str]]]


def cleanup_old_backups_task(keep_count: int = 5, dry_run: bool = False) -> TaskResult:
    """Delete old backup files, keeping N most recent.

    Args:
        keep_count: Number of recent backups to keep (default: 5)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_old_backups_task", dry_run)
    logger.info(
        "cleanup_old_backups_started", task_id=task_id, keep_count=keep_count, dry_run=dry_run
    )
    try:
        result = run_backups_cleanup(task_id, dry_run, keep_count, log_id)
        result["duration_seconds"] = round(calculate_duration(start_time), 2)
        logger.info(
            "cleanup_old_backups_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "cleanup_old_backups_task", True, result)
        return result
    except Exception as e:
        return _handle_task_error(
            task_id, e, start_time, log_id, "cleanup_old_backups_task", dry_run
        )


def cleanup_old_models_task(keep_count: int = 3, dry_run: bool = False) -> TaskResult:
    """Delete old ML model versions, keeping N most recent per model type.

    Args:
        keep_count: Number of recent versions to keep per model type (default: 3)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_old_models_task", dry_run)
    logger.info(
        "cleanup_old_models_started", task_id=task_id, keep_count=keep_count, dry_run=dry_run
    )
    try:
        result = run_models_cleanup(task_id, dry_run, keep_count, log_id)
        result["duration_seconds"] = round(calculate_duration(start_time), 2)
        logger.info(
            "cleanup_old_models_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "cleanup_old_models_task", True, result)
        return result
    except Exception as e:
        return _handle_task_error(
            task_id, e, start_time, log_id, "cleanup_old_models_task", dry_run
        )


def _handle_task_error(
    task_id: str,
    error: Exception,
    start_time: dt.datetime,
    log_id: int,
    task_name: str,
    dry_run: bool,
) -> TaskResult:
    """Log error and build standardized error result for a failed task.

    Args:
        task_id: The task ID
        error: The exception that was raised
        start_time: Task start time for duration calculation
        log_id: Maintenance log ID
        task_name: Name of the failed task
        dry_run: Whether this was a dry run

    Returns:
        Standardized error result dict
    """
    duration = calculate_duration(start_time)
    logger.error(
        "artifact_cleanup_failed",
        task_name=task_name,
        task_id=task_id,
        error=str(error),
        error_type=type(error).__name__,
        duration_seconds=round(duration, 2),
        exc_info=True,
    )
    error_result = build_error_result(task_id, error, duration, dry_run=dry_run)
    log_maintenance_complete(log_id, task_name, False, error_result, str(error))
    return error_result
