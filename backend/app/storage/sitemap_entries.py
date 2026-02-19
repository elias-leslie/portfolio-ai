"""Sitemap entry CRUD storage operations."""

from __future__ import annotations

from ..logging_config import get_logger
from .connection import ConnectionManager
from .sitemap_entry import ENTRY_COLUMNS, row_to_entry

logger = get_logger(__name__)


def get_entries(
    conn_mgr: ConnectionManager,
    port: int | None = None,
    health_status: str | None = None,
    entry_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, object]], int]:
    """Get paginated sitemap entries with optional filters.

    Args:
        conn_mgr: Database connection manager.
        port: Filter by port.
        health_status: Filter by health status.
        entry_type: Filter by entry type.
        limit: Max results.
        offset: Pagination offset.

    Returns:
        Tuple of (entries list, total count).
    """
    conditions: list[str] = []
    params: list[object] = []

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

    with conn_mgr.connection() as conn:
        count_result = conn.execute(
            f"SELECT COUNT(*) FROM sitemap_entries WHERE {where_clause}",
            params,  # type: ignore[arg-type]
        )
        row = count_result.fetchone()
        total: int = int(row[0]) if row and row[0] is not None else 0  # type: ignore[arg-type]

        result = conn.execute(
            f"""
            SELECT {ENTRY_COLUMNS}
            FROM sitemap_entries
            WHERE {where_clause}
            ORDER BY port, path
            LIMIT %s OFFSET %s
            """,
            [*params, limit, offset],  # type: ignore[list-item]
        )
        entries = [row_to_entry(r).to_dict() for r in result.fetchall()]
        return entries, total


def get_entry(conn_mgr: ConnectionManager, entry_id: int) -> dict[str, object] | None:
    """Get single entry by ID.

    Args:
        conn_mgr: Database connection manager.
        entry_id: Entry ID.

    Returns:
        Entry dict or None if not found.
    """
    with conn_mgr.connection() as conn:
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
    return row_to_entry(row).to_dict()


def register_entry(
    conn_mgr: ConnectionManager,
    port: int,
    path: str,
    method: str = "GET",
    entry_type: str = "manual",
    title: str | None = None,
) -> dict[str, object] | None:
    """Manually register a new sitemap entry.

    Args:
        conn_mgr: Database connection manager.
        port: Port number.
        path: URL path.
        method: HTTP method.
        entry_type: Entry type.
        title: Optional title.

    Returns:
        Created entry dict or None on failure.
    """
    with conn_mgr.connection() as conn:
        result = conn.execute(
            """
            INSERT INTO sitemap_entries (port, path, method, entry_type, source, title)
            VALUES (%s, %s, %s, %s, 'manual', %s)
            RETURNING id
            """,
            [port, path, method, entry_type, title],
        )
        row = result.fetchone()
        entry_id = int(row[0]) if row and row[0] is not None else None  # type: ignore[arg-type]
        conn.commit()

    if entry_id is not None:
        return get_entry(conn_mgr, entry_id)
    return None


def delete_entry(conn_mgr: ConnectionManager, entry_id: int) -> bool:
    """Remove a sitemap entry.

    Args:
        conn_mgr: Database connection manager.
        entry_id: Entry ID to delete.

    Returns:
        True if deleted, False if not found.
    """
    with conn_mgr.connection() as conn:
        result = conn.execute(
            "DELETE FROM sitemap_entries WHERE id = %s RETURNING id",
            [entry_id],
        )
        deleted = result.fetchone() is not None
        conn.commit()
        return deleted


def bulk_save_discovered_entries(conn_mgr: ConnectionManager, entries: list[dict[str, object]]) -> int:
    """Bulk save discovered sitemap entries with upsert logic.

    Args:
        conn_mgr: Database connection manager.
        entries: List of entry dicts with keys: port, path, method, entry_type, source, title.

    Returns:
        Number of entries successfully saved.
    """
    saved = 0
    with conn_mgr.connection() as conn:
        for entry in entries:
            try:
                conn.execute(
                    """
                    INSERT INTO sitemap_entries (port, path, method, entry_type, source, title, discovered_at)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (port, path, method) DO UPDATE SET
                        title = COALESCE(EXCLUDED.title, sitemap_entries.title),
                        source = EXCLUDED.source,
                        updated_at = NOW()
                    """,
                    [
                        entry["port"],
                        entry["path"],
                        entry["method"],
                        entry["entry_type"],
                        entry["source"],
                        entry.get("title"),
                    ],
                )
                saved += 1
            except Exception as e:
                logger.debug("sitemap_save_entry_failed", path=entry["path"], error=str(e))

        conn.commit()

    return saved
