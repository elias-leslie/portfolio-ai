"""Database helper utilities for common query patterns.

Provides shared functions for row-to-dict conversion and fetch patterns
to reduce duplication across the codebase.
"""

from __future__ import annotations

from typing import Any


def rows_to_dicts(rows: list[tuple[Any, ...]], conn_wrapper: Any) -> list[dict[str, Any]]:
    """Convert database cursor rows (tuples) to dictionaries using cursor column names.

    Args:
        rows: List of tuple rows from cursor.fetchall()
        conn_wrapper: PostgreSQL connection wrapper with description property

    Returns:
        List of dictionaries with column names as keys

    Example:
        rows = conn.execute("SELECT id, name FROM users").fetchall()
        dicts = rows_to_dicts(rows, conn)
        # [{'id': 1, 'name': 'Alice'}, {'id': 2, 'name': 'Bob'}]
    """
    if not rows or conn_wrapper.description is None:
        return []

    columns = [desc[0] for desc in conn_wrapper.description]
    return [dict(zip(columns, row, strict=False)) for row in rows]


def fetch_rows(
    conn: Any,
    query: str,
    params: list[Any] | tuple[Any, ...] | None = None,
) -> list[dict[str, Any]]:
    """Execute query and return results as list of dictionaries.

    Combines execute, fetchall, and row-to-dict conversion in one call.

    Args:
        conn: Database connection wrapper
        query: SQL query string
        params: Query parameters (optional)

    Returns:
        List of dictionaries with column names as keys

    Example:
        with connection_manager.connection() as conn:
            users = fetch_rows(conn, "SELECT * FROM users WHERE active = %s", [True])
    """
    result = conn.execute(query, params) if params else conn.execute(query)
    rows = result.fetchall()
    return rows_to_dicts(rows, result)


def safe_get_float(
    rows: list[dict[str, Any]],
    index: int,
    key: str,
    default: float = 0.0,
) -> float:
    """Safely extract float value from query result rows.

    Args:
        rows: List of row dictionaries
        index: Row index to access
        key: Column key to extract
        default: Default value if extraction fails

    Returns:
        Float value or default
    """
    if not rows or index >= len(rows):
        return default
    value = rows[index].get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_get_int(
    rows: list[dict[str, Any]],
    index: int,
    key: str,
    default: int = 0,
) -> int:
    """Safely extract int value from query result rows.

    Args:
        rows: List of row dictionaries
        index: Row index to access
        key: Column key to extract
        default: Default value if extraction fails

    Returns:
        Int value or default
    """
    if not rows or index >= len(rows):
        return default
    value = rows[index].get(key)
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
