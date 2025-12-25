"""Sitemap storage layer for database operations.

Extracted from sitemap_service.py to separate concerns:
- Service layer handles discovery, health checks, business logic
- Storage layer handles CRUD operations and data access

This module provides:
- SitemapEntry dataclass for type-safe row representation
- SitemapStorage class for all sitemap database operations
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from ..logging_config import get_logger
from .connection import ConnectionManager, get_connection_manager

logger = get_logger(__name__)


@dataclass
class SitemapEntry:
    """Type-safe representation of a sitemap entry row."""

    id: int
    port: int
    path: str
    method: str | None
    entry_type: str | None
    source: str | None
    title: str | None
    parent_path: str | None
    health_status: str | None
    console_errors: int | None
    console_warnings: int | None
    http_status: int | None
    response_time_ms: float | None
    last_error_message: str | None
    artifact_id: str | None
    last_checked_at: datetime | None
    discovered_at: datetime | None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary with ISO-formatted dates."""
        return {
            "id": self.id,
            "port": self.port,
            "path": self.path,
            "method": self.method,
            "entry_type": self.entry_type,
            "source": self.source,
            "title": self.title,
            "parent_path": self.parent_path,
            "health_status": self.health_status,
            "console_errors": self.console_errors,
            "console_warnings": self.console_warnings,
            "http_status": self.http_status,
            "response_time_ms": self.response_time_ms,
            "last_error_message": self.last_error_message,
            "artifact_id": self.artifact_id,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
        }


def _row_to_entry(row: tuple[Any, ...]) -> SitemapEntry:
    """Convert database row tuple to SitemapEntry."""
    return SitemapEntry(
        id=row[0],
        port=row[1],
        path=row[2],
        method=row[3],
        entry_type=row[4],
        source=row[5],
        title=row[6],
        parent_path=row[7],
        health_status=row[8],
        console_errors=row[9],
        console_warnings=row[10],
        http_status=row[11],
        response_time_ms=row[12],
        last_error_message=row[13],
        artifact_id=row[14],
        last_checked_at=row[15] if isinstance(row[15], datetime) else None,
        discovered_at=row[16] if isinstance(row[16], datetime) else None,
    )


# Standard SELECT columns for sitemap entries
ENTRY_COLUMNS = """
    id, port, path, method, entry_type, source, title, parent_path,
    health_status, console_errors, console_warnings, http_status,
    response_time_ms, last_error_message, artifact_id,
    last_checked_at, discovered_at
"""


