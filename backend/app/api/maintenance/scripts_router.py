"""Script-based maintenance operations router.

This module provides REST API endpoints for triggering maintenance scripts
(cleanup_old_news.py, vacuum_database.py, validate_data_integrity.py).
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

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


# Request Models


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
        backend_dir = Path(__file__).parent.parent.parent.parent
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
