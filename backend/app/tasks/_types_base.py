"""Base task result TypedDict and builder functions.

Provides TaskResultDict and standard build_task_success/build_task_failure helpers
used across all task modules.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict


class TaskResultDict(TypedDict, total=False):
    """Standard task result dictionary returned by most tasks.

    Fields:
        status: Task status ("success", "error", "skipped", "completed", "insufficient_data")
        message: Human-readable status message
        data: Metadata about the task result
        errors: List of error messages (if any)
        timestamp: ISO format timestamp of task completion
        error: Error message (alternative field for backward compatibility)
    """

    status: str
    message: str
    data: dict[str, int | float | str | list[object] | None]
    errors: list[str]
    timestamp: str
    error: str


def _build_optional_data(
    evaluated: int | None,
    generated: int | None,
    promoted: int | None,
    archived: int | None,
    evolved: int | None,
    details: dict[str, int | float | str | list[object] | None] | None,
) -> dict[str, int | float | str | list[object] | None]:
    """Collect optional numeric fields into a data dict."""
    data: dict[str, int | float | str | list[object] | None] = {}
    if evaluated is not None:
        data["evaluated"] = evaluated
    if generated is not None:
        data["generated"] = generated
    if promoted is not None:
        data["promoted"] = promoted
    if archived is not None:
        data["archived"] = archived
    if evolved is not None:
        data["evolved"] = evolved
    if details:
        data.update(details)
    return data


def build_task_success(
    message: str = "Task completed successfully",
    *,
    evaluated: int | None = None,
    generated: int | None = None,
    promoted: int | None = None,
    archived: int | None = None,
    evolved: int | None = None,
    details: dict[str, int | float | str | list[object] | None] | None = None,
) -> TaskResultDict:
    """Build a standardized success result dictionary.

    Note: For strategy monitoring tasks, prefer build_strategy_success()
    which uses the correct 'completed'/'failed' status values.

    Args:
        message: Human-readable status message
        evaluated: Number of items evaluated (optional)
        generated: Number of items generated (optional)
        promoted: Number of items promoted (optional)
        archived: Number of items archived (optional)
        evolved: Number of items evolved (optional)
        details: Additional metadata (optional)

    Returns:
        TaskResultDict with status="success" and provided fields
    """
    result: TaskResultDict = {
        "status": "success",
        "message": message,
        "timestamp": datetime.now(UTC).isoformat(),
    }
    data = _build_optional_data(evaluated, generated, promoted, archived, evolved, details)
    if data:
        result["data"] = data
    return result


def build_task_failure(error: Exception) -> TaskResultDict:
    """Build a standardized failure result dictionary.

    Note: For strategy monitoring tasks, prefer build_strategy_failure()
    which uses 'failed' status instead of 'error'.

    Args:
        error: Exception that caused the task failure

    Returns:
        TaskResultDict with status="error" and error message
    """
    return {
        "status": "error",
        "message": "Task failed",
        "error": str(error),
        "timestamp": datetime.now(UTC).isoformat(),
    }
