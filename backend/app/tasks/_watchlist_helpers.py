"""Helper functions for watchlist tasks.

Extracted DB queries, trigger logic, and refresh implementation details
to keep watchlist_tasks.py concise.
"""

from __future__ import annotations

import datetime as dt
import time

from app.constants import DEFAULT_BACKFILL_DAYS
from app.logging_config import get_logger
from app.models.preferences import MIN_WATCHLIST_REFRESH_MINUTES
from app.services.preferences_service import get_automation_preferences
from app.storage import PortfolioStorage, get_storage
from app.tasks.types import WatchlistResultDict
from app.utils.market_hours import is_market_hours
from app.utils.task_logging import task_logger
from app.watchlist.scoring_service import (
    refresh_watchlist_scores as refresh_watchlist_scores_service,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def get_refresh_interval(storage: PortfolioStorage, account_id: str) -> int:
    """Return watchlist refresh interval in minutes from user preferences."""
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT
                COALESCE(watchlist_refresh_override, default_refresh_minutes, 15) AS refresh_interval,
                watchlist_refresh_override IS NOT NULL AS using_override
            FROM user_preferences
            WHERE id = %s
            """,
            [account_id],
        ).fetchone()

    if not result:
        logger.debug("watchlist_refresh_no_preferences", account_id=account_id, refresh_interval_minutes=15)
        return 15

    raw_minutes = int(result[0]) if result[0] is not None else MIN_WATCHLIST_REFRESH_MINUTES
    minutes = max(raw_minutes, MIN_WATCHLIST_REFRESH_MINUTES)
    if minutes != raw_minutes:
        logger.info(
            "watchlist_refresh_interval_clamped",
            account_id=account_id,
            requested_refresh_minutes=raw_minutes,
            applied_refresh_minutes=minutes,
        )
    event = "watchlist_refresh_using_override" if result[1] else "watchlist_refresh_using_default"
    logger.debug(event, account_id=account_id, refresh_interval_minutes=minutes)
    return minutes


def get_last_refresh_time(storage: PortfolioStorage) -> dt.datetime | None:
    """Return timestamp of last watchlist refresh, or None if never refreshed."""
    with storage.connection() as conn:
        row = conn.execute(
            "SELECT MAX(fetched_at) AS last_refresh FROM watchlist_snapshots_v"
        ).fetchone()

    if not row or not row[0]:
        return None
    value = row[0]
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, str):
        return dt.datetime.fromisoformat(value)
    return None


def get_watchlist_symbols(storage: PortfolioStorage) -> list[str]:
    """Return distinct symbols from watchlist_items."""
    with storage.connection() as conn:
        rows = conn.execute("SELECT DISTINCT symbol FROM watchlist_items").fetchall()
    return [str(row[0]) for row in rows if row[0] is not None]


# ---------------------------------------------------------------------------
# Trigger helpers
# ---------------------------------------------------------------------------


def trigger_strategy_generation_for_top_symbols() -> None:
    """Trigger async strategy generation for top watchlist symbols (auto-001)."""
    automation = get_automation_preferences()
    if not bool(automation["scheduled_strategy_research_enabled"]["enabled"]):
        logger.info("strategy_generation_trigger_skipped", reason="scheduled_strategy_research_disabled")
        return
    try:
        from app.tasks.strategy.generation_tasks import trigger_strategies_for_top_watchlist

        trigger_strategies_for_top_watchlist()
        logger.info("strategy_generation_triggered_from_watchlist")
    except Exception as e:
        logger.warning("strategy_generation_trigger_failed", error=str(e), error_type=type(e).__name__)


def trigger_auto_backfill(storage: PortfolioStorage) -> None:
    """Check for missing historical data and trigger backfill if needed."""
    try:
        _run_auto_backfill(storage)
    except Exception as e:
        logger.error("auto_backfill_failed_from_task", error=str(e), error_type=type(e).__name__, exc_info=True)


def _run_auto_backfill(storage: PortfolioStorage) -> None:
    """Inner logic for auto-backfill (separated for error isolation)."""
    from app.watchlist.refresh_data_fetchers import detect_missing_historical_data

    symbols = get_watchlist_symbols(storage)
    if not symbols:
        return

    symbols_needing_backfill = detect_missing_historical_data(
        storage=storage, symbols=symbols, min_days=30, stale_threshold_days=7
    )
    if not symbols_needing_backfill:
        return

    logger.info("auto_backfill_triggered_from_task", symbol_count=len(symbols_needing_backfill), symbols=symbols_needing_backfill)

    from app.tasks.ingestion import ingest_historical_ohlcv

    ingest_historical_ohlcv(symbols_needing_backfill, days=DEFAULT_BACKFILL_DAYS)
    logger.info("auto_backfill_task_dispatched_from_task", symbol_count=len(symbols_needing_backfill))


# ---------------------------------------------------------------------------
# Refresh implementation helpers
# ---------------------------------------------------------------------------


def build_skip_result(
    task_id: str,
    minutes_since_refresh: float,
    refresh_interval_minutes: int,
    start_time: float,
) -> WatchlistResultDict:
    """Build result dict for a skipped refresh."""
    return {
        "task_id": task_id,
        "skipped": True,
        "reason": "refresh_interval_not_met",
        "minutes_since_refresh": round(minutes_since_refresh, 1),
        "refresh_interval_minutes": refresh_interval_minutes,
        "duration_seconds": round(time.time() - start_time, 2),
    }


def check_interval(
    last_refresh: dt.datetime | None,
    refresh_interval_minutes: int,
    force: bool,
    task_id: str,
    account_id: str,
    skip_check_start: float,
    start_time: float,
) -> WatchlistResultDict | None:
    """Return a skip result if the refresh interval has not been met, else None."""
    if not last_refresh or force:
        if force:
            logger.info("refresh_watchlist_scores_forced", task_id=task_id, account_id=account_id, reason="force_flag_set")
        return None

    aware_last = (
        last_refresh.replace(tzinfo=dt.UTC) if last_refresh.tzinfo is None else last_refresh.astimezone(dt.UTC)
    )
    minutes_since_refresh = (dt.datetime.now(dt.UTC) - aware_last).total_seconds() / 60.0

    if minutes_since_refresh >= refresh_interval_minutes:
        return None

    logger.debug(
        "refresh_watchlist_scores_skipped",
        task_name="refresh_watchlist_scores",
        task_id=task_id,
        status="skipped",
        reason="refresh_interval_not_met",
        duration_ms=round((time.perf_counter() - skip_check_start) * 1000, 2),
        account_id=account_id,
        minutes_since_refresh=round(minutes_since_refresh, 1),
        refresh_interval_minutes=refresh_interval_minutes,
    )
    return build_skip_result(task_id, minutes_since_refresh, refresh_interval_minutes, start_time)


def execute_refresh(
    account_id: str,
    task_id: str,
    refresh_interval_minutes: int,
    start_time: float,
) -> WatchlistResultDict:
    """Run the actual watchlist score refresh and return a typed result."""
    markets_open = is_market_hours()
    storage = get_storage()

    with task_logger(
        "refresh_watchlist_scores",
        task_id,
        {"account_id": account_id, "refresh_interval_minutes": refresh_interval_minutes, "markets_open": markets_open},
    ):
        result = refresh_watchlist_scores_service(
            storage,
            account_id=account_id,
            include_news=False,
        )
        duration = round(time.time() - start_time, 2)
        result.update({"task_id": task_id, "markets_open": markets_open, "refresh_interval_minutes": refresh_interval_minutes, "duration_seconds": duration})
        logger.info("watchlist_scores_refreshed", task_id=task_id, processed=result.get("processed", 0), markets_open=markets_open)

        return {
            "task_id": task_id,
            "processed": result.get("processed", 0),
            "skipped": result.get("skipped", 0),
            "failed": result.get("failed", 0),
            "markets_open": markets_open,
            "refresh_interval_minutes": refresh_interval_minutes,
            "duration_seconds": result.get("duration_seconds", duration),
        }


def refresh_single_symbol_impl(task_id: str, symbol: str, start_time: float) -> dict[str, object]:
    """Inner logic for single-symbol refresh (separated from lock context)."""
    try:
        storage = get_storage()
        logger.info("refresh_single_symbol_started", task_id=task_id, symbol=symbol)

        result = refresh_watchlist_scores_service(storage, symbols_filter=[symbol], batch_size=1)
        duration = round(time.time() - start_time, 2)
        logger.info("refresh_single_symbol_completed", task_id=task_id, symbol=symbol, processed=result.get("processed", 0), duration_seconds=duration)

        return {
            "task_id": task_id,
            "symbol": symbol,
            "processed": result.get("processed", 0),
            "success": symbol in result.get("success", []),
            "duration_seconds": duration,
        }
    except Exception as exc:
        logger.error("refresh_single_symbol_failed", task_id=task_id, symbol=symbol, error=str(exc), exc_info=True)
        raise
