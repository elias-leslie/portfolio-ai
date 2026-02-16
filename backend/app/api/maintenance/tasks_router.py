"""Task management router.

This module provides REST API endpoints for triggering and monitoring
maintenance tasks.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...hatchet_app import get_admin_client
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
    task_to_workflow = {
        "vacuum_database_task": "portfolio-vacuum-db",
        "cleanup_old_news_task": "portfolio-cleanup-old-news",
        "cleanup_old_agent_runs_task": "portfolio-cleanup-agent-runs",
        "cleanup_orphaned_data_task": "portfolio-cleanup-orphaned-data",
        "cleanup_old_logs_task": "portfolio-cleanup-logs",
        "cleanup_temp_files_task": "portfolio-cleanup-temp",
        "cleanup_old_backups_task": "portfolio-cleanup-backups",
        "cleanup_old_models_task": "portfolio-cleanup-models",
        "cleanup_solution_state_task": "portfolio-cleanup-solution-state",
        "cleanup_cache_directories_task": "portfolio-cleanup-caches",
        "cleanup_old_versions": "portfolio-cleanup-versions",
        "cleanup_debug_captures": "portfolio-cleanup-debug-captures",
        "check_disk_space_task": "portfolio-check-disk",
        "get_database_size_task": "portfolio-db-size",
        "rotate_logs_task": "portfolio-rotate-logs",
    }

    valid_tasks = set(task_to_workflow.keys())

    if task_name not in valid_tasks:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task name. Valid tasks: {', '.join(valid_tasks)}",
        )

    # All tasks now support dry_run parameter
    tasks_with_dry_run = {
        # File cleanup tasks
        "cleanup_old_logs_task",
        "cleanup_temp_files_task",
        "cleanup_old_backups_task",
        "cleanup_old_models_task",
        "cleanup_solution_state_task",
        "cleanup_cache_directories_task",
        "rotate_logs_task",
        # Database cleanup tasks
        "cleanup_old_news_task",
        "cleanup_old_agent_runs_task",
        "cleanup_orphaned_data_task",
        "vacuum_database_task",
        # Artifact cleanup tasks
        "cleanup_old_versions",
        "cleanup_debug_captures",
    }

    try:
        admin = get_admin_client()
        workflow_name = task_to_workflow[task_name]

        input_data = {}
        if task_name in tasks_with_dry_run:
            input_data["dry_run"] = dry_run

        workflow_run = admin.run_workflow(workflow_name, input_data)

        logger.info(
            "maintenance_task_triggered",
            task_name=task_name,
            task_id=workflow_run.workflow_run_id,
            dry_run=dry_run,
        )

        response: TaskTriggerResponseDict = {
            "task_id": workflow_run.workflow_run_id,
            "task_name": task_name,
            "status": "triggered",
            "message": f"Task {task_name} has been triggered{' (dry run)' if dry_run else ''}",
        }

        if wait_for_result:
            response["status"] = "running"
            response["message"] = f"Task {task_name} running (polling not yet implemented)"

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
        task_id: Hatchet workflow run ID

    Returns:
        Dict with task status and result

    Raises:
        HTTPException: If status check fails
    """
    try:
        admin = get_admin_client()
        details = admin.get_details(task_id)

        return {
            "task_id": task_id,
            "state": details.status.value if details else "UNKNOWN",
            "ready": details.status.value in ("COMPLETED", "FAILED") if details else False,
            "successful": details.status.value == "COMPLETED" if details else None,
            "result": None,
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
