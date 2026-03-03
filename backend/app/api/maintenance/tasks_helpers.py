"""Helper constants and functions for the tasks router."""

from __future__ import annotations

from ...hatchet_app import get_admin_client
from ...logging_config import get_logger
from ..maintenance_types import TaskStatusResponseDict, TaskTriggerResponseDict

logger = get_logger(__name__)

TASK_TO_WORKFLOW: dict[str, str] = {
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

TASKS_WITH_DRY_RUN: frozenset[str] = frozenset(
    {
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
)


def run_trigger(
    task_name: str,
    dry_run: bool,
    wait_for_result: bool,
) -> TaskTriggerResponseDict:
    """Trigger a maintenance task workflow and return the initial response."""
    admin = get_admin_client()
    workflow_name = TASK_TO_WORKFLOW[task_name]

    input_data: dict[str, bool] = {}
    if task_name in TASKS_WITH_DRY_RUN:
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
        logger.warning(
            "wait_for_result_not_implemented",
            task_name=task_name,
            message="wait_for_result=True has no effect; polling is not implemented",
        )
        response["status"] = "running"
        response["message"] = f"Task {task_name} running (polling not yet implemented)"

    return response


def get_status(task_id: str) -> TaskStatusResponseDict:
    """Fetch workflow run status from Hatchet and return a normalised dict."""
    admin = get_admin_client()
    details = admin.get_details(task_id)

    if not details:
        return {
            "task_id": task_id,
            "state": "UNKNOWN",
            "ready": False,
            "successful": None,
            "result": None,
        }

    state = details.status.value
    is_terminal = state in ("COMPLETED", "FAILED")
    return {
        "task_id": task_id,
        "state": state,
        "ready": is_terminal,
        "successful": state == "COMPLETED" if is_terminal else None,
        "result": None,
    }
