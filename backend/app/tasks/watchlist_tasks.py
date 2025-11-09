"""Celery tasks for watchlist score refresh.

This module defines background tasks for refreshing watchlist scores asynchronously.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage import PortfolioStorage, get_storage
from app.utils.market_hours import is_market_hours
from app.watchlist.service import refresh_watchlist_scores as refresh_watchlist_scores_service

logger = get_logger(__name__)


def _get_refresh_interval(storage: PortfolioStorage, account_id: str) -> int:
    """Get watchlist refresh interval from user preferences.

    Args:
        storage: Storage instance for database operations
        account_id: Account ID to get preferences for

    Returns:
        Refresh interval in minutes
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT
                COALESCE(watchlist_refresh_override, default_refresh_minutes, 15) as refresh_interval,
                watchlist_refresh_override IS NOT NULL as using_override
            FROM user_preferences
            WHERE id = %s
            """,
            [account_id],
        ).fetchone()

        if result:
            refresh_interval_minutes = int(result[0])
            using_override = result[1]

            if using_override:
                logger.info(
                    "watchlist_refresh_using_override",
                    account_id=account_id,
                    refresh_interval_minutes=refresh_interval_minutes,
                )
            else:
                logger.info(
                    "watchlist_refresh_using_default",
                    account_id=account_id,
                    refresh_interval_minutes=refresh_interval_minutes,
                )
        else:
            refresh_interval_minutes = 15  # Fallback if no preferences found
            logger.info(
                "watchlist_refresh_no_preferences",
                account_id=account_id,
                refresh_interval_minutes=refresh_interval_minutes,
            )

        return refresh_interval_minutes


def _get_last_refresh_time(storage: PortfolioStorage) -> dt.datetime | None:
    """Get timestamp of last watchlist refresh.

    Args:
        storage: Storage instance for database operations

    Returns:
        Timestamp of last refresh, or None if never refreshed
    """
    with storage.connection() as conn:
        last_refresh_result = conn.execute(
            """
            SELECT MAX(fetched_at) as last_refresh
            FROM watchlist_snapshots
            """
        ).fetchone()

        return last_refresh_result[0] if last_refresh_result and last_refresh_result[0] else None


def _trigger_auto_backfill(storage: PortfolioStorage) -> None:
    """Check for missing historical data and trigger backfill if needed.

    Args:
        storage: Storage instance for database operations
    """
    try:
        from ..watchlist.service import detect_missing_historical_data  # noqa: PLC0415

        # Load watchlist items to get symbols
        with storage.connection() as conn:
            items_result = conn.execute(
                """
                SELECT DISTINCT symbol
                FROM watchlist_items
                """
            ).fetchall()
            symbols = [row[0] for row in items_result]

        if symbols:
            tickers_needing_backfill = detect_missing_historical_data(
                storage=storage,
                symbols=symbols,
                min_days=30,
                stale_threshold_days=7,
            )

            if tickers_needing_backfill:
                logger.info(
                    "auto_backfill_triggered_from_task",
                    ticker_count=len(tickers_needing_backfill),
                    tickers=tickers_needing_backfill,
                )

                # Import here to avoid circular dependency
                from .data_ingestion_tasks import ingest_historical_ohlcv  # noqa: PLC0415

                # Trigger async backfill (non-blocking)
                ingest_historical_ohlcv.delay(tickers_needing_backfill, days=252)

                logger.info(
                    "auto_backfill_task_dispatched_from_task",
                    ticker_count=len(tickers_needing_backfill),
                )
    except Exception as e:
        logger.error(
            "auto_backfill_failed_from_task",
            error=str(e),
            error_type=type(e).__name__,
        )


def _build_skip_result(
    task_id: str,
    minutes_since_refresh: float,
    refresh_interval_minutes: int,
    start_time: float,
) -> dict[str, Any]:
    """Build result dictionary for skipped refresh.

    Args:
        task_id: Celery task ID
        minutes_since_refresh: Minutes elapsed since last refresh
        refresh_interval_minutes: Configured refresh interval
        start_time: Task start time

    Returns:
        Dict with skip result
    """
    return {
        "task_id": task_id,
        "skipped": True,
        "reason": "refresh_interval_not_met",
        "minutes_since_refresh": round(minutes_since_refresh, 1),
        "refresh_interval_minutes": refresh_interval_minutes,
        "duration_seconds": round(time.time() - start_time, 2),
    }


@celery_app.task(name="refresh_watchlist_scores", bind=True)  # type: ignore[misc]
def refresh_watchlist_scores_task(self, account_id: str | None = None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Refresh watchlist scores for all items or a specific account.

    This task runs every 1 minute via Celery Beat, but respects the user's
    watchlist_refresh_minutes preference by skipping execution if not enough
    time has passed since the last refresh.

    Note: This task checks market hours for logging, but refreshes 24/7.
    """
    start_time = time.time()  # Track task duration
    task_id = self.request.id
    account_id = account_id or "default"

    try:
        storage = get_storage()

        # Get refresh interval from user preferences
        refresh_interval_minutes = _get_refresh_interval(storage, account_id)

        # Get last refresh time from most recent snapshot
        last_refresh = _get_last_refresh_time(storage)

        # Calculate time since last refresh
        now = dt.datetime.now(dt.UTC)
        if last_refresh:
            # Ensure last_refresh is timezone-aware
            if last_refresh.tzinfo is None:
                last_refresh = last_refresh.replace(tzinfo=dt.UTC)
            else:
                last_refresh = last_refresh.astimezone(dt.UTC)

            minutes_since_refresh = (now - last_refresh).total_seconds() / 60.0

            # AUTO-BACKFILL: Check for missing historical data (runs BEFORE interval skip)
            _trigger_auto_backfill(storage)

            # Skip if not enough time has passed
            if minutes_since_refresh < refresh_interval_minutes:
                logger.info(
                    "watchlist_refresh_skipped",
                    task_id=task_id,
                    account_id=account_id,
                    minutes_since_refresh=round(minutes_since_refresh, 1),
                    refresh_interval_minutes=refresh_interval_minutes,
                    reason="Not enough time elapsed since last refresh",
                )
                return _build_skip_result(
                    task_id=task_id,
                    minutes_since_refresh=minutes_since_refresh,
                    refresh_interval_minutes=refresh_interval_minutes,
                    start_time=start_time,
                )

        # Proceed with refresh
        markets_open = is_market_hours()
        logger.info(
            "watchlist_refresh_task_started",
            task_id=task_id,
            account_id=account_id,
            markets_open=markets_open,
            refresh_interval_minutes=refresh_interval_minutes,
        )

        result = refresh_watchlist_scores_service(storage, account_id=account_id)
        result.update(
            {
                "task_id": task_id,
                "markets_open": markets_open,
                "refresh_interval_minutes": refresh_interval_minutes,
                "duration_seconds": round(time.time() - start_time, 2),
            }
        )

        logger.info(
            "watchlist_refresh_task_completed",
            task_id=task_id,
            processed=result.get("processed", 0),
            markets_open=markets_open,
            refresh_interval_minutes=refresh_interval_minutes,
            duration_seconds=result["duration_seconds"],
        )
        return result

    except Exception as exc:  # pragma: no cover - safety net
        logger.error(
            "watchlist_refresh_task_failed",
            task_id=task_id,
            account_id=account_id,
            error=str(exc),
        )
        raise
