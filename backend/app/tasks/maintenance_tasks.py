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

from app.logging_config import get_logger
from app.sources.sec_cik_fetcher import fetch_and_save as fetch_cik_mapping
from app.storage import get_storage
from app.tasks.maintenance_helpers import execute_maintenance_task
from app.tasks.maintenance_operations import (
    cleanup_old_agent_runs,
    cleanup_old_news,
    cleanup_orphaned_data,
    get_database_size,
    vacuum_tables,
)
from app.utils.task_helpers import calculate_duration

logger = get_logger(__name__)


def vacuum_database_task(
    self: Task[..., Any], tables: list[str] | None = None, dry_run: bool = False
) -> dict[str, Any]:
    """VACUUM ANALYZE database tables to reclaim space and update statistics.

    Args:
        tables: Specific tables to vacuum (None = all tables)
        dry_run: If True, only report which tables would be vacuumed

    Returns:
        Dict with task_id, tables_processed, duration_seconds, success status
    """
    task_id = self.request.id or "unknown"

    def vacuum_impl() -> dict[str, Any]:
        return vacuum_tables(tables=tables, dry_run=dry_run)

    return execute_maintenance_task("vacuum_database_task", task_id, vacuum_impl, dry_run)


def cleanup_old_news_task(
    self: Task[..., Any], days: int = 90, dry_run: bool = False
) -> dict[str, Any]:
    """Delete news articles older than specified days.

    Args:
        days: Delete news older than N days (default: 90)
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with task_id, rows_deleted, duration_seconds, success status
    """
    task_id = self.request.id or "unknown"

    def cleanup_impl() -> dict[str, Any]:
        return cleanup_old_news(days=days, dry_run=dry_run)

    return execute_maintenance_task("cleanup_old_news_task", task_id, cleanup_impl, dry_run)


def cleanup_old_agent_runs_task(
    self: Task[..., Any], days: int = 30, dry_run: bool = False
) -> dict[str, Any]:
    """Delete agent run history older than specified days.

    Args:
        days: Delete agent runs older than N days (default: 30)
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with task_id, runs_deleted, duration_seconds, success status
    """
    task_id = self.request.id or "unknown"

    def cleanup_impl() -> dict[str, Any]:
        return cleanup_old_agent_runs(days=days, dry_run=dry_run)

    return execute_maintenance_task("cleanup_old_agent_runs_task", task_id, cleanup_impl, dry_run)


def cleanup_orphaned_data_task(self: Task[..., Any], dry_run: bool = False) -> dict[str, Any]:
    """Remove orphaned records and fix zombie runs.

    Args:
        dry_run: If True, only report what would be cleaned

    Returns:
        Dict with task_id, orphaned_insights_deleted, zombie_runs_fixed, duration_seconds, success status
    """
    task_id = self.request.id or "unknown"

    def cleanup_impl() -> dict[str, Any]:
        return cleanup_orphaned_data(dry_run=dry_run)

    return execute_maintenance_task("cleanup_orphaned_data_task", task_id, cleanup_impl, dry_run)


def get_database_size_task(
    self: Task[..., Any],
) -> dict[str, int | str | float | list[dict[str, Any]]]:
    """Get database size and table sizes for monitoring.

    Returns:
        Dict with task_id, database_size_bytes, top_tables, duration_seconds
    """
    task_id = self.request.id or "unknown"
    start_time = dt.datetime.now(dt.UTC)

    logger.info("get_database_size_started", task_id=task_id)

    try:
        result = get_database_size()
        duration = calculate_duration(start_time)

        result_dict: dict[str, int | str | float | list[dict[str, Any]]] = {
            "task_id": task_id,
            **result,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("get_database_size_completed", **result_dict)
        return result_dict

    except Exception as e:
        duration = calculate_duration(start_time)
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


def refresh_sec_cik_cache(self: Task[..., Any]) -> dict[str, Any]:
    """Refresh SEC CIK cache from SEC EDGAR.

    Fetches the latest symbol→CIK mapping from SEC and updates the database.
    This enables SEC filing lookups for all tracked symbols.

    Returns:
        Dict with task_id, symbols_updated, duration_seconds, success
    """
    task_id = self.request.id or "unknown"
    start_time = dt.datetime.now(dt.UTC)

    logger.info("refresh_sec_cik_cache_started", task_id=task_id)

    try:
        storage = get_storage()
        mapping = fetch_cik_mapping(storage)

        duration = calculate_duration(start_time)

        result_dict: dict[str, Any] = {
            "task_id": task_id,
            "symbols_updated": len(mapping),
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("refresh_sec_cik_cache_completed", **result_dict)
        return result_dict

    except Exception as e:
        duration = calculate_duration(start_time)
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
