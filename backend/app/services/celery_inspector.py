"""Celery task inspection service.

Provides functions to inspect Celery tasks from multiple sources:
- Active tasks (currently running)
- Pending tasks (queued/reserved)
- Completed tasks (from celery_taskmeta table)
- Failed tasks (from celery_taskmeta table)
"""

import json
import pickle
from datetime import datetime
from typing import Any, Literal

from app.storage.connection import ConnectionManager


def _deserialize_celery_field(value: Any) -> str | None:
    """Safely deserialize a Celery result/traceback field.

    Celery stores results/tracebacks as pickled objects in bytea columns.
    When read from the database, they come back as memoryview objects.

    Args:
        value: Raw field value from database (memoryview, bytes, or already deserialized)

    Returns:
        JSON-serializable string representation, or None if empty/invalid
    """
    if value is None:
        return None

    try:
        # Convert memoryview to bytes
        bytes_value = value.tobytes() if isinstance(value, memoryview) else value

        # If it's bytes, try to unpickle
        if isinstance(bytes_value, bytes):
            # Try unpickling first
            try:
                unpickled = pickle.loads(bytes_value)
                # Convert to JSON-safe string
                return (
                    json.dumps(unpickled) if isinstance(unpickled, (dict, list)) else str(unpickled)
                )
            except (pickle.UnpicklingError, Exception):
                # If unpickling fails, try UTF-8 decode as fallback
                try:
                    return bytes_value.decode("utf-8")
                except UnicodeDecodeError:
                    return f"<binary data: {len(bytes_value)} bytes>"

        # Already a string or other type
        return str(value)

    except Exception as e:
        return f"<error deserializing: {e!s}>"


def get_active_tasks() -> list[dict[str, Any]]:
    """Get currently running tasks from Celery workers.

    Returns:
        List of active tasks with normalized schema:
        [{
            "id": "task-uuid",
            "name": "app.tasks.task_name",
            "status": "ACTIVE",
            "started_at": ISO timestamp,
            "duration": seconds (float),
            "worker": "celery@hostname",
            "args": JSON string,
            "kwargs": JSON string,
        }, ...]
    """
    # Lazy import to avoid circular dependency with app.tasks
    from app.celery_app import celery_app  # noqa: PLC0415

    inspect = celery_app.control.inspect(timeout=2.0)
    try:
        active = inspect.active()

        if not active:
            return []

        tasks: list[dict[str, Any]] = []
        for worker_name, worker_tasks in active.items():
            for task in worker_tasks:
                # Normalize args and kwargs to JSON strings
                args = task.get("args", [])
                kwargs = task.get("kwargs", {})
                args_str = json.dumps(args) if isinstance(args, (list, tuple)) else str(args)
                kwargs_str = json.dumps(kwargs) if isinstance(kwargs, dict) else str(kwargs)

                normalized_task = {
                    "id": task["id"],
                    "name": task["name"],
                    "status": "ACTIVE",
                    "started_at": (
                        datetime.fromtimestamp(task["time_start"]).isoformat()
                        if "time_start" in task
                        else None
                    ),
                    "duration": (
                        (datetime.now().timestamp() - task["time_start"])
                        if "time_start" in task
                        else None
                    ),
                    "worker": worker_name,
                    "args": args_str,
                    "kwargs": kwargs_str,
                }
                tasks.append(normalized_task)

        return tasks
    finally:
        # Close the inspect connection to prevent connection leaks
        if hasattr(inspect, "close"):
            inspect.close()


