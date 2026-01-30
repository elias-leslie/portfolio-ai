"""Database persistence for capability scanner."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from ..logging_config import get_logger
from .capability_utils import _to_json_string

if TYPE_CHECKING:
    from ..storage.connection import ConnectionManager

logger = get_logger(__name__)


def save_capabilities(
    conn_mgr: ConnectionManager,
    capabilities: list[dict[str, Any]],
) -> int:
    """Save scanned capabilities to db_capabilities table.

    Uses UPSERT logic (INSERT ... ON CONFLICT DO UPDATE) to update existing records.

    Args:
        conn_mgr: Connection manager for database access
        capabilities: List of capability dicts from scan()

    Returns:
        Number of rows inserted/updated
    """
    if not capabilities:
        logger.info("no_db_capabilities_to_save")
        return 0

    logger.info("saving_db_capabilities", count=len(capabilities))

    with conn_mgr.connection() as conn:
        for cap in capabilities:
            # Convert lists to JSON strings for JSONB columns
            columns_json = _to_json_string(cap["columns"])
            columns_with_data_json = _to_json_string(cap["columns_with_data"])
            columns_mostly_null_json = _to_json_string(cap["columns_mostly_null"])

            # UPSERT query
            conn.execute(
                """
                INSERT INTO db_capabilities (
                    table_name, category, row_count, total_columns,
                    columns, columns_with_data, columns_mostly_null,
                    completeness_pct, date_range_start, date_range_end,
                    expected_freshness, days_since_update, freshness_status,
                    health_status, last_scanned_at, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (table_name) DO UPDATE SET
                    category = EXCLUDED.category,
                    row_count = EXCLUDED.row_count,
                    total_columns = EXCLUDED.total_columns,
                    columns = EXCLUDED.columns,
                    columns_with_data = EXCLUDED.columns_with_data,
                    columns_mostly_null = EXCLUDED.columns_mostly_null,
                    completeness_pct = EXCLUDED.completeness_pct,
                    date_range_start = EXCLUDED.date_range_start,
                    date_range_end = EXCLUDED.date_range_end,
                    expected_freshness = EXCLUDED.expected_freshness,
                    days_since_update = EXCLUDED.days_since_update,
                    freshness_status = EXCLUDED.freshness_status,
                    health_status = EXCLUDED.health_status,
                    last_scanned_at = EXCLUDED.last_scanned_at,
                    updated_at = EXCLUDED.updated_at
                """,
                [
                    cap["table_name"],
                    cap["category"],
                    cap["row_count"],
                    cap["total_columns"],
                    columns_json,
                    columns_with_data_json,
                    columns_mostly_null_json,
                    cap["completeness_pct"],
                    cap["date_range_start"],
                    cap["date_range_end"],
                    cap["expected_freshness"],
                    cap["days_since_update"],
                    cap["freshness_status"],
                    cap["health_status"],
                    datetime.now(UTC),  # last_scanned_at
                    datetime.now(UTC),  # created_at
                    datetime.now(UTC),  # updated_at
                ],
            )
            conn.commit()

        # Clean up removed tables (inside the with block)
        removed_count = cleanup_removed_capabilities(
            conn, [cap["table_name"] for cap in capabilities]
        )
        if removed_count > 0:
            logger.info("db_capabilities_removed", count=removed_count)

    logger.info("db_capabilities_saved", count=len(capabilities))
    return len(capabilities)


def cleanup_removed_capabilities(
    conn: Any,
    current_table_names: list[str],
) -> int:
    """Remove capabilities for tables that no longer exist.

    Args:
        conn: Database connection
        current_table_names: List of table names currently in database

    Returns:
        Number of rows deleted
    """
    if not current_table_names:
        return 0

    # Find and delete tables that are in db_capabilities but no longer exist
    result = conn.execute(
        """
        DELETE FROM db_capabilities
        WHERE table_name NOT IN %s
        RETURNING table_name
        """,
        [tuple(current_table_names)],
    )
    deleted = result.fetchall()
    conn.commit()

    for row in deleted:
        logger.info("db_capability_removed", table_name=row[0])

    return len(deleted)
