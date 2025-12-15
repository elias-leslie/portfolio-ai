"""Celery task management router.

This module provides REST API endpoints for triggering and monitoring
Celery-based maintenance tasks.
"""

from __future__ import annotations

from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException

from ...celery_app import celery_app
from ...logging_config import get_logger
from ..maintenance_types import TaskStatusResponseDict, TaskTriggerResponseDict

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# API Endpoints


@router.post("/trigger/{task_name}")
async def trigger_maintenance_task(
    task_name: str,
    dry_run: bool = False,
    wait_for_result: bool = False,
    timeout: int = 30,
) -> TaskTriggerResponseDict:
    """Manually trigger a specific maintenance task.

    Args:
        task_name: Name of the task to trigger (e.g., 'cleanup_old_logs_task')
        dry_run: If True, preview changes without executing (tasks that support it)
        wait_for_result: If True, wait for task to complete and return result
        timeout: Max seconds to wait for result (only if wait_for_result=True)

    Returns:
        Dict with task_id, status, and optionally result (if wait_for_result)

    Raises:
        HTTPException: If task name is invalid or trigger fails
    """
    # Validate task name
    valid_tasks = {
        "vacuum_database_task",
        "cleanup_old_news_task",
        "cleanup_old_agent_runs_task",
        "cleanup_orphaned_data_task",
        "cleanup_old_logs_task",
        "cleanup_temp_files_task",
        "cleanup_old_backups_task",
        "cleanup_old_models_task",
        "cleanup_solution_state_task",
        "cleanup_cache_directories_task",  # Manual-only: Python/Next.js/Claude caches
        "cleanup_old_versions",  # Artifact version cleanup (keep 5 per criterion)
        "cleanup_debug_captures",  # Debug screenshot cleanup (>7 days)
        "check_disk_space_task",
        "get_database_size_task",
        "rotate_logs_task",
    }

    if task_name not in valid_tasks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task name. Valid tasks: {', '.join(valid_tasks)}",
        )

    # Only these tasks support dry_run parameter
    tasks_with_dry_run = {
        "cleanup_cache_directories_task",
        "cleanup_old_versions",
        "cleanup_debug_captures",
    }

    try:
        # Build kwargs for task - only pass dry_run for tasks that support it
        kwargs = {}
        if dry_run and task_name in tasks_with_dry_run:
            kwargs["dry_run"] = True

        # Trigger the Celery task with optional kwargs
        task = celery_app.send_task(task_name, kwargs=kwargs if kwargs else None)

        logger.info(
            "maintenance_task_triggered",
            task_name=task_name,
            task_id=task.id,
            dry_run=dry_run,
        )

        response: TaskTriggerResponseDict = {
            "task_id": task.id,
            "task_name": task_name,
            "status": "triggered",
            "message": f"Task {task_name} has been triggered{' (dry run)' if dry_run else ''}",
        }

        # Optionally wait for result (useful for dry-run previews)
        if wait_for_result:
            try:
                result = task.get(timeout=timeout)
                response["status"] = "completed"
                response["result"] = result
                response["message"] = f"Task {task_name} completed{' (dry run)' if dry_run else ''}"
            except TimeoutError:
                response["status"] = "timeout"
                response["message"] = f"Task {task_name} is still running after {timeout}s"

        return response

    except Exception as e:
        logger.error(
            "trigger_maintenance_task_failed",
            task_name=task_name,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to trigger task {task_name}: {e!s}",
        ) from e


@router.get("/status/{task_id}")
async def get_task_status(task_id: str) -> TaskStatusResponseDict:
    """Get status of a running maintenance task.

    Args:
        task_id: Celery task ID

    Returns:
        Dict with task status and result

    Raises:
        HTTPException: If status check fails
    """
    try:
        result = AsyncResult(task_id, app=celery_app)

        return {
            "task_id": task_id,
            "state": result.state,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "result": result.result if result.ready() else None,
        }

    except Exception as e:
        logger.error(
            "get_task_status_failed",
            task_id=task_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {e!s}",
        ) from e