def get_pending_tasks() -> list[dict[str, Any]]:
    """Get pending/reserved tasks from Celery workers.

    Returns:
        List of pending tasks with normalized schema:
        [{
            "id": "task-uuid",
            "name": "app.tasks.task_name",
            "status": "PENDING",
            "worker": "celery@hostname",
            "args": JSON string,
            "kwargs": JSON string,
        }, ...]
    """
    # Lazy import to avoid circular dependency with app.tasks
    from app.celery_app import celery_app  # noqa: PLC0415

    inspect = celery_app.control.inspect(timeout=2.0)
    try:
        reserved = inspect.reserved()

        if not reserved:
            return []

        tasks: list[dict[str, Any]] = []
        for worker_name, worker_tasks in reserved.items():
            for task in worker_tasks:
                # Normalize args and kwargs to JSON strings
                args = task.get("args", [])
                kwargs = task.get("kwargs", {})
                args_str = json.dumps(args) if isinstance(args, (list, tuple)) else str(args)
                kwargs_str = json.dumps(kwargs) if isinstance(kwargs, dict) else str(kwargs)

                normalized_task = {
                    "id": task["id"],
                    "name": task["name"],
                    "status": "PENDING",
                    "started_at": None,
                    "duration": None,
                    "worker": worker_name,
                    "args": args_str,
                    "kwargs": kwargs_str,
                }
                tasks.append(normalized_task)

        return tasks
    finally:
        # Close the inspect connection to prevent connection leaks
        if hasattr(inspect, "close"):
            inspect.close()


def get_recent_completed(limit: int = 50) -> list[dict[str, Any]]:
    """Get recently completed tasks from celery_taskmeta table.

    Args:
        limit: Maximum number of tasks to return (default 50)

    Returns:
        List of completed tasks with normalized schema:
        [{
            "task_id": "task-uuid",
            "status": "SUCCESS",
            "result": JSON string or None,
            "date_done": ISO timestamp,
        }, ...]
    """
    cm = ConnectionManager()

    with cm.connection() as conn:
        result = conn.execute(
            """
            SELECT task_id, status, result, date_done, traceback, name, args, kwargs, worker
            FROM celery_taskmeta
            WHERE status = 'SUCCESS'
            ORDER BY date_done DESC
            LIMIT %s
        """,
            [limit],
        )

        rows = result.fetchall()
        tasks = []
        for row in rows:
            task = {
                "task_id": row[0],
                "status": row[1],
                "result": _deserialize_celery_field(row[2]),
                "date_done": row[3].isoformat() if isinstance(row[3], datetime) else None,
                "traceback": _deserialize_celery_field(row[4]),
                "name": row[5] or "unknown",  # Handle NULL names
                "args": _deserialize_celery_field(row[6]),
                "kwargs": _deserialize_celery_field(row[7]),
                "worker": row[8],
            }
            tasks.append(task)

        return tasks


def get_recent_failed(limit: int = 50) -> list[dict[str, Any]]:
    """Get recently failed tasks from celery_taskmeta table.

    Args:
        limit: Maximum number of tasks to return (default 50)

    Returns:
        List of failed tasks with normalized schema:
        [{
            "task_id": "task-uuid",
            "status": "FAILURE",
            "traceback": Error traceback string,
            "date_done": ISO timestamp,
        }, ...]
    """
    cm = ConnectionManager()

    with cm.connection() as conn:
        result = conn.execute(
            """
            SELECT task_id, status, result, date_done, traceback, name, args, kwargs, worker
            FROM celery_taskmeta
            WHERE status = 'FAILURE'
            ORDER BY date_done DESC
            LIMIT %s
        """,
            [limit],
        )

        rows = result.fetchall()
        tasks = []
        for row in rows:
            task = {
                "task_id": row[0],
                "status": row[1],
                "result": _deserialize_celery_field(row[2]),
                "date_done": row[3].isoformat() if isinstance(row[3], datetime) else None,
                "traceback": _deserialize_celery_field(row[4]),
                "name": row[5] or "unknown",  # Handle NULL names
                "args": _deserialize_celery_field(row[6]),
                "kwargs": _deserialize_celery_field(row[7]),
                "worker": row[8],
            }
            tasks.append(task)

        return tasks


def get_queue_depth() -> int:
    """Get total count of pending/queued tasks across all workers.

    Returns:
        Total number of pending tasks
    """
    pending_tasks = get_pending_tasks()
    return len(pending_tasks)


# Default threshold for queue backpressure (prevent cascading task explosions)
QUEUE_BACKPRESSURE_THRESHOLD = 100


