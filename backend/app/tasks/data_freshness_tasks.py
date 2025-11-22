"""Celery task for automated data freshness monitoring and refresh.

VISION.md requirement: <24 hour data freshness for all monitored tickers
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage import get_storage

if TYPE_CHECKING:
    from celery import Task  # type: ignore[import-untyped]

logger = get_logger(__name__)


def _check_data_freshness_impl() -> dict[str, Any]:
    """Check watchlist data freshness and identify stale tickers.

    Returns:
        Dict with tickers_checked, stale_found, details list
    """
    storage = get_storage()
    freshness_threshold = dt.timedelta(hours=24)
    now = dt.datetime.now(dt.UTC)

    with storage.connection() as conn:
        # Get all watchlist items with last snapshot timestamp
        result = conn.execute(
            """
            SELECT
                wi.symbol,
                MAX(ws.fetched_at) as last_fetched
            FROM watchlist_items wi
            LEFT JOIN watchlist_snapshots ws ON wi.id = ws.item_id
            GROUP BY wi.symbol
            """
        ).fetchdf()

    if result.empty:
        return {
            "tickers_checked": 0,
            "stale_found": 0,
            "stale_tickers": [],
        }

    # Calculate staleness
    result["age_hours"] = (
        (now - result["last_fetched"]).dt.total_seconds() / 3600
        if "last_fetched" in result
        else 999
    )
    result["is_stale"] = result["age_hours"] > 24

    stale_tickers = result[result["is_stale"]]["symbol"].tolist() if "is_stale" in result else []

    return {
        "tickers_checked": len(result),
        "stale_found": len(stale_tickers),
        "stale_tickers": stale_tickers,
    }


@celery_app.task(name="maintain_data_freshness", bind=True)  # type: ignore[misc]
def maintain_data_freshness(self: Task) -> dict[str, Any]:
    """Check all watchlist tickers for freshness and auto-refresh stale data.

    VISION.md requirement: <24 hour data freshness for all monitored tables

    Process:
    1. Query all watchlist items for last fetched_at timestamp
    2. Identify tickers with >24 hour stale data
    3. Auto-refresh stale tickers using existing refresh mechanism
    4. Log freshness violations for monitoring
    5. Return summary metrics

    Returns:
        Dict with status, tickers_checked, stale_found, refreshed, failed counts
    """
    task_id = self.request.id
    start_time = dt.datetime.now(dt.UTC)
    logger.info("maintain_data_freshness_started", task_id=task_id)

    try:
        # Check freshness
        freshness_result = _check_data_freshness_impl()
        stale_tickers = freshness_result["stale_tickers"]

        if not stale_tickers:
            duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
            result = {
                "status": "success",
                "tickers_checked": freshness_result["tickers_checked"],
                "stale_found": 0,
                "refreshed": 0,
                "failed": 0,
                "execution_time_sec": round(duration, 2),
            }
            logger.info("maintain_data_freshness_completed_no_stale", **result)
            return result

        # Refresh stale tickers by triggering full watchlist refresh
        # Note: refresh_watchlist_scores_task refreshes all tickers
        from app.tasks.watchlist_tasks import refresh_watchlist_scores_task

        try:
            refresh_watchlist_scores_task.apply(args=["default"])
            refreshed = len(stale_tickers)
            failed = 0
            logger.info("watchlist_refreshed", stale_count=len(stale_tickers))
        except Exception as e:
            refreshed = 0
            failed = len(stale_tickers)
            logger.error("watchlist_refresh_failed", error=str(e))

        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        result = {
            "status": "success",
            "tickers_checked": freshness_result["tickers_checked"],
            "stale_found": len(stale_tickers),
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
