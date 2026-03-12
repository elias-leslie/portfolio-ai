"""Tasks for OHLCV price data ingestion.

This module defines background tasks for ingesting historical and daily OHLCV data.
Internal helpers live in _ohlcv_helpers.py.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.ingestion._ohlcv_helpers import (
    empty_result,
    load_watchlist_symbols,
    run_ingestion_pipeline,
    run_watchlist_pipeline,
)
from app.utils.task_lifecycle import task_cleanup
from app.utils.task_locks import generate_task_lock_key, task_lock

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared implementation
# ---------------------------------------------------------------------------


def _ingest_historical_ohlcv_impl(
    symbols: list[str], days: int = 252, task_id: str | None = None
) -> dict[str, int | str | float]:
    """Run the OHLCV ingestion pipeline. Shared by ingest_historical_ohlcv and refresh_daily_ohlcv."""
    ingest_run_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    logger.info(
        "ingest_historical_ohlcv_started",
        task_id=task_id,
        ingest_run_id=ingest_run_id,
        symbols_count=len(symbols),
        days=days,
    )
    try:
        return run_ingestion_pipeline(symbols, days, task_id, ingest_run_id, start_time)
    except Exception as e:
        logger.error(
            "ingest_historical_ohlcv_failed",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise


# ---------------------------------------------------------------------------
# Public task functions
# ---------------------------------------------------------------------------


def refresh_daily_ohlcv(
    symbols: list[str] | None = None,
) -> dict[str, int | str | float]:
    """Refresh latest OHLCV data for critical symbols (SPY by default).

    Fetches the most recent 5 trading days to ensure fresh data,
    scheduled to run daily to keep day_bars table current.

    Args:
        symbols: List of symbols (default: ["SPY"]).

    Returns:
        Dict with task results:
        - task_id, ingest_run_id, symbols_count, rows_inserted, errors.

    Example:
        >>> refresh_daily_ohlcv()
        >>> refresh_daily_ohlcv(["SPY", "QQQ", "IWM"])
    """
    if symbols is None:
        symbols = ["SPY"]

    task_id = str(uuid.uuid4())
    logger.info("refresh_daily_ohlcv_started", task_id=task_id, symbols=symbols)

    try:
        return _ingest_historical_ohlcv_impl(symbols, days=5, task_id=task_id)
    except Exception as e:
        logger.error(
            "refresh_daily_ohlcv_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise
    finally:
        task_cleanup("refresh_daily_ohlcv")


def refresh_watchlist_ohlcv() -> dict[str, int | str | float]:
    """Refresh latest OHLCV data for all watchlist symbols (5-day window, daily at 02:15 UTC)."""
    task_id = str(uuid.uuid4())
    ingest_run_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    try:
        storage = get_storage()
        symbols = load_watchlist_symbols(storage, task_id)
        if not symbols:
            return empty_result(task_id, ingest_run_id)
        return run_watchlist_pipeline(storage, symbols, task_id, ingest_run_id, start_time)
    except Exception as e:
        logger.error(
            "refresh_watchlist_ohlcv_failed",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        raise
    finally:
        task_cleanup("refresh_watchlist_ohlcv")


def ingest_historical_ohlcv(
    symbols: list[str], days: int = 252
) -> dict[str, int | str | float]:
    """Backfill historical OHLCV data using multi-source fetcher.

    Uses a Redis-based task lock to prevent duplicate concurrent executions
    for the same symbol set.

    Args:
        symbols: Symbols to fetch.
        days: Trading-day lookback window (default: 252 = ~1 year).

    Returns:
        Dict with task results:
        - task_id, ingest_run_id, symbols_count, rows_inserted,
          duration_seconds, errors; or skipped=True if lock not acquired.

    Example:
        >>> ingest_historical_ohlcv(["AAPL", "MSFT", "GOOGL"], days=252)
    """
    lock_key = generate_task_lock_key("ingest_historical_ohlcv", symbols, days)

    with task_lock(lock_key, ttl=600) as acquired:
        if not acquired:
            logger.info(
                "ingest_historical_ohlcv_skipped_duplicate",
                task_id=str(uuid.uuid4()),
                symbols=symbols,
                days=days,
                reason="duplicate_task_running",
            )
            return {
                "task_id": str(uuid.uuid4()),
                "skipped": True,
                "reason": "duplicate_task_running",
                "symbols_count": len(symbols),
            }

        try:
            return _ingest_historical_ohlcv_impl(symbols, days, str(uuid.uuid4()))
        finally:
            task_cleanup("ingest_historical_ohlcv")
