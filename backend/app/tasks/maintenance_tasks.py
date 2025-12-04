"""Celery tasks for database maintenance operations.

This module provides automated maintenance tasks for:
- Database vacuuming and optimization
- Old data cleanup (news, agent runs, orphaned records)
- Database size monitoring and tracking

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Self-healing (detect and fix issues automatically)
- Scheduled (run on Celery Beat schedule)
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.sources.sec_cik_fetcher import fetch_and_save as fetch_cik_mapping
from app.storage import get_storage
from app.storage.connection import get_connection_manager

if TYPE_CHECKING:
    from celery import Task

logger = get_logger(__name__)


# Helper functions (pure logic, no Celery)


def _get_database_size_impl() -> dict[str, Any]:
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
        "success": True,
    }


@celery_app.task(name="vacuum_database_task", bind=True)  # type: ignore[misc]
def vacuum_database_task(
    self: Task, tables: list[str] | None = None
) -> dict[str, int | str | float | bool]:
    """VACUUM ANALYZE database tables to reclaim space and update statistics.

    Args:
        tables: Specific tables to vacuum (None = all tables)

    Returns:
        Dict with task_id, tables_processed, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("vacuum_database_started", task_id=task_id, tables=tables)

    try:
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

        # VACUUM ANALYZE each table
        # Note: VACUUM cannot run inside transaction block, so we do each table separately
        tables_processed = 0
        for table in tables_to_vacuum:
            try:
                # Need to use isolation_level AUTOCOMMIT for VACUUM
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
                        # Restore isolation level
                        raw_conn.set_isolation_level(old_isolation_level)

            except Exception as table_error:
                logger.error(
                    "table_vacuum_failed",
                    table=table,
                    error=str(table_error),
                )
                # Continue with next table

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result: dict[str, int | str | float | bool] = {
            "task_id": task_id,
            "tables_processed": tables_processed,
            "total_tables": len(tables_to_vacuum),
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("vacuum_database_completed", **result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "vacuum_database_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="cleanup_old_news_task", bind=True)  # type: ignore[misc]
def cleanup_old_news_task(self: Task, days: int = 90) -> dict[str, int | str | float]:
    """Delete news articles older than specified days.

    Args:
        days: Delete news older than N days (default: 90)

    Returns:
        Dict with task_id, rows_deleted, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("cleanup_old_news_started", task_id=task_id, days=days)

    try:
        storage = get_connection_manager()

        # Calculate cutoff date
        cutoff_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

        with storage.connection() as conn:
            # Delete old news articles
            conn.execute(
                """
                DELETE FROM news_cache
                WHERE fetched_at < %s
                """,
                [cutoff_date],
            )
            rows_deleted = conn._cursor.rowcount
            conn.commit()

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result_dict = {
            "task_id": task_id,
            "rows_deleted": rows_deleted,
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": days,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("cleanup_old_news_completed", **result_dict)
        return result_dict

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_old_news_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="cleanup_old_agent_runs_task", bind=True)  # type: ignore[misc]
def cleanup_old_agent_runs_task(self: Task, days: int = 30) -> dict[str, int | str | float]:
    """Delete agent run history older than specified days.

    Args:
        days: Delete agent runs older than N days (default: 30)

    Returns:
        Dict with task_id, runs_deleted, ideas_deleted, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("cleanup_old_agent_runs_started", task_id=task_id, days=days)

    try:
        storage = get_connection_manager()

        # Calculate cutoff date
        cutoff_date = dt.datetime.now(dt.UTC) - dt.timedelta(days=days)

        with storage.connection() as conn:
            # Get agent run IDs to delete
            result = conn.execute(
                """
                SELECT id FROM agent_runs
                WHERE created_at < %s
                """,
                [cutoff_date],
            ).fetchall()
            run_ids = [row[0] for row in result]

            if run_ids:
                # Delete associated ideas first (FK constraint)
                conn.execute(
                    """
                    DELETE FROM agent_ideas
                    WHERE run_id = ANY(%s)
                    """,
                    [run_ids],
                )
                ideas_deleted = conn._cursor.rowcount

                # Delete agent runs
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
                ideas_deleted = 0
                runs_deleted = 0

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result_dict = {
            "task_id": task_id,
            "runs_deleted": runs_deleted,
            "ideas_deleted": ideas_deleted,
            "cutoff_date": cutoff_date.isoformat(),
            "retention_days": days,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("cleanup_old_agent_runs_completed", **result_dict)
        return result_dict

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_old_agent_runs_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="cleanup_orphaned_data_task", bind=True)  # type: ignore[misc]
def cleanup_orphaned_data_task(self: Task) -> dict[str, int | str | float]:
    """Remove orphaned records (ideas without runs, etc.).

    Returns:
        Dict with task_id, orphaned_ideas_deleted, duration_seconds, success status
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("cleanup_orphaned_data_started", task_id=task_id)

    try:
        storage = get_connection_manager()

        with storage.connection() as conn:
            # Delete ideas with non-existent run_ids
            conn.execute(
                """
                DELETE FROM agent_ideas
                WHERE run_id NOT IN (SELECT id FROM agent_runs)
                """
            )
            orphaned_ideas = conn._cursor.rowcount

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

            conn.commit()

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result_dict = {
            "task_id": task_id,
            "orphaned_ideas_deleted": orphaned_ideas,
            "orphaned_insights_deleted": orphaned_insights,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("cleanup_orphaned_data_completed", **result_dict)
        return result_dict

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "cleanup_orphaned_data_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="get_database_size_task", bind=True)  # type: ignore[misc]
def get_database_size_task(self: Task) -> dict[str, int | str | float | list[dict[str, Any]]]:
    """Get database size and table sizes for monitoring.

    Returns:
        Dict with task_id, database_size_bytes, top_tables, duration_seconds
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("get_database_size_started", task_id=task_id)

    try:
        result = _get_database_size_impl()
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result_dict: dict[str, int | str | float | list[dict[str, Any]]] = {
            "task_id": task_id,
            **result,
            "duration_seconds": round(duration, 2),
        }

        logger.info("get_database_size_completed", **result_dict)
        return result_dict

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "get_database_size_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }


@celery_app.task(name="refresh_sec_cik_cache", bind=True)  # type: ignore[misc]
def refresh_sec_cik_cache(self: Task) -> dict[str, Any]:
    """Refresh SEC CIK cache from SEC EDGAR.

    Fetches the latest symbol→CIK mapping from SEC and updates the database.
    This enables SEC filing lookups for all tracked symbols.

    Returns:
        Dict with task_id, symbols_updated, duration_seconds, success
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)

    logger.info("refresh_sec_cik_cache_started", task_id=task_id)

    try:
        storage = get_storage()
        mapping = fetch_cik_mapping(storage)

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        result_dict: dict[str, Any] = {
            "task_id": task_id,
            "symbols_updated": len(mapping),
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("refresh_sec_cik_cache_completed", **result_dict)
        return result_dict

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "refresh_sec_cik_cache_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            duration_seconds=round(duration, 2),
        )
        return {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }
