"""Database operations for maintenance logging.

This module centralizes all maintenance_log table operations to eliminate
duplication across routers.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ...logging_config import get_logger
from ...storage.connection import get_connection_manager
from .models import MaintenanceResult

logger = get_logger(__name__)


def create_maintenance_log_entry(task_name: str, dry_run: bool) -> int:
    """Create a new maintenance log entry with 'running' status.

    Args:
        task_name: Name of maintenance task
        dry_run: Whether task is running in dry-run mode

    Returns:
        ID of created log entry

    Raises:
        RuntimeError: If log entry creation fails
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

        task_id = result[0]
        return int(task_id) if task_id is not None else 0


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


def get_last_run_from_db() -> list[tuple[Any, ...]]:
    """Query last run for each task type.

    Returns:
        List of database rows with last run data

    Raises:
        Exception: If database query fails
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        return conn.execute(
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


def get_history_from_db(
    task_name: str | None = None,
    limit: int = 50,
) -> list[tuple[Any, ...]]:
    """Query maintenance execution history.

    Args:
        task_name: Filter by task name (optional)
        limit: Maximum number of results

    Returns:
        List of database rows with history data

    Raises:
        Exception: If database query fails
    """
    conn_mgr = get_connection_manager()

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

        return conn.execute(query, [str(p) if p is not None else None for p in params]).fetchall()


def row_to_maintenance_result(row: tuple[Any, ...]) -> MaintenanceResult:
    """Convert database row to MaintenanceResult model.

    Args:
        row: Database row tuple (id, task_name, started_at, completed_at, status, dry_run, summary, error_message)

    Returns:
        MaintenanceResult model instance
    """
    # Handle summary - may be a dict (JSONB) or string (JSON text)
    summary = row[6]
    if summary is not None and isinstance(summary, str):
        summary = json.loads(summary)

    return MaintenanceResult(
        task_id=row[0],
        task_name=row[1],
        started_at=row[2],
        completed_at=row[3],
        status=row[4],
        dry_run=row[5],
        summary=summary,
        error_message=row[7],
    )
