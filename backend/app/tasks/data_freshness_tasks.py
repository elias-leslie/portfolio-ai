"""Celery task for automated data freshness monitoring and refresh.

VISION.md requirement: <24 hour data freshness for all monitored symbols
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.services.data_freshness_service import check_all_tables_freshness
from app.services.maintenance_tracker import record_maintenance_completion, record_maintenance_start
from app.storage import get_storage
from app.storage.connection import get_connection_manager
from app.tasks.watchlist_tasks import refresh_watchlist_scores_task

if TYPE_CHECKING:
    from celery import Task

logger = get_logger(__name__)


def _check_data_freshness_impl() -> dict[str, Any]:
    """Check watchlist data freshness and identify stale symbols.

    Returns:
        Dict with symbols_checked, stale_found, details list
    """
    storage = get_storage()
    now = dt.datetime.now(dt.UTC)

    with storage.connection() as conn:
        # Get all watchlist items with last snapshot timestamp
        rows = conn.execute(
            """
            SELECT
                wi.symbol,
                MAX(ws.fetched_at) as last_fetched
            FROM watchlist_items wi
            LEFT JOIN watchlist_snapshots_v ws ON wi.id = ws.item_id
            GROUP BY wi.symbol
            """
        ).fetchall()

    if len(rows) == 0:
        return {
            "symbols_checked": 0,
            "stale_found": 0,
            "stale_symbols": [],
        }

    # Calculate staleness from raw rows (symbol, last_fetched)
    stale_symbols: list[str] = []
    for row in rows:
        symbol = str(row[0]) if row[0] is not None else ""
        last_fetched = row[1]

        if not symbol:
            continue

        if last_fetched is None:
            # No snapshot data yet - symbol is stale
            stale_symbols.append(symbol)
        elif isinstance(last_fetched, dt.datetime):
            # Check if older than 24 hours
            age = now - last_fetched
            if age.total_seconds() > 24 * 3600:
                stale_symbols.append(symbol)
        else:
            # Unknown type - consider stale
            stale_symbols.append(symbol)

    return {
        "symbols_checked": len(rows),
        "stale_found": len(stale_symbols),
        "stale_symbols": stale_symbols,
    }


@celery_app.task(
    bind=True,
    name="maintain_data_freshness",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def maintain_data_freshness(self: Task[..., Any]) -> dict[str, Any]:
    """Check all watchlist symbols for freshness and auto-refresh stale data.

    VISION.md requirement: <24 hour data freshness for all monitored tables

    Process:
    1. Query all watchlist items for last fetched_at timestamp
    2. Identify symbols with >24 hour stale data
    3. Auto-refresh stale symbols using existing refresh mechanism
    4. Log freshness violations for monitoring
    5. Return summary metrics

    Returns:
        Dict with status, symbols_checked, stale_found, refreshed, failed counts
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)
    logger.info("maintain_data_freshness_started", task_id=task_id)

    try:
        # Check freshness
        freshness_result = _check_data_freshness_impl()
        stale_symbols = freshness_result["stale_symbols"]

        if not stale_symbols:
            duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
            result = {
                "status": "success",
                "symbols_checked": freshness_result["symbols_checked"],
                "stale_found": 0,
                "refreshed": 0,
                "failed": 0,
                "execution_time_sec": round(duration, 2),
            }
            logger.info("maintain_data_freshness_completed_no_stale", **result)
            return result

        # Refresh stale symbols by triggering full watchlist refresh
        # Note: refresh_watchlist_scores_task refreshes all symbols
        try:
            refresh_watchlist_scores_task.apply(args=("default",))
            refreshed = len(stale_symbols)
            failed = 0
            logger.info("watchlist_refreshed", stale_count=len(stale_symbols))
        except Exception as e:
            refreshed = 0
            failed = len(stale_symbols)
            logger.error("watchlist_refresh_failed", error=str(e))

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        result = {
            "status": "success",
            "symbols_checked": freshness_result["symbols_checked"],
            "stale_found": len(stale_symbols),
            "refreshed": refreshed,
            "failed": failed,
            "execution_time_sec": round(duration, 2),
        }

        logger.info("maintain_data_freshness_completed", **result)
        return result

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        logger.error(
            "maintain_data_freshness_failed",
            task_id=task_id,
            error=str(e),
            duration_seconds=round(duration, 2),
        )
        return {
            "status": "failed",
            "error": str(e),
            "execution_time_sec": round(duration, 2),
        }


@celery_app.task(
    bind=True,
    name="check_all_data_freshness",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def check_all_data_freshness(self: Task[..., Any], auto_remediate: bool = True) -> dict[str, Any]:
    """Comprehensive data freshness check for all critical tables with auto-remediation.

    VISION.md requirement: <24 hour data freshness for all monitored tables

    Process:
    1. Query MAX(date_column) for each configured table
    2. Calculate age in hours
    3. Create maintenance_log alerts for critically stale tables
    4. Trigger refresh tasks for stale/critical tables (if auto_remediate=True)
    5. Skip weekend/holiday alerts for market data tables
    6. Return summary metrics

    Args:
        auto_remediate: If True, automatically trigger refresh tasks for stale data

    Returns:
        Dict with status, tables_checked, fresh, stale, critical, alerts_created, remediations_triggered
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)
    logger.info("check_all_data_freshness_started", task_id=task_id, auto_remediate=auto_remediate)

    # Record start in maintenance_log
    log_id = record_maintenance_start(task_name="check_all_data_freshness", dry_run=False)

    try:
        # Get database connection
        storage = get_connection_manager()

        # Check all tables with auto-remediation
        result = check_all_tables_freshness(storage, auto_remediate=auto_remediate)

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()

        # Build response
        response = {
            "status": "success",
            "tables_checked": result["tables_checked"],
            "fresh": result["fresh"],
            "stale": result["stale"],
            "critical": result["critical"],
            "alerts_created": result["alerts_created"],
            "remediations_triggered": result.get("remediations_triggered", 0),
            "execution_time_sec": round(duration, 2),
        }

        # Record completion in maintenance_log
        record_maintenance_completion(
            log_id=log_id,
            status="success",
            summary=response,
            error_message=None,
        )

        logger.info("check_all_data_freshness_completed", **response)
        return response

    except Exception as e:
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        error_msg = str(e)

        # Record failure in maintenance_log
        record_maintenance_completion(
            log_id=log_id,
            status="error",
            summary={"execution_time_sec": round(duration, 2)},
            error_message=error_msg,
        )

        logger.error(
            "check_all_data_freshness_failed",
            task_id=task_id,
            error=error_msg,
            duration_seconds=round(duration, 2),
        )
        return {
            "status": "failed",
            "error": error_msg,
            "execution_time_sec": round(duration, 2),
        }