def should_skip_cascade(threshold: int = QUEUE_BACKPRESSURE_THRESHOLD) -> bool:
    """Check if queue is too deep to schedule more cascaded tasks.

    Use this before calling .delay() or apply_async() on downstream tasks
    to prevent queue saturation during high load periods.

    Args:
        threshold: Maximum queue depth before skipping (default: 100)

    Returns:
        True if queue depth exceeds threshold (skip scheduling), False otherwise
    """
    try:
        depth = get_queue_depth()
        return depth >= threshold
    except Exception:
        # If we can't check queue depth, allow scheduling (fail open)
        return False


def schedule_with_backpressure(
    task: Any,
    args: tuple[Any, ...] | None = None,
    kwargs: dict[str, Any] | None = None,
    threshold: int = QUEUE_BACKPRESSURE_THRESHOLD,
    countdown: int | None = None,
) -> str | None:
    """Schedule a task only if queue depth is below threshold.

    Provides backpressure mechanism to prevent queue saturation.

    Args:
        task: Celery task to schedule
        args: Positional arguments for the task
        kwargs: Keyword arguments for the task
        threshold: Maximum queue depth before skipping
        countdown: Optional delay in seconds before task runs

    Returns:
        Task ID if scheduled, None if skipped due to backpressure
    """
    if should_skip_cascade(threshold):
        return None

    apply_kwargs: dict[str, Any] = {}
    if args:
        apply_kwargs["args"] = args
    if kwargs:
        apply_kwargs["kwargs"] = kwargs
    if countdown:
        apply_kwargs["countdown"] = countdown

    result = task.apply_async(**apply_kwargs)
    task_id: str | None = result.id
    return task_id


def get_unified_task_list(
    status: Literal["all", "active", "pending", "completed", "failed"] = "all",
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Get unified task list from all sources with optional filtering.

    Args:
        status: Filter by task status:
            - "all": Return all tasks (default)
            - "active": Only running tasks
            - "pending": Only queued tasks
            - "completed": Only successfully completed tasks
            - "failed": Only failed tasks
        limit: Maximum number of tasks to return per category

    Returns:
        List of tasks from all sources, sorted by most recent first
    """
    tasks: list[dict[str, Any]] = []

    if status in ("all", "active"):
        tasks.extend(get_active_tasks())

    if status in ("all", "pending"):
        tasks.extend(get_pending_tasks())

    if status in ("all", "completed"):
        completed = get_recent_completed(limit=limit)
        # Convert to unified schema with all required fields
        for task in completed:
            task["id"] = task.pop("task_id")
            # name, args, kwargs, worker, result, traceback are already populated from DB
            task["started_at"] = None  # Not available for completed tasks

            # Extract duration from result if available (tasks include duration_seconds in result)
            duration = None
            if task.get("result"):
                try:
                    result_data = (
                        json.loads(task["result"])
                        if isinstance(task["result"], str)
                        else task["result"]
                    )
                    if isinstance(result_data, dict) and "duration_seconds" in result_data:
                        duration = result_data["duration_seconds"]
                except (json.JSONDecodeError, TypeError):
                    pass  # If result isn't JSON or doesn't have duration, duration stays None

            task["duration"] = duration
        tasks.extend(completed)

    if status in ("all", "failed"):
        failed = get_recent_failed(limit=limit)
        # Convert to unified schema with all required fields
        for task in failed:
            task["id"] = task.pop("task_id")
            # name, args, kwargs, worker, result, traceback are already populated from DB
            task["started_at"] = None  # Not available for failed tasks

            # Extract duration from result if available (tasks include duration_seconds in result)
            duration = None
            if task.get("result"):
                try:
                    result_data = (
                        json.loads(task["result"])
                        if isinstance(task["result"], str)
                        else task["result"]
                    )
                    if isinstance(result_data, dict) and "duration_seconds" in result_data:
                        duration = result_data["duration_seconds"]
                except (json.JSONDecodeError, TypeError):
                    pass  # If result isn't JSON or doesn't have duration, duration stays None

            task["duration"] = duration
        tasks.extend(failed)

    return tasks
