"""Temporary file and cache cleanup tasks.

This module provides automated cleanup tasks for:
- Temporary files in /tmp
- Development cache directories (optional manual task)

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Non-destructive (respect retention periods)
- Scheduled or manually triggered
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from app.logging_config import get_logger
from app.tasks.cleanup.temp_cleanup_helpers import run_cache_cleanup, run_temp_cleanup
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


def cleanup_temp_files_task(
    hours: int = 24, dry_run: bool = False
) -> dict[str, Any]:
    """Delete temporary files older than specified hours.

    Args:
        hours: Delete temp files older than N hours (default: 24)
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with task_id, files_deleted, bytes_freed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_temp_files_task", dry_run)

    logger.info("cleanup_temp_files_started", task_id=task_id, hours=hours, dry_run=dry_run)

    try:
        result = run_temp_cleanup(task_id, dry_run, hours)
        result["duration_seconds"] = round(calculate_duration(start_time), 2)
        logger.info(
            "cleanup_temp_files_completed",
            **{k: v for k, v in result.items() if k != "would_action_list"},
        )
        log_maintenance_complete(log_id, "cleanup_temp_files_task", True, result)
        return result

    except Exception as e:
        return _handle_task_error(
            task_id, e, start_time, log_id, "cleanup_temp_files_task", dry_run
        )


def cleanup_cache_directories_task(dry_run: bool = False) -> dict[str, Any]:
    """Clean up development cache directories to free disk space.

    This is an OPTIONAL manual task - not scheduled by default.
    Safe to run anytime as caches regenerate automatically.

    Targets:
    - backend/__pycache__ (recursive)
    - backend/.ruff_cache
    - backend/.pytest_cache
    - backend/.mypy_cache
    - frontend/.next/cache (NOT .next/server)
    - .claude/backups/memory (Claude transient memory)
    - services/*/__pycache__ (recursive)

    Args:
        dry_run: If True, only report what would be deleted

    Returns:
        Dict with directories_cleaned, files_deleted, bytes_freed, duration_seconds
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start("cleanup_cache_directories_task", dry_run)

    logger.info("cleanup_cache_directories_started", task_id=task_id, dry_run=dry_run)

    try:
        result = run_cache_cleanup(task_id, dry_run)
        result["duration_seconds"] = round(calculate_duration(start_time), 2)
        logger.info(
            "cleanup_cache_directories_completed",
            **{k: v for k, v in result.items() if k != "details"},
        )
        log_maintenance_complete(log_id, "cleanup_cache_directories_task", True, result)
        return result

    except Exception as e:
        return _handle_task_error(
            task_id, e, start_time, log_id, "cleanup_cache_directories_task", dry_run
        )
