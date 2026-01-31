"""Celery tasks for watchlist score refresh.

This module defines background tasks for refreshing watchlist scores asynchronously.
"""

from __future__ import annotations

import datetime as dt
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from celery import Task

from app.celery_app import celery_app
from app.constants import DEFAULT_BACKFILL_DAYS
from app.logging_config import get_logger
from app.storage import PortfolioStorage, get_storage
from app.tasks.types import WatchlistResultDict
from app.utils.market_hours import is_market_hours
from app.utils.task_locks import task_lock
from app.utils.task_logging import log_task_skip, task_logger
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
            refresh_interval_minutes = int(result[0]) if result[0] is not None else 15
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
            FROM watchlist_snapshots_v
            """
        ).fetchone()

        if last_refresh_result and last_refresh_result[0]:
            value = last_refresh_result[0]
            if isinstance(value, dt.datetime):
                return value
            # Try to parse if it's a string
            if isinstance(value, str):
                return dt.datetime.fromisoformat(value)
        return None


def _trigger_strategy_generation_for_top_symbols() -> None:
    """Trigger async strategy generation for top watchlist symbols (auto-001).

    Dispatches the trigger_strategies_for_top_watchlist task with backpressure check.
    The task itself handles rate limiting (max 3/day).
    """
    try:
        from ..services.celery_inspector import should_skip_cascade

        # Check queue backpressure before scheduling strategy generation
        if should_skip_cascade():
            logger.info(
                "strategy_generation_skipped_backpressure",
                reason="queue_depth_exceeded",
            )
            return

        # Import and dispatch strategy generation task
        from .strategy.generation_tasks import (
            trigger_strategies_for_top_watchlist,
        )

        trigger_strategies_for_top_watchlist.delay()
        logger.info("strategy_generation_triggered_from_watchlist")

    except Exception as e:
        logger.warning(
            "strategy_generation_trigger_failed",
            error=str(e),
            error_type=type(e).__name__,
        )


def _trigger_auto_backfill(storage: PortfolioStorage) -> None:
    """Check for missing historical data and trigger backfill if needed.

    Uses backpressure check to prevent queue saturation during high load.

    Args:
        storage: Storage instance for database operations
    """
    try:
        from ..services.celery_inspector import should_skip_cascade
        from ..watchlist.service import detect_missing_historical_data

        # Check queue backpressure before scheduling more work
        if should_skip_cascade():
            logger.info("auto_backfill_skipped_backpressure", reason="queue_depth_exceeded")
            return

        # Load watchlist items to get symbols
        with storage.connection() as conn:
            items_result = conn.execute(
                """
                SELECT DISTINCT symbol
                FROM watchlist_items
                """
            ).fetchall()
            symbols = [str(row[0]) for row in items_result if row[0] is not None]

        if symbols:
            symbols_needing_backfill = detect_missing_historical_data(
                storage=storage,
                symbols=symbols,
                min_days=30,
                stale_threshold_days=7,
            )

            if symbols_needing_backfill:
                logger.info(
                    "auto_backfill_triggered_from_task",
                    symbol_count=len(symbols_needing_backfill),
                    symbols=symbols_needing_backfill,
                )

                # Import here to avoid circular dependency
                from .ingestion import ingest_historical_ohlcv

                # Trigger async backfill (non-blocking)
                ingest_historical_ohlcv.delay(symbols_needing_backfill, days=DEFAULT_BACKFILL_DAYS)

                logger.info(
                    "auto_backfill_task_dispatched_from_task",
                    symbol_count=len(symbols_needing_backfill),
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
) -> WatchlistResultDict:
    """Build result dictionary for skipped refresh.

    Args:
        task_id: Celery task ID
        minutes_since_refresh: Minutes elapsed since last refresh
        refresh_interval_minutes: Configured refresh interval
        start_time: Task start time

    Returns:
        WatchlistResultDict with skip result
    """
    return {
        "task_id": task_id,
        "skipped": True,
        "reason": "refresh_interval_not_met",
        "minutes_since_refresh": round(minutes_since_refresh, 1),
        "refresh_interval_minutes": refresh_interval_minutes,
        "duration_seconds": round(time.time() - start_time, 2),
    }


@celery_app.task(name="refresh_watchlist_scores", bind=True)
def refresh_watchlist_scores_task(
    self: Task[..., Any], account_id: str | None = None, force: bool = False
) -> WatchlistResultDict:
    """Refresh watchlist scores for all items or a specific account.

    This task runs every 1 minute via Celery Beat, but respects the user's
    watchlist_refresh_minutes preference by skipping execution if not enough
    time has passed since the last refresh.

    Uses Redis-based task lock to prevent duplicate concurrent executions.

    Note: This task checks market hours for logging, but refreshes 24/7.
    """
    skip_check_start = time.perf_counter()  # For skip duration measurement
    start_time = time.time()  # For result duration_seconds
    task_id = self.request.id or "unknown"
    account_id = account_id or "default"

    # Use task lock to prevent duplicate concurrent executions
    lock_key = f"refresh_watchlist_scores:{account_id}"
    with task_lock(lock_key, ttl=300) as acquired:  # 5-minute lock
        if not acquired:
            logger.info(
                "refresh_watchlist_scores_skipped_duplicate",
                task_id=task_id,
                account_id=account_id,
                reason="duplicate_task_running",
            )
            return {
                "task_id": task_id,
                "skipped": True,
                "reason": "duplicate_task_running",
                "duration_seconds": round(time.time() - start_time, 2),
            }

        return _refresh_watchlist_scores_impl(
            self, account_id, skip_check_start, start_time, task_id, force
        )


def _refresh_watchlist_scores_impl(
    self: Task[..., Any],
    account_id: str,
    skip_check_start: float,
    start_time: float,
    task_id: str,
    force: bool = False,
) -> WatchlistResultDict:
    """Implementation of watchlist score refresh (extracted for lock context).

    Args:
        force: If True, bypass rate limit check (used for new symbol adds)
    """
    try:
        storage = get_storage()

        # Get refresh interval from user preferences
        refresh_interval_minutes = _get_refresh_interval(storage, account_id)

        # Get last refresh time from most recent snapshot
        last_refresh = _get_last_refresh_time(storage)

        # Calculate time since last refresh
        now = dt.datetime.now(dt.UTC)
        if last_refresh and not force:
            # Ensure last_refresh is timezone-aware
            if last_refresh.tzinfo is None:
                last_refresh = last_refresh.replace(tzinfo=dt.UTC)
            else:
                last_refresh = last_refresh.astimezone(dt.UTC)

            minutes_since_refresh = (now - last_refresh).total_seconds() / 60.0

            # Skip if not enough time has passed (check BEFORE auto-backfill to avoid cascade spam)
            # NOTE: force=True bypasses this check (used for new symbol adds)
            if minutes_since_refresh < refresh_interval_minutes:
                skip_duration_ms = (time.perf_counter() - skip_check_start) * 1000
                log_task_skip(
                    task_name="refresh_watchlist_scores",
                    task_id=task_id,
                    reason="refresh_interval_not_met",
                    duration_ms=skip_duration_ms,
                    extra_fields={
                        "account_id": account_id,
                        "minutes_since_refresh": round(minutes_since_refresh, 1),
                        "refresh_interval_minutes": refresh_interval_minutes,
                    },
                )
                return _build_skip_result(
                    task_id=task_id,
                    minutes_since_refresh=minutes_since_refresh,
                    refresh_interval_minutes=refresh_interval_minutes,
                    start_time=start_time,
                )
        elif force:
            logger.info(
                "refresh_watchlist_scores_forced",
                task_id=task_id,
                account_id=account_id,
                reason="force_flag_set",
            )

        # AUTO-BACKFILL: Only trigger when we're actually going to refresh (not skipping)
        # This prevents cascade spam from 60-second Beat polling
        _trigger_auto_backfill(storage)

        # Proceed with refresh
        markets_open = is_market_hours()

        with task_logger(
            "refresh_watchlist_scores",
            task_id,
            {
                "account_id": account_id,
                "refresh_interval_minutes": refresh_interval_minutes,
                "markets_open": markets_open,
            },
        ):
            result = refresh_watchlist_scores_service(storage, account_id=account_id)  # type: ignore[misc]  # mypy can't infer type through lazy-loaded __getattr__
            result.update(
                {
                    "task_id": task_id,
                    "markets_open": markets_open,
                    "refresh_interval_minutes": refresh_interval_minutes,
                    "duration_seconds": round(time.time() - start_time, 2),
                }
            )

            logger.info(
                "watchlist_scores_refreshed",
                task_id=task_id,
                processed=result.get("processed", 0),
                markets_open=markets_open,
            )

            # AUTO-001: Trigger strategy generation for top watchlist symbols
            # Only trigger if we actually processed items (not a skip/error)
            if result.get("processed", 0) > 0:
                _trigger_strategy_generation_for_top_symbols()

            # Cast to proper type for return
            typed_result: WatchlistResultDict = {
                "task_id": task_id,
                "processed": result.get("processed", 0),
                "skipped": result.get("skipped", 0),
                "failed": result.get("failed", 0),
                "markets_open": markets_open,
                "refresh_interval_minutes": refresh_interval_minutes,
                "duration_seconds": result.get("duration_seconds", 0.0),
            }
            return typed_result

    except Exception as exc:  # pragma: no cover - safety net
        logger.error(
            "watchlist_refresh_task_failed",
            task_id=task_id,
            account_id=account_id,
            error=str(exc),
        )
        raise


@celery_app.task(name="refresh_single_symbol_scores", bind=True)
def refresh_single_symbol_scores_task(self: Task[..., Any], symbol: str) -> dict[str, object]:
    """Refresh scores for a single symbol immediately (no rate limit check).

    This task is designed for newly-added symbols that need immediate scoring.
    It bypasses the global refresh interval check and only processes one symbol.

    Args:
        symbol: Stock symbol to refresh

    Returns:
        Dict with processing result for the single symbol
    """
    task_id = self.request.id
    start_time = time.time()

    # Use task lock to prevent duplicate concurrent executions for same symbol
    lock_key = f"refresh_single_symbol:{symbol}"
    with task_lock(lock_key, ttl=120) as acquired:  # 2-minute lock
        if not acquired:
            logger.info(
                "refresh_single_symbol_skipped_duplicate",
                task_id=task_id,
                symbol=symbol,
                reason="duplicate_task_running",
            )
            return {
                "task_id": task_id,
                "symbol": symbol,
                "skipped": True,
                "reason": "duplicate_task_running",
            }

        try:
            storage = get_storage()

            logger.info(
                "refresh_single_symbol_started",
                task_id=task_id,
                symbol=symbol,
            )

            # Call scoring service with symbols_filter for just this one symbol
            result = refresh_watchlist_scores_service(  # type: ignore[misc]  # mypy can't infer type through lazy-loaded __getattr__
                storage,
                symbols_filter=[symbol],
                batch_size=1,  # Single symbol, minimal batch
            )

            duration = round(time.time() - start_time, 2)
            logger.info(
                "refresh_single_symbol_completed",
                task_id=task_id,
                symbol=symbol,
                processed=result.get("processed", 0),
                duration_seconds=duration,
            )

            return {
                "task_id": task_id,
                "symbol": symbol,
                "processed": result.get("processed", 0),
                "success": symbol in result.get("success", []),
                "duration_seconds": duration,
            }

        except Exception as exc:
            logger.error(
                "refresh_single_symbol_failed",
                task_id=task_id,
                symbol=symbol,
                error=str(exc),
            )
            raise
