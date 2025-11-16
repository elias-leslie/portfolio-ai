"""Celery task management router.

This module provides REST API endpoints for triggering and monitoring
Celery-based maintenance tasks.
"""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult  # type: ignore[import-untyped]
from fastapi import APIRouter, HTTPException

from ...celery_app import celery_app
from ...logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# API Endpoints


@router.post("/trigger/{task_name}")
async def trigger_maintenance_task(task_name: str) -> dict[str, Any]:
    """Manually trigger a specific maintenance task.

    Args:
        task_name: Name of the task to trigger (e.g., 'cleanup_old_logs_task')

    Returns:
        Dict with task_id and status

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
        "check_disk_space_task",
        "get_database_size_task",
    }

    if task_name not in valid_tasks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task name. Valid tasks: {', '.join(valid_tasks)}",
        )

    try:
        # Trigger the Celery task
        task = celery_app.send_task(task_name)

        logger.info(
            "maintenance_task_triggered",
            task_name=task_name,
            task_id=task.id,
        )

        return {
            "task_id": task.id,
            "task_name": task_name,
            "status": "triggered",
            "message": f"Task {task_name} has been triggered successfully",
        }

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
async def get_task_status(task_id: str) -> dict[str, Any]:
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
