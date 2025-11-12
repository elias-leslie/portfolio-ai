"""Maintenance API endpoints for database operations.

This module provides REST API endpoints for triggering and monitoring
database maintenance tasks like cleanup, vacuum, and integrity validation.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# Request/Response Models


class CleanupNewsRequest(BaseModel):
    """Request model for cleanup-news endpoint."""

    dry_run: bool = Field(default=True, description="Preview mode without actual deletion")
    days: int = Field(default=90, ge=1, le=365, description="Delete news older than N days")


class VacuumDatabaseRequest(BaseModel):
    """Request model for vacuum-database endpoint."""

    dry_run: bool = Field(default=False, description="Preview mode without actual vacuum")
    tables: list[str] | None = Field(
        default=None, description="Specific tables to vacuum (None = all)"
    )


class ValidateIntegrityRequest(BaseModel):
    """Request model for validate-integrity endpoint."""

    dry_run: bool = Field(default=True, description="Report-only mode without fixes")


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


# Helper Functions


def create_maintenance_log_entry(task_name: str, dry_run: bool) -> int:
    """Create a new maintenance log entry with 'running' status.

    Args:
        task_name: Name of maintenance task
        dry_run: Whether task is running in dry-run mode

    Returns:
        ID of created log entry
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        result = conn.execute(
            """
            INSERT INTO maintenance_log (task_name, started_at, status, dry_run)
            VALUES (?, ?, 'running', ?)
            RETURNING id
            """,
            [task_name, datetime.now(UTC), dry_run],
        ).fetchone()

        conn.commit()

        if not result:
            raise RuntimeError("Failed to create maintenance log entry")

        return int(result[0])


def update_maintenance_log_entry(
    task_id: int,
    status: str,
    summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """Update maintenance log entry with completion status.

    Args:
        task_id: Maintenance log entry ID
        status: Final status (success/error)
        summary: Task execution summary
        error_message: Error message if failed
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        conn.execute(
            """
            UPDATE maintenance_log
            SET completed_at = ?,
                status = ?,
                summary = ?,
                error_message = ?
            WHERE id = ?
            """,
            [
                datetime.now(UTC),
                status,
                json.dumps(summary) if summary else None,
                error_message,
                task_id,
            ],
        )

        conn.commit()


async def run_maintenance_script(
    script_name: str,
    args: list[str],
    task_name: str,
    dry_run: bool,
) -> MaintenanceResult:
    """Run a maintenance script as subprocess and track in database.

    Args:
        script_name: Script filename (e.g., 'cleanup_old_news.py')
        args: Command-line arguments for script
        task_name: Task name for logging
        dry_run: Whether running in dry-run mode

    Returns:
        MaintenanceResult with execution details

    Raises:
        HTTPException: If script execution fails
    """
    # Create log entry
    task_id = create_maintenance_log_entry(task_name, dry_run)

    logger.info(
        "maintenance_script_started",
        task_id=task_id,
        task_name=task_name,
        script=script_name,
        args=args,
    )

    try:
        # Build command to run script as module
        backend_dir = Path(__file__).parent.parent.parent
        cmd = [
            sys.executable,
            "-m",
            f"app.scripts.{script_name.replace('.py', '')}",
            *args,
        ]

        # Run script and capture output
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(backend_dir),
        )

        stdout, stderr = await result.communicate()

        # Parse JSON output from script
        try:
            summary = json.loads(stdout.decode())
        except json.JSONDecodeError:
            summary = {"raw_output": stdout.decode()}

        # Check exit code
        if result.returncode == 0:
            status = "success"
            error_message = None
            logger.info(
                "maintenance_script_success",
                task_id=task_id,
                task_name=task_name,
                summary=summary,
            )
        else:
            status = "error"
            error_message = stderr.decode() or "Script execution failed"
            logger.error(
                "maintenance_script_error",
                task_id=task_id,
                task_name=task_name,
                error=error_message,
                exit_code=result.returncode,
            )

        # Update log entry
        update_maintenance_log_entry(
            task_id=task_id,
            status=status,
            summary=summary,
            error_message=error_message,
        )

        # Return result
        return MaintenanceResult(
            task_id=task_id,
            task_name=task_name,
            status=status,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            dry_run=dry_run,
            summary=summary,
            error_message=error_message,
        )

    except Exception as e:
        error_msg = str(e)
        logger.error(
            "maintenance_script_exception",
            task_id=task_id,
            task_name=task_name,
            error=error_msg,
            exc_info=True,
        )

        # Update log entry with error
        update_maintenance_log_entry(
            task_id=task_id,
            status="error",
            error_message=error_msg,
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute maintenance task: {error_msg}",
        ) from e


# API Endpoints


@router.post("/cleanup-news", response_model=MaintenanceResult)
async def cleanup_news(request: CleanupNewsRequest) -> MaintenanceResult:
    """Trigger cleanup of old news articles.

    Args:
        request: Cleanup configuration (days, dry_run)

    Returns:
        MaintenanceResult with execution details

    Raises:
        HTTPException: If cleanup fails
    """
    args = ["--days", str(request.days)]

    if request.dry_run:
        args.append("--dry-run")

    return await run_maintenance_script(
        script_name="cleanup_old_news.py",
        args=args,
        task_name="cleanup_news",
        dry_run=request.dry_run,
    )


@router.post("/vacuum-database", response_model=MaintenanceResult)
async def vacuum_database(request: VacuumDatabaseRequest) -> MaintenanceResult:
    """Trigger database vacuum operation.

    Args:
        request: Vacuum configuration (tables, dry_run)

    Returns:
        MaintenanceResult with execution details

    Raises:
        HTTPException: If vacuum fails
    """
    args = []

    if request.dry_run:
        args.append("--dry-run")

    if request.tables:
        args.append("--tables")
        args.extend(request.tables)

    return await run_maintenance_script(
        script_name="vacuum_database.py",
        args=args,
        task_name="vacuum_database",
        dry_run=request.dry_run,
    )


@router.post("/validate-integrity", response_model=MaintenanceResult)
async def validate_integrity(request: ValidateIntegrityRequest) -> MaintenanceResult:
    """Trigger data integrity validation.

    Args:
        request: Validation configuration (dry_run)

    Returns:
        MaintenanceResult with execution details

    Raises:
        HTTPException: If validation fails
    """
    args = []

    if request.dry_run:
        args.append("--dry-run")
    else:
        args.append("--fix")

    return await run_maintenance_script(
        script_name="validate_data_integrity.py",
        args=args,
        task_name="validate_integrity",
        dry_run=request.dry_run,
    )


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
