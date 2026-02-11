"""Database operations for maintenance tasks.

This module provides the actual database operations for maintenance:
- Database vacuuming and optimization
- Old data cleanup (news, agent runs, orphaned records)
- Database size monitoring
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)


def get_database_size() -> dict[str, Any]:
    """Get database size and table sizes for monitoring.

    Returns:
        Dict with database_size_bytes, database_size_mb, top_tables
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        # Get total database size
        size_result = conn.execute(
            """
            SELECT pg_database_size(current_database())
            """
        ).fetchone()
        database_size = int(size_result[0]) if size_result and size_result[0] is not None else 0

        # Get top 10 largest tables
        tables_result = conn.execute(
            """
            SELECT
                tablename,
                pg_total_relation_size(schemaname || '.' || tablename) as size_bytes,
                pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) as size_pretty
            FROM pg_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC
            LIMIT 10
            """
        ).fetchall()

        top_tables = [
            {
                "table": str(row[0]),
                "size_bytes": int(row[1]) if row[1] is not None else 0,
                "size_pretty": str(row[2]),
            }
            for row in tables_result
        ]

    # Store metric in maintenance_stats
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO maintenance_stats (metric_name, metric_value, metric_unit)
            VALUES (%s, %s, %s)
            """,
            ["database_size_bytes", float(database_size), "bytes"],
        )
        conn.commit()

    return {
        "database_size_bytes": database_size,
        "database_size_mb": round(database_size / (1024 * 1024), 2),
        "top_tables": top_tables,
    }


def vacuum_tables(tables: list[str] | None = None, dry_run: bool = False) -> dict[str, Any]:
    """VACUUM ANALYZE database tables.

    Args:
        tables: Specific tables to vacuum (None = all tables)
        dry_run: If True, only report which tables would be vacuumed

    Returns:
        Dict with tables_processed, total_tables, or tables_to_vacuum (dry_run)
    """
    storage = get_connection_manager()

    # Get list of tables to vacuum
    if tables is None:
        with storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            ).fetchall()
            tables_to_vacuum: list[str] = [str(row[0]) for row in rows]
    else:
        tables_to_vacuum = tables

    if dry_run:
        return {
            "tables_to_vacuum": tables_to_vacuum,
            "total_tables": len(tables_to_vacuum),
            "message": f"Would vacuum {len(tables_to_vacuum)} tables",
        }

    # VACUUM ANALYZE each table
    tables_processed = 0
    for table in tables_to_vacuum:
        try:
            with storage.connection() as conn:
                # Set autocommit mode for VACUUM command
                raw_conn = conn.connection  # type: ignore[attr-defined]
                old_isolation_level = raw_conn.isolation_level
                raw_conn.set_isolation_level(0)  # AUTOCOMMIT

                try:
                    conn.execute(f"VACUUM ANALYZE {table}")  # validated: table from pg_tables
                    tables_processed += 1
                    logger.info("table_vacuumed", table=table)
                finally:
                    raw_conn.set_isolation_level(old_isolation_level)

        except Exception as table_error:
            logger.error("table_vacuum_failed", table=table, error=str(table_error))
            # Continue with next table

    return {
        "tables_processed": tables_processed,
        "total_tables": len(tables_to_vacuum),
    }


def cleanup_old_news(days: int = 90, dry_run: bool = False) -> dict[str, Any]:
    """Delete news articles older than specified days.

    Args:
        days: Delete news older than N days
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with rows_deleted/rows_to_delete, cutoff_date, retention_days
    """
    storage = get_connection_manager()
    cutoff_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

    with storage.connection() as conn:
        if dry_run:
            result = conn.execute(
                """
                SELECT COUNT(*) FROM news_cache
                WHERE published_at < %s
                """,
                [cutoff_date],
            ).fetchone()
            rows_to_delete = result[0] if result else 0

            return {
                "rows_to_delete": rows_to_delete,
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": days,
                "message": f"Would delete {rows_to_delete} news articles",
            }

        conn.execute(
            """
            DELETE FROM news_cache
            WHERE published_at < %s
            """,
            [cutoff_date],
        )
        rows_deleted = conn._cursor.rowcount
        conn.commit()

    return {
        "rows_deleted": rows_deleted,
        "cutoff_date": cutoff_date.isoformat(),
        "retention_days": days,
    }


def cleanup_old_agent_runs(days: int = 30, dry_run: bool = False) -> dict[str, Any]:
    """Delete agent run history older than specified days.

    Args:
        days: Delete agent runs older than N days
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with runs_deleted/runs_to_delete, cutoff_date, retention_days
    """
    storage = get_connection_manager()
    cutoff_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

    with storage.connection() as conn:
        if dry_run:
            count_row = conn.execute(
                """
                SELECT COUNT(*) FROM agent_runs
                WHERE started_at < %s
                """,
                [cutoff_date],
            ).fetchone()
            runs_to_delete = count_row[0] if count_row else 0

            return {
                "runs_to_delete": runs_to_delete,
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": days,
                "message": f"Would delete {runs_to_delete} agent runs",
            }

        # Get agent run IDs to delete
        rows = conn.execute(
            """
            SELECT id FROM agent_runs
            WHERE started_at < %s
            """,
            [cutoff_date],
        ).fetchall()
        run_ids = [row[0] for row in rows]

        if run_ids:
            conn.execute(
                """
                DELETE FROM agent_runs
                WHERE id = ANY(%s)
                """,
                [run_ids],
            )
            runs_deleted = conn._cursor.rowcount
            conn.commit()
        else:
            runs_deleted = 0

    return {
        "runs_deleted": runs_deleted,
        "cutoff_date": cutoff_date.isoformat(),
        "retention_days": days,
    }


def cleanup_old_watchlist_snapshots(days: int = 60, dry_run: bool = False) -> dict[str, Any]:
    """Delete watchlist snapshots older than specified days.

    Deletes from both normalized tables (via CASCADE from watchlist_snapshots_core)
    and the legacy watchlist_snapshots table.

    Args:
        days: Delete snapshots older than N days
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with rows_deleted/rows_to_delete for each table, cutoff_date, retention_days
    """
    storage = get_connection_manager()
    cutoff_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

    with storage.connection() as conn:
        if dry_run:
            core_count = conn.execute(
                """
                SELECT COUNT(*) FROM watchlist_snapshots_core
                WHERE fetched_at < %s
                """,
                [cutoff_date],
            ).fetchone()
            legacy_count = conn.execute(
                """
                SELECT COUNT(*) FROM watchlist_snapshots
                WHERE fetched_at < %s
                """,
                [cutoff_date],
            ).fetchone()

            return {
                "core_rows_to_delete": core_count[0] if core_count else 0,
                "legacy_rows_to_delete": legacy_count[0] if legacy_count else 0,
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": days,
                "message": (
                    f"Would delete {core_count[0] if core_count else 0} core rows "
                    f"and {legacy_count[0] if legacy_count else 0} legacy rows"
                ),
            }

        # Delete from normalized tables (CASCADE handles technical_metrics, narrative, news_summary)
        conn.execute(
            """
            DELETE FROM watchlist_snapshots_core
            WHERE fetched_at < %s
            """,
            [cutoff_date],
        )
        core_deleted = conn._cursor.rowcount

        # Delete from legacy table
        conn.execute(
            """
            DELETE FROM watchlist_snapshots
            WHERE fetched_at < %s
            """,
            [cutoff_date],
        )
        legacy_deleted = conn._cursor.rowcount

        conn.commit()

    return {
        "core_rows_deleted": core_deleted,
        "legacy_rows_deleted": legacy_deleted,
        "cutoff_date": cutoff_date.isoformat(),
        "retention_days": days,
    }


def cleanup_maintenance_tables(days: int = 90, dry_run: bool = False) -> dict[str, Any]:
    """Delete old entries from maintenance tracking tables.

    Cleans up: maintenance_stats, maintenance_log, news_summary_log.

    Args:
        days: Delete entries older than N days
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with rows_deleted per table, cutoff_date, retention_days
    """
    storage = get_connection_manager()
    cutoff_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

    tables = [
        ("maintenance_stats", "recorded_at"),
        ("maintenance_log", "started_at"),
        ("news_summary_log", "created_at"),
    ]

    with storage.connection() as conn:
        if dry_run:
            counts: dict[str, int] = {}
            for table, col in tables:
                result = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {col} < %s",  # table/col from constant list
                    [cutoff_date],
                ).fetchone()
                counts[f"{table}_to_delete"] = int(result[0]) if result else 0

            return {
                **counts,
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": days,
                "message": f"Would delete {sum(counts.values())} total rows across {len(tables)} tables",
            }

        deleted: dict[str, int] = {}
        for table, col in tables:
            conn.execute(
                f"DELETE FROM {table} WHERE {col} < %s",  # table/col from constant list
                [cutoff_date],
            )
            deleted[f"{table}_deleted"] = conn._cursor.rowcount

        conn.commit()

    return {
        **deleted,
        "cutoff_date": cutoff_date.isoformat(),
        "retention_days": days,
    }


def cleanup_orphaned_data(dry_run: bool = False) -> dict[str, Any]:
    """Remove orphaned records and fix zombie runs.

    Args:
        dry_run: If True, only report what would be cleaned

    Returns:
        Dict with orphaned_insights_deleted, zombie_runs_fixed
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        if dry_run:
            # Count orphaned insights
            result = conn.execute(
                """
                SELECT COUNT(*) FROM capability_insights
                WHERE capability_id NOT IN (
                    SELECT capability_id FROM db_capabilities
                    UNION
                    SELECT capability_id FROM celery_capabilities
                    UNION
                    SELECT capability_id FROM api_capabilities
                )
                """
            ).fetchone()
            orphaned_insights = result[0] if result else 0

            # Count zombie runs
            cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)
            result = conn.execute(
                """
                SELECT COUNT(*) FROM agent_runs
                WHERE status IN ('running', 'error')
                AND started_at < %s
                """,
                [cutoff],
            ).fetchone()
            zombie_runs = result[0] if result else 0

            return {
                "orphaned_insights_to_delete": orphaned_insights,
                "zombie_runs_to_fix": zombie_runs,
                "message": f"Would delete {orphaned_insights} orphaned insights and fix {zombie_runs} zombie runs",
            }

        # Delete capabilities insights with non-existent capability_id
        conn.execute(
            """
            DELETE FROM capability_insights
            WHERE capability_id NOT IN (
                SELECT capability_id FROM db_capabilities
                UNION
                SELECT capability_id FROM celery_capabilities
                UNION
                SELECT capability_id FROM api_capabilities
            )
            """
        )
        orphaned_insights = conn._cursor.rowcount

        # Fix zombie agent runs
        cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)
        conn.execute(
            """
            UPDATE agent_runs
            SET status = 'failed',
                completed_at = NOW(),
                error_message = 'Marked as failed by cleanup task - run stuck in running state'
            WHERE status IN ('running', 'error')
            AND started_at < %s
            """,
            [cutoff],
        )
        zombie_runs_fixed = conn._cursor.rowcount

        conn.commit()

    return {
        "orphaned_insights_deleted": orphaned_insights,
        "zombie_runs_fixed": zombie_runs_fixed,
    }
