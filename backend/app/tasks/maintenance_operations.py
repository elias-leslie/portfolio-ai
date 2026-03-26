"""Database operations for maintenance tasks.

This module provides the actual database operations for maintenance:
- Database vacuuming and optimization
- Old data cleanup (news and agent runs)
- Database size monitoring
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _cutoff_at(days: int) -> dt.datetime:
    """Return a UTC datetime representing now minus *days* days."""
    return dt.datetime.now(dt.UTC) - dt.timedelta(days=days)


def _count_rows(conn: Any, table: str, col: str, cutoff: dt.datetime) -> int:
    """Return the count of rows in *table* where *col* is before *cutoff*."""
    row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} < %s", [cutoff]).fetchone()
    return int(row[0] or 0) if row else 0


def _vacuum_one_table(storage: Any, table: str) -> None:
    """Run VACUUM ANALYZE on a single table using autocommit mode."""
    with storage.connection() as conn:
        raw_conn = conn.raw_connection
        old_autocommit = raw_conn.autocommit
        raw_conn.autocommit = True
        try:
            with raw_conn.cursor() as cursor:
                cursor.execute(f'VACUUM ANALYZE "{table}"')
        finally:
            raw_conn.autocommit = old_autocommit


def _resolve_vacuum_tables(tables: list[str] | None, storage: Any) -> list[str]:
    """Return the list of tables to vacuum, querying pg_tables if *tables* is None."""
    if tables is None:
        with storage.connection() as conn:
            rows = conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            ).fetchall()
            return [str(row[0]) for row in rows]
    return tables


def get_database_size() -> dict[str, Any]:
    """Get database size and table sizes for monitoring.

    Returns:
        Dict with database_size_bytes, database_size_mb, top_tables
    """
    storage = get_connection_manager()

    with storage.connection() as conn:
        size_result = conn.execute(
            "SELECT pg_database_size(current_database())"
        ).fetchone()
        database_size = int(size_result[0]) if size_result and size_result[0] is not None else 0

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
    tables_to_vacuum = _resolve_vacuum_tables(tables, storage)

    invalid_tables = [t for t in tables_to_vacuum if not _SAFE_IDENTIFIER.fullmatch(t)]
    if invalid_tables:
        msg = f"Unsafe table names for vacuum: {', '.join(sorted(invalid_tables))}"
        raise ValueError(msg)

    if dry_run:
        return {
            "tables_to_vacuum": tables_to_vacuum,
            "total_tables": len(tables_to_vacuum),
            "message": f"Would vacuum {len(tables_to_vacuum)} tables",
        }

    tables_processed = 0
    failed_tables: list[str] = []
    for table in tables_to_vacuum:
        try:
            _vacuum_one_table(storage, table)
            tables_processed += 1
            logger.info("table_vacuumed", table=table)
        except Exception as table_error:
            logger.error("table_vacuum_failed", table=table, error=str(table_error), exc_info=True)
            failed_tables.append(table)

    if failed_tables:
        msg = (
            f"VACUUM ANALYZE failed for {len(failed_tables)} tables; "
            f"processed={tables_processed}, failed={failed_tables}"
        )
        raise RuntimeError(msg)

    return {
        "tables_processed": tables_processed,
        "total_tables": len(tables_to_vacuum),
        "tables_failed": failed_tables,
        "failed_tables_count": len(failed_tables),
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
    cutoff_date = _cutoff_at(days)

    where_clause = """
        WHERE COALESCE(published_at, fetched_at) < %s
          AND fetched_at < %s
    """

    with storage.connection() as conn:
        if dry_run:
            result = conn.execute(
                f"SELECT COUNT(*) FROM news_cache {where_clause}",
                [cutoff_date, cutoff_date],
            ).fetchone()
            rows_to_delete = result[0] if result else 0
            return {
                "rows_to_delete": rows_to_delete,
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": days,
                "message": (
                    f"Would delete {rows_to_delete} news articles older than the retention window "
                    "and not re-fetched recently"
                ),
            }

        conn.execute(
            f"DELETE FROM news_cache {where_clause}",
            [cutoff_date, cutoff_date],
        )
        rows_deleted = conn.rowcount
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
    cutoff_date = _cutoff_at(days)

    with storage.connection() as conn:
        if dry_run:
            runs_to_delete = _count_rows(conn, "agent_runs", "started_at", cutoff_date)
            return {
                "runs_to_delete": runs_to_delete,
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": days,
                "message": f"Would delete {runs_to_delete} agent runs",
            }

        conn.execute(
            "DELETE FROM agent_runs WHERE started_at < %s",
            [cutoff_date],
        )
        runs_deleted = conn.rowcount
        conn.commit()

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
    cutoff_date = _cutoff_at(days)

    with storage.connection() as conn:
        if dry_run:
            core_count = _count_rows(conn, "watchlist_snapshots_core", "fetched_at", cutoff_date)
            old_count = _count_rows(conn, "watchlist_snapshots", "fetched_at", cutoff_date)
            return {
                "core_rows_to_delete": core_count,
                "legacy_rows_to_delete": old_count,
                "cutoff_date": cutoff_date.isoformat(),
                "retention_days": days,
                "message": f"Would delete {core_count} core rows and {old_count} legacy rows",
            }

        # DELETE from normalized tables (CASCADE handles technical_metrics, narrative, news_summary)
        conn.execute(
            "DELETE FROM watchlist_snapshots_core WHERE fetched_at < %s",
            [cutoff_date],
        )
        core_deleted = conn.rowcount

        conn.execute(
            "DELETE FROM watchlist_snapshots WHERE fetched_at < %s",
            [cutoff_date],
        )
        old_deleted = conn.rowcount
        conn.commit()

    return {
        "core_rows_deleted": core_deleted,
        "legacy_rows_deleted": old_deleted,
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
    cutoff_date = _cutoff_at(days)

    tables = [
        ("maintenance_stats", "recorded_at"),
        ("maintenance_log", "started_at"),
        ("news_summary_log", "created_at"),
    ]

    with storage.connection() as conn:
        if dry_run:
            counts = {
                f"{table}_to_delete": _count_rows(conn, table, col, cutoff_date)
                for table, col in tables
            }
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
            deleted[f"{table}_deleted"] = conn.rowcount
        conn.commit()

    return {
        **deleted,
        "cutoff_date": cutoff_date.isoformat(),
        "retention_days": days,
    }


def cleanup_orphaned_data(dry_run: bool = False) -> dict[str, Any]:
    """Fix stale agent runs left behind by interrupted maintenance workflows.

    Args:
        dry_run: If True, only report what would be cleaned

    Returns:
        Dict with zombie_runs_fixed or zombie_runs_to_fix
    """
    storage = get_connection_manager()
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(hours=1)

    with storage.connection() as conn:
        if dry_run:
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
                "zombie_runs_to_fix": zombie_runs,
                "message": f"Would mark {zombie_runs} stale agent runs as failed",
            }

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
        zombie_runs_fixed = conn.rowcount
        conn.commit()

    return {
        "zombie_runs_fixed": zombie_runs_fixed,
    }
