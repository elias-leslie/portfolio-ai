"""Shared utility functions for maintenance operations.

This module provides common utilities for executing maintenance scripts
and handling execution results.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException

from ...logging_config import get_logger
from .database import create_maintenance_log_entry, update_maintenance_log_entry
from .models import MaintenanceResult

logger = get_logger(__name__)


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
