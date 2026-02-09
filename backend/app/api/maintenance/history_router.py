"""Maintenance history and logging router.

This module provides REST API endpoints for querying maintenance
execution history and last run summaries.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ...logging_config import get_logger
from .database import get_history_from_db, get_last_run_from_db, row_to_maintenance_result
from .models import LastRunSummary, MaintenanceHistory, MaintenanceResult

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# API Endpoints


@router.get("/last-run", response_model=LastRunSummary)
async def get_last_run() -> LastRunSummary:
    """Get last run details for each maintenance task.

    Returns all maintenance tasks dynamically (Hatchet + script-based).
    Task names are stored as-is from the maintenance_log table.

    Returns:
        LastRunSummary with most recent run for each task

    Raises:
        HTTPException: If database query fails
    """
    try:
        # Query last run for each task type (DISTINCT ON returns all unique task_name)
        result = get_last_run_from_db()

        # Build response - all tasks, dynamic
        tasks: dict[str, MaintenanceResult | None] = {}
        for row in result:
            task_result = row_to_maintenance_result(row)
            task_name: str = row[1]  # task_name column
            tasks[task_name] = task_result

        return LastRunSummary(tasks=tasks)

    except Exception as e:
        logger.error("get_last_run_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch last run data: {e!s}",
        ) from e


@router.get("/history", response_model=MaintenanceHistory)
async def get_history(
    task_name: str | None = None,
    limit: int = 50,
) -> MaintenanceHistory:
    """Get maintenance execution history.

    Args:
        task_name: Filter by task name (optional)
        limit: Maximum number of results (default: 50, max: 200)

    Returns:
        MaintenanceHistory with list of runs

    Raises:
        HTTPException: If database query fails
    """
    # Validate limit
    if limit < 1 or limit > 200:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 200",
        )

    try:
        # Query history
        result = get_history_from_db(task_name=task_name, limit=limit)

        # Build response
        runs = [row_to_maintenance_result(row) for row in result]

        return MaintenanceHistory(
            runs=runs,
            total=len(runs),
        )

    except Exception as e:
        logger.error("get_history_error", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch maintenance history: {e!s}",
        ) from e
