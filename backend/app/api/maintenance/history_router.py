"""Maintenance history and logging router.

This module provides REST API endpoints for querying maintenance
execution history and last run summaries.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# Response Models


class MaintenanceResult(BaseModel):
    """Response model for maintenance task execution."""

    task_id: int = Field(description="Maintenance log entry ID")
    task_name: str = Field(description="Task name")
    status: str = Field(description="Execution status (running/success/error)")
    started_at: datetime = Field(description="Task start timestamp")
    completed_at: datetime | None = Field(description="Task completion timestamp")
    dry_run: bool = Field(description="Whether task ran in dry-run mode")
    summary: dict[str, Any] | None = Field(description="Task execution summary")
    error_message: str | None = Field(default=None, description="Error message if failed")


class MaintenanceHistory(BaseModel):
    """Response model for maintenance history."""

    runs: list[MaintenanceResult] = Field(description="List of maintenance runs")
    total: int = Field(description="Total number of runs")


class LastRunSummary(BaseModel):
    """Response model for last-run summary."""

    cleanup_news: MaintenanceResult | None = Field(description="Last cleanup run")
    vacuum_database: MaintenanceResult | None = Field(description="Last vacuum run")
    validate_integrity: MaintenanceResult | None = Field(description="Last validation run")


# API Endpoints


@router.get("/last-run", response_model=LastRunSummary)
async def get_last_run() -> LastRunSummary:
    """Get last run details for each maintenance task.

    Returns:
        LastRunSummary with most recent run for each task

    Raises:
        HTTPException: If database query fails
    """
    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Query last run for each task type
            result = conn.execute(
                """
                SELECT DISTINCT ON (task_name)
                    id,
                    task_name,
                    started_at,
                    completed_at,
                    status,
                    dry_run,
                    summary,
                    error_message
                FROM maintenance_log
                ORDER BY task_name, started_at DESC
                """
            ).fetchall()

            # Build response
            last_runs = {}

            for row in result:
                task_result = MaintenanceResult(
                    task_id=row[0],
                    task_name=row[1],
                    started_at=row[2],
                    completed_at=row[3],
                    status=row[4],
                    dry_run=row[5],
                    summary=json.loads(row[6]) if row[6] else None,
                    error_message=row[7],
                )

                last_runs[row[1]] = task_result

            return LastRunSummary(
                cleanup_news=last_runs.get("cleanup_news"),
                vacuum_database=last_runs.get("vacuum_database"),
                validate_integrity=last_runs.get("validate_integrity"),
            )

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

    conn_mgr = get_connection_manager()

    try:
        with conn_mgr.connection() as conn:
            # Build query with optional filter
            if task_name:
                query = """
                    SELECT id, task_name, started_at, completed_at, status, dry_run, summary, error_message
                    FROM maintenance_log
                    WHERE task_name = ?
                    ORDER BY started_at DESC
                    LIMIT ?
                """
                params = [task_name, limit]
            else:
                query = """
                    SELECT id, task_name, started_at, completed_at, status, dry_run, summary, error_message
                    FROM maintenance_log
                    ORDER BY started_at DESC
                    LIMIT ?
                """
                params = [limit]

            result = conn.execute(query, params).fetchall()

            # Build response
            runs = [
                MaintenanceResult(
                    task_id=row[0],
                    task_name=row[1],
                    started_at=row[2],
                    completed_at=row[3],
                    status=row[4],
                    dry_run=row[5],
                    summary=json.loads(row[6]) if row[6] else None,
                    error_message=row[7],
                )
                for row in result
            ]

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
