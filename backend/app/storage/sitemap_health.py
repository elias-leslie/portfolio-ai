"""Sitemap health check storage operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from ..logging_config import get_logger
from .connection import ConnectionManager

logger = get_logger(__name__)


def get_health_summary(conn_mgr: ConnectionManager) -> dict[str, object]:
    """Get aggregate health statistics.

    Returns:
        Dict with total, healthy, warning, error, unknown counts and by_port breakdown.
    """
    with conn_mgr.connection() as conn:
        result = conn.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE health_status = 'healthy') as healthy,
                COUNT(*) FILTER (WHERE health_status = 'warning') as warning,
                COUNT(*) FILTER (WHERE health_status = 'error') as error,
                COUNT(*) FILTER (WHERE health_status = 'unknown' OR health_status IS NULL) as unknown
            FROM sitemap_entries
        """)
        row = result.fetchone()
        by_port = _get_health_by_port(conn_mgr)

    return {
        "total": row[0] if row else 0,
        "healthy": row[1] if row else 0,
        "warning": row[2] if row else 0,
        "error": row[3] if row else 0,
        "unknown": row[4] if row else 0,
        "by_port": by_port,
    }


def _get_health_by_port(conn_mgr: ConnectionManager) -> dict[str, object]:
    """Get health counts grouped by port."""
    with conn_mgr.connection() as conn:
        port_result = conn.execute("""
            SELECT port,
                COUNT(*) FILTER (WHERE health_status = 'healthy') as healthy,
                COUNT(*) FILTER (WHERE health_status = 'warning') as warning,
                COUNT(*) FILTER (WHERE health_status = 'error') as error,
                COUNT(*) FILTER (WHERE health_status = 'unknown' OR health_status IS NULL) as unknown
            FROM sitemap_entries
            GROUP BY port
        """)
        by_port: dict[str, object] = {}
        for port_row in port_result.fetchall():
            by_port[str(port_row[0])] = {
                "healthy": port_row[1],
                "warning": port_row[2],
                "error": port_row[3],
                "unknown": port_row[4],
            }
        return by_port


def cleanup_old_history(conn_mgr: ConnectionManager, days: int = 7) -> int:
    """Delete health history older than specified days.

    Args:
        conn_mgr: Database connection manager.
        days: Number of days to keep.

    Returns:
        Number of rows deleted.
    """
    with conn_mgr.connection() as conn:
        result = conn.execute(
            """
            DELETE FROM sitemap_health_history
            WHERE checked_at < NOW() - INTERVAL '%s days'
            RETURNING id
            """,
            [days],
        )
        deleted = len(result.fetchall())
        conn.commit()

    logger.info("sitemap_cleanup_history", deleted=deleted, retention_days=days)
    return deleted


def get_history_stats(conn_mgr: ConnectionManager) -> dict[str, object]:
    """Get health history statistics for maintenance UI.

    Returns:
        Dict with total_rows, oldest_entry, storage_estimate.
    """
    with conn_mgr.connection() as conn:
        result = conn.execute("""
            SELECT
                COUNT(*) as total_rows,
                MIN(checked_at) as oldest_entry,
                pg_size_pretty(pg_total_relation_size('sitemap_health_history')) as storage_size
            FROM sitemap_health_history
        """)
        row = result.fetchone()

    if not row:
        return {"total_rows": 0, "oldest_entry": None, "storage_size": "0 bytes"}

    oldest = row[1]
    return {
        "total_rows": row[0] if row[0] else 0,
        "oldest_entry": oldest.isoformat() if isinstance(oldest, datetime) else None,
        "storage_size": row[2] if row[2] else "0 bytes",
    }


def update_health_status(
    conn_mgr: ConnectionManager,
    entry_id: int,
    health_status: str,
    http_status: int | None = None,
    response_time_ms: float | None = None,
    console_errors: int | None = None,
    console_warnings: int | None = None,
    last_error_message: str | None = None,
) -> None:
    """Update health check results for an entry.

    Args:
        conn_mgr: Database connection manager.
        entry_id: Entry ID to update.
        health_status: New health status.
        http_status: HTTP response code.
        response_time_ms: Response time in milliseconds.
        console_errors: Number of console errors.
        console_warnings: Number of console warnings.
        last_error_message: Error message if any.
    """
    with conn_mgr.connection() as conn:
        conn.execute(
            """
            UPDATE sitemap_entries
            SET health_status = %s,
                http_status = %s,
                response_time_ms = %s,
                console_errors = %s,
                console_warnings = %s,
                last_error_message = %s,
                last_checked_at = NOW()
            WHERE id = %s
            """,
            [
                health_status,
                http_status,
                response_time_ms,
                console_errors,
                console_warnings,
                last_error_message,
                entry_id,
            ],
        )
        conn.commit()


def insert_health_history(
    conn_mgr: ConnectionManager,
    entry_id: int,
    health_status: str,
    http_status: int | None = None,
    response_time_ms: float | None = None,
    console_errors: int | None = None,
    console_warnings: int | None = None,
    error_message: str | None = None,
) -> None:
    """Insert a health history record.

    Args:
        conn_mgr: Database connection manager.
        entry_id: Entry ID.
        health_status: Health status.
        http_status: HTTP response code.
        response_time_ms: Response time in milliseconds.
        console_errors: Number of console errors.
        console_warnings: Number of console warnings.
        error_message: Error message if any.
    """
    with conn_mgr.connection() as conn:
        conn.execute(
            """
            INSERT INTO sitemap_health_history
            (entry_id, health_status, http_status, response_time_ms,
             console_errors, console_warnings, error_message)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            [
                entry_id,
                health_status,
                http_status,
                response_time_ms,
                console_errors,
                console_warnings,
                error_message,
            ],
        )
        conn.commit()


def save_health_check_result(
    conn_mgr: ConnectionManager,
    entry_id: int,
    health_status: str,
    console_errors: int,
    console_warnings: int,
    http_status: int | None,
    response_time_ms: float | None,
    last_error_message: str | None,
    error_details: dict[str, object] | None = None,
) -> None:
    """Save health check result to database (entry update + history insert).

    Args:
        conn_mgr: Database connection manager.
        entry_id: ID of sitemap entry.
        health_status: Health status value.
        console_errors: Number of console errors.
        console_warnings: Number of console warnings.
        http_status: HTTP response code.
        response_time_ms: Response time in milliseconds.
        last_error_message: Error message if any.
        error_details: Additional error details for history.
    """
    with conn_mgr.connection() as conn:
        conn.execute(
            """
            UPDATE sitemap_entries SET
                health_status = %s,
                console_errors = %s,
                console_warnings = %s,
                http_status = %s,
                response_time_ms = %s,
                last_error_message = %s,
                last_checked_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            [
                health_status,
                console_errors,
                console_warnings,
                http_status,
                response_time_ms,
                last_error_message,
                entry_id,
            ],
        )
        conn.execute(
            """
            INSERT INTO sitemap_health_history
                (sitemap_entry_id, checked_at, health_status, console_errors, console_warnings,
                 http_status, response_time_ms, error_details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                entry_id,
                datetime.now(UTC),
                health_status,
                console_errors,
                console_warnings,
                http_status,
                response_time_ms,
                json.dumps(error_details) if error_details else None,
            ],
        )
        conn.commit()
