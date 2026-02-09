"""Context manager for structured background task logging.

This module provides a context manager that automatically logs task execution
with consistent structured fields including timing, parameters, and error details.
"""

from __future__ import annotations

import time
import traceback
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from app.logging_config import get_logger


@contextmanager
def task_logger(
    task_name: str,
    task_id: str,
    input_params: dict[str, Any] | None = None,
    logger_name: str | None = None,
) -> Generator[None]:
    """Context manager for structured background task logging with automatic timing.

    Logs task execution with consistent structured fields:
    - task_name: Human-readable task identifier
    - task_id: Task ID
    - duration_ms: Execution time in milliseconds
    - input_params: Dictionary of input parameters
    - status: "started", "completed", "failed"
    - error/error_type/traceback: On failure only

    Usage:
        ```python
        def my_task(param1: str, param2: int) -> dict[str, Any]:
            task_id = str(uuid.uuid4())

            with task_logger("my_task", task_id, {"param1": param1, "param2": param2}):
                # Task logic here
                result = do_work(param1, param2)
                return result
        ```

    Args:
        task_name: Human-readable task name (e.g., "refresh_watchlist_scores")
        task_id: Task ID
        input_params: Dictionary of task input parameters for logging
        logger_name: Optional logger name (defaults to task_name)

    Yields:
        None (context manager)

    Raises:
        Re-raises any exception after logging it with full traceback
    """
    logger = get_logger(logger_name or f"tasks.{task_name}")
    params = input_params or {}

    # Log task start
    start_time = time.perf_counter()
    logger.info(
        f"{task_name}_started",
        task_name=task_name,
        task_id=task_id,
        status="started",
        **params,
    )

    try:
        yield
        # Log task completion
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"{task_name}_completed",
            task_name=task_name,
            task_id=task_id,
            status="completed",
            duration_ms=round(duration_ms, 2),
            **params,
        )

    except Exception as e:
        # Log task failure with full traceback
        duration_ms = (time.perf_counter() - start_time) * 1000
        error_traceback = traceback.format_exc()

        logger.error(
            f"{task_name}_failed",
            task_name=task_name,
            task_id=task_id,
            status="failed",
            duration_ms=round(duration_ms, 2),
            error=str(e),
            error_type=type(e).__name__,
            traceback=error_traceback,
            **params,
        )
        raise  # Re-raise to preserve error handling


def log_task_skip(
    task_name: str,
    task_id: str,
    reason: str,
    duration_ms: float,
    extra_fields: dict[str, Any] | None = None,
    logger_name: str | None = None,
) -> None:
    """Log when a task is skipped without executing main logic.

    Used for tasks that may skip execution based on conditions
    (e.g., refresh interval not met, no data to process).

    Args:
        task_name: Human-readable task name
        task_id: Task ID
        reason: Explanation for why task was skipped
        duration_ms: Time spent checking conditions before skipping
        extra_fields: Additional structured fields to log
        logger_name: Optional logger name (defaults to task_name)
    """
    logger = get_logger(logger_name or f"tasks.{task_name}")
    fields = extra_fields or {}

    logger.info(
        f"{task_name}_skipped",
        task_name=task_name,
        task_id=task_id,
        status="skipped",
        reason=reason,
        duration_ms=round(duration_ms, 2),
        **fields,
    )
