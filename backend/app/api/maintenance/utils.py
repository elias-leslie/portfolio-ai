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


def _extract_json_from_output(output: str) -> dict[str, object]:
    """Extract JSON object from script output that may contain log lines.

    Scripts output log lines followed by a JSON summary. This function
    finds and parses just the JSON portion.

    Args:
        output: Raw stdout from script (logs + JSON)

    Returns:
        Parsed JSON dict, or {"raw_output": output} if parsing fails
    """
    # Try parsing the whole output first (clean output)
    try:
        return json.loads(output)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        pass

    # Look for JSON object at end of output (after log lines)
    # Find the last occurrence of '{' that starts a complete JSON object
    lines = output.strip().split("\n")

    # Try to find JSON by looking for lines starting with '{'
    json_start_idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith("{"):
            json_start_idx = i
            break

    if json_start_idx >= 0:
        json_text = "\n".join(lines[json_start_idx:])
        try:
            return json.loads(json_text)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            pass

    # Fallback: return raw output
    return {"raw_output": output}


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

        # Parse JSON output from script (may be mixed with log lines)
        stdout_text = stdout.decode()
        summary = _extract_json_from_output(stdout_text)

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
