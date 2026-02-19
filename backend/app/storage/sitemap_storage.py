"""Sitemap storage layer for database operations.

Extracted from sitemap_service.py to separate concerns:
- Service layer handles discovery, health checks, business logic
- Storage layer handles CRUD operations and data access

This module provides:
- SitemapEntry dataclass for type-safe row representation
- SitemapStorage class for all sitemap database operations
"""

from __future__ import annotations

from .connection import ConnectionManager, get_connection_manager
from .sitemap_entries import (
    bulk_save_discovered_entries,
    delete_entry,
    get_entries,
    get_entry,
    register_entry,
)
from .sitemap_entry import ENTRY_COLUMNS, SitemapEntry
from .sitemap_health import (
    cleanup_old_history,
    get_health_summary,
    get_history_stats,
    save_health_check_result,
)

__all__ = [
    "ENTRY_COLUMNS",
    "SitemapEntry",
    "SitemapStorage",
    "get_sitemap_storage",
]


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
    ) -> tuple[list[dict[str, object]], int]:
        """Get paginated sitemap entries with optional filters."""
        return get_entries(self.conn_mgr, port, health_status, entry_type, limit, offset)

    def get_entry(self, entry_id: int) -> dict[str, object] | None:
        """Get single entry by ID."""
        return get_entry(self.conn_mgr, entry_id)

    def get_health_summary(self) -> dict[str, object]:
        """Get aggregate health statistics."""
        return get_health_summary(self.conn_mgr)

    def register_entry(
        self,
        port: int,
        path: str,
        method: str = "GET",
        entry_type: str = "manual",
        title: str | None = None,
    ) -> dict[str, object] | None:
        """Manually register a new sitemap entry."""
        return register_entry(self.conn_mgr, port, path, method, entry_type, title)

    def delete_entry(self, entry_id: int) -> bool:
        """Remove a sitemap entry."""
        return delete_entry(self.conn_mgr, entry_id)

    def cleanup_old_history(self, days: int = 7) -> int:
        """Delete health history older than specified days."""
        return cleanup_old_history(self.conn_mgr, days)

    def get_history_stats(self) -> dict[str, object]:
        """Get health history statistics for maintenance UI."""
        return get_history_stats(self.conn_mgr)

    def bulk_save_discovered_entries(self, entries: list[dict[str, object]]) -> int:
        """Bulk save discovered sitemap entries with upsert logic."""
        return bulk_save_discovered_entries(self.conn_mgr, entries)

    def save_health_check_result(
        self,
        entry_id: int,
        health_status: str,
        console_errors: int,
        console_warnings: int,
        http_status: int | None,
        response_time_ms: float | None,
        last_error_message: str | None,
        error_details: dict[str, object] | None = None,
    ) -> None:
        """Save health check result to database (entry update + history)."""
        save_health_check_result(
            self.conn_mgr,
            entry_id,
            health_status,
            console_errors,
            console_warnings,
            http_status,
            response_time_ms,
            last_error_message,
            error_details,
        )


# Singleton instance
_storage_instance: SitemapStorage | None = None


def get_sitemap_storage() -> SitemapStorage:
    """Get singleton instance of sitemap storage."""
    global _storage_instance  # noqa: PLW0603
    if _storage_instance is None:
        _storage_instance = SitemapStorage()
    return _storage_instance
