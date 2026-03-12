"""Helper functions for maintenance tasks.

This module provides common utilities for maintenance tasks:
- Task execution wrappers (logging, duration tracking, error handling)
- Result builders (dry run, success, error)
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Any, TypeVar

from app.logging_config import get_logger
from app.tasks.maintenance_logging import log_maintenance_complete, log_maintenance_start
from app.utils.task_helpers import calculate_duration

logger = get_logger(__name__)

T = TypeVar("T")


def execute_maintenance_task(
    task_name: str,
    task_id: str,
    task_func: Callable[[], dict[str, Any]],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Execute a maintenance task with standardized logging and error handling.

    Args:
        task_name: Name of the task for logging
        task_id: Task ID
        task_func: Function that performs the actual work, returns result dict
        dry_run: Whether this is a dry run

    Returns:
        Dict with task results, duration, success status
    """
    start_time = dt.datetime.now(dt.UTC)
    log_id = log_maintenance_start(task_name, dry_run)

    logger.info("maintenance_task_started", task_name=task_name, task_id=task_id, dry_run=dry_run)

    try:
        result = task_func()
        duration = calculate_duration(start_time)

        result_dict: dict[str, Any] = {
            "task_id": task_id,
            "dry_run": dry_run,
            **result,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("maintenance_task_completed", task_name=task_name, **result_dict)
        log_maintenance_complete(log_id, task_name, True, result_dict)
        return result_dict

    except Exception as e:
        duration = calculate_duration(start_time)
        logger.error(
            "maintenance_task_failed",
            task_name=task_name,
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
            exc_info=True,
        )
        error_result = {
            "task_id": task_id,
            "dry_run": dry_run,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }
        log_maintenance_complete(log_id, task_name, False, error_result, str(e))
        return error_result


def build_dry_run_result(**kwargs: Any) -> dict[str, Any]:
    """Build a standardized dry run result dict.

    Args:
        **kwargs: Key-value pairs to include in result

    Returns:
        Dict with dry_run=True and provided kwargs
    """
    return {
        "dry_run": True,
        **kwargs,
        "success": True,
    }
