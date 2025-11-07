"""Celery task monitoring endpoints.

Provides REST API endpoints for inspecting Celery tasks:
- GET /api/status/celery/tasks - Unified task list with filtering
- GET /api/status/celery/queue - Queue depth and stats
- GET /api/status/celery/schedule - Beat schedule information
"""

from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.celery_app import celery_app
from app.services.celery_inspector import (
    get_queue_depth,
    get_unified_task_list,
)
from app.storage import get_storage

router = APIRouter(prefix="/api/status/celery", tags=["celery"])


# Pydantic Models
class TaskInfo(BaseModel):
    """Information about a single Celery task."""

    id: str = Field(..., description="Task UUID")
    name: str = Field(..., description="Task name (module.function)")
    status: str = Field(..., description="Task status: ACTIVE, PENDING, SUCCESS, FAILURE")
    started_at: str | None = Field(None, description="ISO timestamp when task started")
    duration: float | None = Field(None, description="Task duration in seconds (active tasks only)")
    worker: str | None = Field(None, description="Worker name (e.g., celery@hostname)")
    args: str | None = Field(None, description="JSON string of task arguments")
    kwargs: str | None = Field(None, description="JSON string of task keyword arguments")
    result: str | None = Field(None, description="Task result (completed tasks only)")
    traceback: str | None = Field(None, description="Error traceback (failed tasks only)")
    date_done: str | None = Field(None, description="ISO timestamp when task completed")


class TaskListResponse(BaseModel):
    """Response containing list of tasks with statistics."""

    tasks: list[TaskInfo] = Field(..., description="List of tasks")
    total: int = Field(..., description="Total number of tasks returned")
    active_count: int = Field(..., description="Count of active (running) tasks")
    pending_count: int = Field(..., description="Count of pending (queued) tasks")
    completed_count: int = Field(..., description="Count of completed tasks")
    failed_count: int = Field(..., description="Count of failed tasks")


class QueueInfo(BaseModel):
    """Queue depth and consumer information."""

    depth: int = Field(..., description="Number of tasks in queue")
    consumers: int = Field(..., description="Number of active workers")


class ScheduleInfo(BaseModel):
    """Celery Beat schedule information."""

    name: str = Field(..., description="Task name")
    task: str = Field(..., description="Full task path")
    schedule: str = Field(..., description="Schedule string (e.g., 'every 60 seconds')")
    last_run: str | None = Field(None, description="Last run timestamp (ISO)")
    next_run: str | None = Field(None, description="Next run timestamp (ISO)")


# API Endpoints
@router.get("/tasks", response_model=TaskListResponse)
def get_celery_tasks(
    status: Literal["all", "active", "pending", "completed", "failed"] = Query(
        "all", description="Filter tasks by status"
    ),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of tasks to return"),
    sort: Literal["time", "duration", "name"] = Query("time", description="Sort order"),
) -> TaskListResponse:
    """Get unified list of Celery tasks with optional filtering.

    Args:
        status: Filter by task status (all, active, pending, completed, failed)
        limit: Maximum number of tasks to return (1-500)
        sort: Sort by time (default), duration, or name

    Returns:
        TaskListResponse with filtered/sorted tasks and statistics
    """
    # Get unified task list
    tasks = get_unified_task_list(status=status, limit=limit)

    # Sort tasks
    if sort == "duration" and status in ("all", "active"):
        # Only active tasks have duration
        tasks = sorted(
            tasks,
            key=lambda t: t.get("duration") or 0,
            reverse=True,
        )
    elif sort == "name":
        tasks = sorted(tasks, key=lambda t: t.get("name", ""))
    # Default: already sorted by time in get_unified_task_list

    # Calculate statistics
    active_count = sum(1 for t in tasks if t.get("status") == "ACTIVE")
    pending_count = sum(1 for t in tasks if t.get("status") == "PENDING")
    completed_count = sum(1 for t in tasks if t.get("status") == "SUCCESS")
    failed_count = sum(1 for t in tasks if t.get("status") == "FAILURE")

    # Convert to Pydantic models
    task_infos = [TaskInfo(**task) for task in tasks]

    return TaskListResponse(
        tasks=task_infos,
        total=len(task_infos),
        active_count=active_count,
        pending_count=pending_count,
        completed_count=completed_count,
        failed_count=failed_count,
    )


