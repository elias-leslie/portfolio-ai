"""Database maintenance tasks.

This module provides automated maintenance tasks for:
- Database vacuuming and optimization
- Old data cleanup (news and agent runs)
- Database size monitoring and tracking

All tasks are designed to be:
- Idempotent (safe to run multiple times)
- Self-healing (detect and fix issues automatically)
- Scheduled via Hatchet cron workflows
"""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from app.logging_config import get_logger
from app.services.maintenance_tracker import (
    record_maintenance_completion,
    record_maintenance_start,
    save_maintenance_stat,
)
from app.sources.sec_cik_fetcher import fetch_and_save as fetch_cik_mapping
from app.storage import get_storage
from app.tasks.maintenance_helpers import execute_maintenance_task
from app.tasks.maintenance_operations import (
    cleanup_maintenance_tables,
    cleanup_old_agent_runs,
    cleanup_old_news,
    cleanup_old_watchlist_snapshots,
    cleanup_orphaned_data,
    get_database_size,
    vacuum_tables,
)
from app.utils.task_helpers import calculate_duration

logger = get_logger(__name__)


def vacuum_database_task(
    tables: list[str] | None = None, dry_run: bool = False
) -> dict[str, Any]:
    """VACUUM ANALYZE database tables to reclaim space and update statistics.

    Args:
        tables: Specific tables to vacuum (None = all tables)
        dry_run: If True, only report which tables would be vacuumed

    Returns:
        Dict with task_id, tables_processed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())

    def vacuum_impl() -> dict[str, Any]:
        return vacuum_tables(tables=tables, dry_run=dry_run)

    return execute_maintenance_task("vacuum_database_task", task_id, vacuum_impl, dry_run)


def cleanup_old_news_task(
    days: int = 90, dry_run: bool = False
) -> dict[str, Any]:
    """Delete news articles older than specified days.

    Args:
        days: Delete news older than N days (default: 90)
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with task_id, rows_deleted, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())

    def cleanup_impl() -> dict[str, Any]:
        return cleanup_old_news(days=days, dry_run=dry_run)

    return execute_maintenance_task("cleanup_old_news_task", task_id, cleanup_impl, dry_run)


def cleanup_old_agent_runs_task(
    days: int = 30, dry_run: bool = False
) -> dict[str, Any]:
    """Delete agent run history older than specified days.

    Args:
        days: Delete agent runs older than N days (default: 30)
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with task_id, runs_deleted, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())

    def cleanup_impl() -> dict[str, Any]:
        return cleanup_old_agent_runs(days=days, dry_run=dry_run)

    return execute_maintenance_task("cleanup_old_agent_runs_task", task_id, cleanup_impl, dry_run)


def cleanup_old_watchlist_snapshots_task(
    days: int = 60, dry_run: bool = False
) -> dict[str, Any]:
    """Delete watchlist snapshots older than specified days.

    Args:
        days: Delete snapshots older than N days (default: 60)
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with task_id, rows_deleted, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())

    def cleanup_impl() -> dict[str, Any]:
        return cleanup_old_watchlist_snapshots(days=days, dry_run=dry_run)

    return execute_maintenance_task("cleanup_old_watchlist_snapshots_task", task_id, cleanup_impl, dry_run)


def cleanup_maintenance_tables_task(
    days: int = 90, dry_run: bool = False
) -> dict[str, Any]:
    """Delete old maintenance stats, logs, and news summary logs.

    Args:
        days: Delete entries older than N days (default: 90)
        dry_run: If True, only report how many rows would be deleted

    Returns:
        Dict with task_id, rows_deleted per table, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())

    def cleanup_impl() -> dict[str, Any]:
        return cleanup_maintenance_tables(days=days, dry_run=dry_run)

    return execute_maintenance_task("cleanup_maintenance_tables_task", task_id, cleanup_impl, dry_run)


def cleanup_orphaned_data_task(dry_run: bool = False) -> dict[str, Any]:
    """Fix stale agent runs left behind by interrupted workflows.

    Args:
        dry_run: If True, only report what would be cleaned

    Returns:
        Dict with task_id, zombie_runs_fixed, duration_seconds, success status
    """
    task_id = str(uuid.uuid4())

    def cleanup_impl() -> dict[str, Any]:
        return cleanup_orphaned_data(dry_run=dry_run)

    return execute_maintenance_task("cleanup_orphaned_data_task", task_id, cleanup_impl, dry_run)


def get_database_size_task() -> dict[str, int | str | float | list[dict[str, Any]]]:
    """Get database size and table sizes for monitoring.

    Returns:
        Dict with task_id, database_size_bytes, top_tables, duration_seconds
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = record_maintenance_start("get_database_size_task", dry_run=False)

    logger.info("get_database_size_started", task_id=task_id)

    try:
        result = get_database_size()
        duration = calculate_duration(start_time)
        save_maintenance_stat(
            "database_size_bytes",
            float(result["database_size_bytes"]),
            "bytes",
            {"top_table_count": len(result["top_tables"])},
        )

        result_dict: dict[str, int | str | float | list[dict[str, Any]]] = {
            "task_id": task_id,
            **result,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("get_database_size_completed", **result_dict)
        record_maintenance_completion(log_id, "success", result_dict, None)
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
        error_result = {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }
        record_maintenance_completion(log_id, "error", error_result, str(e))
        return error_result


def refresh_sec_cik_cache() -> dict[str, Any]:
    """Refresh SEC CIK cache from SEC EDGAR.

    Fetches the latest symbol→CIK mapping from SEC and updates the database.
    This enables SEC filing lookups for all tracked symbols.

    Returns:
        Dict with task_id, symbols_updated, duration_seconds, success
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    log_id = record_maintenance_start("refresh_sec_cik_cache", dry_run=False)

    logger.info("refresh_sec_cik_cache_started", task_id=task_id)

    try:
        storage = get_storage()
        mapping = fetch_cik_mapping(storage)

        duration = calculate_duration(start_time)
        symbols_updated = len(mapping)
        save_maintenance_stat(
            "sec_cik_symbols_updated",
            float(symbols_updated),
            "count",
        )

        result_dict: dict[str, Any] = {
            "task_id": task_id,
            "symbols_updated": symbols_updated,
            "duration_seconds": round(duration, 2),
            "success": True,
        }

        logger.info("refresh_sec_cik_cache_completed", **result_dict)
        record_maintenance_completion(log_id, "success", result_dict, None)
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
        error_result = {
            "task_id": task_id,
            "error": str(e),
            "success": False,
            "duration_seconds": round(duration, 2),
        }
        record_maintenance_completion(log_id, "error", error_result, str(e))
        return error_result
