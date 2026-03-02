"""Task management router.

This module provides REST API endpoints for triggering and monitoring
maintenance tasks.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...logging_config import get_logger
from ..maintenance_types import TaskStatusResponseDict, TaskTriggerResponseDict
from .tasks_helpers import TASK_TO_WORKFLOW, get_status, run_trigger

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
    if task_name not in TASK_TO_WORKFLOW:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task name. Valid tasks: {', '.join(TASK_TO_WORKFLOW)}",
        )

    try:
        return run_trigger(task_name, dry_run, wait_for_result)
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
        task_id: Hatchet workflow run ID

    Returns:
        Dict with task status and result

    Raises:
        HTTPException: If status check fails
    """
    try:
        return get_status(task_id)
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
