"""Celery task inspection service.

Provides functions to inspect Celery tasks from multiple sources:
- Active tasks (currently running)
- Pending tasks (queued/reserved)
- Completed tasks (from celery_taskmeta table)
- Failed tasks (from celery_taskmeta table)
"""

from datetime import datetime
from typing import Any, Literal

from app.celery_app import celery_app
from app.storage.connection import ConnectionManager


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
    inspect = celery_app.control.inspect(timeout=2.0)
    try:
        active = inspect.active()

        if not active:
            return []

        tasks: list[dict[str, Any]] = []
        for worker_name, worker_tasks in active.items():
            for task in worker_tasks:
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
                    "args": task.get("args", "[]"),
                    "kwargs": task.get("kwargs", "{}"),
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
    inspect = celery_app.control.inspect(timeout=2.0)
    try:
        reserved = inspect.reserved()

        if not reserved:
            return []

        tasks: list[dict[str, Any]] = []
        for worker_name, worker_tasks in reserved.items():
            for task in worker_tasks:
                normalized_task = {
                    "id": task["id"],
                    "name": task["name"],
                    "status": "PENDING",
                    "started_at": None,
                    "duration": None,
                    "worker": worker_name,
                    "args": task.get("args", "[]"),
                    "kwargs": task.get("kwargs", "{}"),
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
            SELECT task_id, status, result, date_done, traceback
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
                "result": row[2],
                "date_done": row[3].isoformat() if row[3] else None,
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
            SELECT task_id, status, result, date_done, traceback
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
                "traceback": row[4],
                "date_done": row[3].isoformat() if row[3] else None,
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
            task["name"] = "unknown"  # Not stored in taskmeta
            task["started_at"] = None
            task["duration"] = None
            task["worker"] = None
            task["args"] = None
            task["kwargs"] = None
            task["traceback"] = None
            # Convert result memoryview to string
            if task.get("result") and hasattr(task["result"], "tobytes"):
                try:
                    task["result"] = task["result"].tobytes().decode("utf-8")
                except Exception:
                    task["result"] = str(task["result"])
            elif task.get("result"):
                task["result"] = str(task["result"])
        tasks.extend(completed)

    if status in ("all", "failed"):
        failed = get_recent_failed(limit=limit)
        # Convert to unified schema with all required fields
        for task in failed:
            task["id"] = task.pop("task_id")
            task["name"] = "unknown"  # Not stored in taskmeta
            task["started_at"] = None
            task["duration"] = None
            task["worker"] = None
            task["args"] = None
            task["kwargs"] = None
            task["result"] = None
            # Convert traceback memoryview to string
            if task.get("traceback") and hasattr(task["traceback"], "tobytes"):
                try:
                    task["traceback"] = task["traceback"].tobytes().decode("utf-8")
                except Exception:
                    task["traceback"] = str(task["traceback"])
            elif task.get("traceback"):
                task["traceback"] = str(task["traceback"])
        tasks.extend(failed)

    return tasks