class SitemapStorage:
    """Storage layer for sitemap entries and health history."""

    def __init__(self, conn_mgr: ConnectionManager | None = None) -> None:
        """Initialize with connection manager.

        Args:
            conn_mgr: Optional connection manager. Uses singleton if not provided.
        """
        self.conn_mgr = conn_mgr or get_connection_manager()

    def get_entries(
        self,
        port: int | None = None,
        health_status: str | None = None,
        entry_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get paginated sitemap entries with optional filters.

        Args:
            port: Filter by port
            health_status: Filter by health status
            entry_type: Filter by entry type
            limit: Max results
            offset: Pagination offset

        Returns:
            Tuple of (entries list, total count)
        """
        conditions = []
        params: list[Any] = []

        if port is not None:
            conditions.append("port = %s")
            params.append(port)
        if health_status:
            conditions.append("health_status = %s")
            params.append(health_status)
        if entry_type:
            conditions.append("entry_type = %s")
            params.append(entry_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        with self.conn_mgr.connection() as conn:
            # Get total count
            count_result = conn.execute(
                f"SELECT COUNT(*) FROM sitemap_entries WHERE {where_clause}",
                params,
            )
            row = count_result.fetchone()
            total: int = int(row[0]) if row and row[0] is not None else 0

            # Get entries
            result = conn.execute(
                f"""
                SELECT {ENTRY_COLUMNS}
                FROM sitemap_entries
                WHERE {where_clause}
                ORDER BY port, path
                LIMIT %s OFFSET %s
                """,
                [*params, limit, offset],
            )

            entries = [_row_to_entry(row).to_dict() for row in result.fetchall()]
            return entries, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        """Get single entry by ID.

        Args:
            entry_id: Entry ID

        Returns:
            Entry dict or None
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute(
                f"""
                SELECT {ENTRY_COLUMNS}
                FROM sitemap_entries
                WHERE id = %s
                """,
                [entry_id],
            )

            row = result.fetchone()
            if not row:
                return None

            return _row_to_entry(row).to_dict()

    def get_health_summary(self) -> dict[str, Any]:
        """Get aggregate health statistics.

        Returns:
            Dict with total, healthy, warning, error, unknown counts
        """
        with self.conn_mgr.connection() as conn:
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

            # Get counts by port
            port_result = conn.execute("""
                SELECT port,
                    COUNT(*) FILTER (WHERE health_status = 'healthy') as healthy,
                    COUNT(*) FILTER (WHERE health_status = 'warning') as warning,
                    COUNT(*) FILTER (WHERE health_status = 'error') as error,
                    COUNT(*) FILTER (WHERE health_status = 'unknown' OR health_status IS NULL) as unknown
                FROM sitemap_entries
                GROUP BY port
            """)

            by_port = {}
            for port_row in port_result.fetchall():
                by_port[str(port_row[0])] = {
                    "healthy": port_row[1],
                    "warning": port_row[2],
                    "error": port_row[3],
                    "unknown": port_row[4],
                }

            return {
                "total": row[0] if row else 0,
                "healthy": row[1] if row else 0,
                "warning": row[2] if row else 0,
                "error": row[3] if row else 0,
                "unknown": row[4] if row else 0,
                "by_port": by_port,
            }

    def register_entry(
        self,
        port: int,
        path: str,
        method: str = "GET",
        entry_type: str = "manual",
        title: str | None = None,
    ) -> dict[str, Any] | None:
        """Manually register a new sitemap entry.

        Args:
            port: Port number
            path: URL path
            method: HTTP method
            entry_type: Entry type
            title: Optional title

        Returns:
            Created entry dict
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute(
                """
                INSERT INTO sitemap_entries (port, path, method, entry_type, source, title)
                VALUES (%s, %s, %s, %s, 'manual', %s)
                RETURNING id
                """,
                [port, path, method, entry_type, title],
            )

            row = result.fetchone()
            entry_id = int(row[0]) if row and row[0] is not None else None
            conn.commit()

        if entry_id is not None:
            return self.get_entry(entry_id)
        return None

    def delete_entry(self, entry_id: int) -> bool:
        """Remove a sitemap entry.

        Args:
            entry_id: Entry ID to delete

        Returns:
            True if deleted, False if not found
        """
        with self.conn_mgr.connection() as conn:
            result = conn.execute(
                "DELETE FROM sitemap_entries WHERE id = %s RETURNING id",
                [entry_id],
            )
            deleted = result.fetchone() is not None
            conn.commit()
            return deleted

    def cleanup_old_history(self, days: int = 7) -> int:
        """Delete health history older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of rows deleted
        """
        with self.conn_mgr.connection() as conn:
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

    def get_history_stats(self) -> dict[str, Any]:
        """Get health history statistics for maintenance UI.

        Returns:
            Dict with total_rows, oldest_entry, storage_estimate
        """
        with self.conn_mgr.connection() as conn:
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
        self,
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
            entry_id: Entry ID to update
            health_status: New health status
            http_status: HTTP response code
            response_time_ms: Response time in milliseconds
            console_errors: Number of console errors
            console_warnings: Number of console warnings
            last_error_message: Error message if any
        """
        with self.conn_mgr.connection() as conn:
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
        self,
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
            entry_id: Entry ID
            health_status: Health status
            http_status: HTTP response code
            response_time_ms: Response time in milliseconds
            console_errors: Number of console errors
            console_warnings: Number of console warnings
            error_message: Error message if any
        """
        with self.conn_mgr.connection() as conn:
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


# Singleton instance
_storage_instance: SitemapStorage | None = None


def get_sitemap_storage() -> SitemapStorage:
    """Get singleton instance of sitemap storage."""
    global _storage_instance  # noqa: PLW0603
    if _storage_instance is None:
        _storage_instance = SitemapStorage()
    return _storage_instance
