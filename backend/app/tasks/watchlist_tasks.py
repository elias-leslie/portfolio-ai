"""Tasks for watchlist score refresh.

This module defines background tasks for refreshing watchlist scores asynchronously.
"""

from __future__ import annotations

import time
import uuid

from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks._watchlist_helpers import (
    check_interval,
    execute_refresh,
    get_last_refresh_time,
    get_refresh_interval,
    refresh_single_symbol_impl,
    trigger_auto_backfill,
)
from app.tasks.types import WatchlistResultDict
from app.utils.task_locks import task_lock

logger = get_logger(__name__)


def _refresh_watchlist_scores_impl(
    account_id: str,
    skip_check_start: float,
    start_time: float,
    task_id: str,
    force: bool = False,
) -> WatchlistResultDict:
    """Implementation of watchlist score refresh (extracted for lock context)."""
    try:
        storage = get_storage()
        refresh_interval_minutes = get_refresh_interval(storage, account_id)
        last_refresh = get_last_refresh_time(storage)

        skip_result = check_interval(
            last_refresh, refresh_interval_minutes, force,
            task_id, account_id, skip_check_start, start_time,
        )
        if skip_result is not None:
            return skip_result

        trigger_auto_backfill(storage)
        return execute_refresh(account_id, task_id, refresh_interval_minutes, start_time)

    except Exception as exc:  # pragma: no cover - safety net
        logger.error(
            "watchlist_refresh_task_failed",
            task_id=task_id,
            account_id=account_id,
            error=str(exc),
        )
        raise


def refresh_watchlist_scores_task(
    account_id: str | None = None, force: bool = False
) -> WatchlistResultDict:
    """Refresh watchlist scores for all items or a specific account.

    This task runs every 1 minute via Hatchet cron, but respects the user's
    watchlist_refresh_minutes preference by skipping execution if not enough
    time has passed since the last refresh.

    Uses Redis-based task lock to prevent duplicate concurrent executions.

    Note: This task checks market hours for logging, but refreshes 24/7.
    """
    skip_check_start = time.perf_counter()
    start_time = time.time()
    task_id = str(uuid.uuid4())
    account_id = account_id or "default"

    lock_key = f"refresh_watchlist_scores:{account_id}"
    with task_lock(lock_key, ttl=300) as acquired:
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
            account_id, skip_check_start, start_time, task_id, force
        )


def refresh_single_symbol_scores_task(symbol: str) -> dict[str, object]:
    """Refresh scores for a single symbol immediately (no rate limit check).

    This task is designed for newly-added symbols that need immediate scoring.
    It bypasses the global refresh interval check and only processes one symbol.

    Args:
        symbol: Stock symbol to refresh

    Returns:
        Dict with processing result for the single symbol
    """
    task_id = str(uuid.uuid4())
    start_time = time.time()

    lock_key = f"refresh_single_symbol:{symbol}"
    with task_lock(lock_key, ttl=120) as acquired:
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
        return refresh_single_symbol_impl(task_id, symbol, start_time)