@router.get("/queue", response_model=QueueInfo)
def get_celery_queue() -> QueueInfo:
    """Get Celery queue depth and worker count.

    Returns:
        QueueInfo with current queue depth and active workers
    """
    depth = get_queue_depth()

    # Get worker count from inspect
    inspect = celery_app.control.inspect(timeout=2.0)
    try:
        stats = inspect.stats()
        consumers = len(stats) if stats else 0
    finally:
        # Close the inspect connection to prevent connection leaks
        if hasattr(inspect, "close"):
            inspect.close()

    return QueueInfo(depth=depth, consumers=consumers)


@router.get("/schedule", response_model=list[ScheduleInfo])
def get_celery_schedule() -> list[ScheduleInfo]:
    """Get Celery Beat schedule information with effective user-configured intervals.

    Returns:
        List of scheduled tasks with timing information from beat_schedule config
    """
    # Get beat schedule configuration directly from celery_app
    beat_schedule = celery_app.conf.beat_schedule

    if not beat_schedule:
        return []

    # Get user-configured refresh intervals
    storage = get_storage()
    user_intervals: dict[str, int] = {}
    try:
        prefs = storage.query(
            """
            SELECT
                COALESCE(watchlist_refresh_override, default_refresh_minutes, 15) as watchlist_minutes,
                COALESCE(news_refresh_override, default_refresh_minutes, 15) as news_minutes,
                default_refresh_minutes
            FROM user_preferences
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
        if not prefs.is_empty():
            row = prefs.to_dicts()[0]
            user_intervals["watchlist"] = int(row.get("watchlist_minutes", 15))
            user_intervals["news"] = int(row.get("news_minutes", 15))
            user_intervals["default"] = int(row.get("default_refresh_minutes", 15))
    except Exception:
        # Fallback if prefs not available
        user_intervals = {"watchlist": 15, "news": 15, "default": 15}

    schedule_list: list[ScheduleInfo] = []
    for name, config in beat_schedule.items():
        # Format schedule string
        schedule_seconds = config.get("schedule", 0)

        # For user-configurable tasks, show the effective interval not the polling interval
        if name == "refresh-watchlist-scores":
            minutes = user_intervals.get("watchlist", 15)
            schedule_str = f"Every {minutes} min (user-configured, polls every 60s)"
        elif name == "refresh-news-sentiment":
            minutes = user_intervals.get("news", 15)
            schedule_str = f"Every {minutes} min (user-configured, polls every 60s)"
        elif isinstance(schedule_seconds, (int, float)):
            # Static schedules - show as-is
            if schedule_seconds >= 86400:
                days = schedule_seconds / 86400
                schedule_str = f"every {days:.1f} day(s)" if days != 1 else "every day"
            elif schedule_seconds >= 3600:
                hours = schedule_seconds / 3600
                schedule_str = f"every {hours:.1f} hour(s)" if hours != 1 else "every hour"
            elif schedule_seconds >= 60:
                interval_minutes = schedule_seconds / 60
                schedule_str = (
                    f"every {interval_minutes:.1f} minute(s)"
                    if interval_minutes != 1
                    else "every minute"
                )
            else:
                schedule_str = f"every {schedule_seconds:.1f} second(s)"
        else:
            # For crontab schedules (future support)
            schedule_str = str(schedule_seconds)

        schedule_info = ScheduleInfo(
            name=name,
            task=config.get("task", "unknown"),
            schedule=schedule_str,
            last_run=None,  # Not available from beat_schedule config
            next_run=None,  # Would need to calculate from schedule
        )
        schedule_list.append(schedule_info)

    return schedule_list
