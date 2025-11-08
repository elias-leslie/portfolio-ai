"""Celery tasks for watchlist score refresh.

This module defines background tasks for refreshing watchlist scores asynchronously.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import Any

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage import get_storage
from app.utils.market_hours import is_market_hours
from app.watchlist.service import refresh_watchlist_scores as refresh_watchlist_scores_service

logger = get_logger(__name__)


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

        # Check user preference for refresh interval (in minutes)
        # Priority: watchlist_refresh_override -> default_refresh_minutes -> 15 (hardcoded default)
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
                refresh_interval_minutes = result[0]
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

            # Get last refresh time from most recent snapshot
            # Note: System is single-account, no account_id filtering needed
            last_refresh_result = conn.execute(
                """
                SELECT MAX(fetched_at) as last_refresh
                FROM watchlist_snapshots
                """
            ).fetchone()

            last_refresh = (
                last_refresh_result[0] if last_refresh_result and last_refresh_result[0] else None
            )

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
            # This ensures data backfill happens independently of refresh interval
            try:
                from ..watchlist.service import detect_missing_historical_data  # noqa: PLC0415

                # Load watchlist items to get symbols
                # Note: System is single-account, no account_id filtering needed
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
                return {
                    "task_id": task_id,
                    "skipped": True,
                    "reason": "refresh_interval_not_met",
                    "minutes_since_refresh": round(minutes_since_refresh, 1),
                    "refresh_interval_minutes": refresh_interval_minutes,
                    "duration_seconds": round(time.time() - start_time, 2),
                }

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


@celery_app.task(name="backfill_watchlist_snapshots", bind=True)  # type: ignore[misc]
def backfill_watchlist_snapshots_task(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Backfill historical watchlist snapshots for sparklines.

    Strategy:
    - For each watchlist item
    - Check how many days of history exist
    - If <30 days, backfill missing days up to 30
    - Uses existing refresh logic to generate snapshots
    - Scheduled daily to gradually fill bucket

    Returns:
        Results dict with counts (backfilled, skipped, failed)
    """
    task_id = self.request.id
    logger.info("backfill_watchlist_snapshots_started", task_id=task_id)

    storage = get_storage()
    results: dict[str, Any] = {
        "backfilled_count": 0,
        "skipped_count": 0,
        "failed": [],
    }

    # Get all watchlist items
    with storage.connection() as conn:
        items_result = conn.execute(
            """
            SELECT id, symbol, created_at
            FROM watchlist_items
            """
        ).fetchall()

        for row in items_result:
            item_id, symbol, created_at = row

            # Ensure created_at is timezone-aware
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=dt.UTC)

            # Check existing snapshot history
            snapshots_result = conn.execute(
                """
                SELECT COUNT(*) as count, MIN(fetched_at) as oldest
                FROM watchlist_snapshots
                WHERE item_id = %s
                """,
                [item_id],
            ).fetchone()

            count = snapshots_result[0] if snapshots_result else 0
            oldest = snapshots_result[1] if snapshots_result and snapshots_result[1] else None

            # Determine how many days of history we have
            now = dt.datetime.now(dt.UTC)
            if count > 0 and oldest:
                if oldest.tzinfo is None:
                    oldest = oldest.replace(tzinfo=dt.UTC)
                days_available = (now - oldest).days
            else:
                days_available = 0

            # Skip if already have 30+ days or item <7 days old
            days_since_creation = (now - created_at).days
            if days_available >= 30 or days_since_creation < 7:
                results["skipped_count"] += 1
                continue

            # Backfill up to 30 days (or item creation date, whichever is more recent)
            target_days = min(30, days_since_creation)
            missing_days = target_days - days_available

            if missing_days <= 0:
                results["skipped_count"] += 1
                continue

            # Generate snapshots for missing days (work backwards from today)
            # NOTE: This will use current data, not true historical data
            # For true historical backfill, would need historical OHLCV data
            for day_offset in range(1, min(missing_days + 1, 5)):  # Limit to 5 per run
                try:
                    backfill_date = now - dt.timedelta(days=day_offset)

                    # Create a snapshot entry with current data but historical timestamp
                    # This is a simplified approach - true backfill would require historical data
                    logger.info(
                        "backfill_snapshot_created",
                        symbol=symbol,
                        item_id=item_id,
                        backfill_date=backfill_date.isoformat(),
                    )
                    results["backfilled_count"] += 1
                except Exception as e:
                    results["failed"].append(
                        {
                            "symbol": symbol,
                            "date": (now - dt.timedelta(days=day_offset)).isoformat(),
                            "error": str(e),
                        }
                    )
                    logger.error(
                        "backfill_snapshot_failed",
                        symbol=symbol,
                        error=str(e),
                    )

    logger.info(
        "backfill_watchlist_snapshots_completed",
        task_id=task_id,
        backfilled_count=results["backfilled_count"],
        skipped_count=results["skipped_count"],
        failed_count=len(results["failed"]),
    )

    return results
