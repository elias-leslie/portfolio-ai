"""Tasks for OHLCV price data ingestion.

This module defines background tasks for ingesting historical and daily OHLCV data.
Internal helpers live in _ohlcv_helpers.py.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.logging_config import get_logger
from app.sources.base import DatasetRequest
from app.storage import get_storage
from app.tasks.ingestion._ohlcv_helpers import (
    build_fetcher,
    build_ingestion_result,
    calculate_date_range,
    empty_result,
    fetch_ohlcv_data,
    insert_ohlcv_data,
    load_watchlist_symbols,
    upsert_watchlist_data,
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
    """Run the OHLCV ingestion pipeline for the given symbols and day count.

    Shared by :func:`ingest_historical_ohlcv` and :func:`refresh_daily_ohlcv`.

    Args:
        symbols: Symbols to fetch.
        days: Trading-day lookback window.
        task_id: Optional caller-provided task ID for logging.

    Returns:
        Dict with ingestion results.
    """
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
        fetcher, storage = build_fetcher(symbols)
        start_date, end_date = calculate_date_range(days)

        request = DatasetRequest(
            dataset="day",
            profile=None,
            symbols=symbols,
            start=start_date,
            end=end_date,
            timezone="UTC",
            ingest_run_id=ingest_run_id,
        )

        result_df, error_count, errors = fetch_ohlcv_data(fetcher, request, ingest_run_id)

        rows_inserted = 0
        if result_df is not None and len(result_df) > 0:
            rows_inserted = insert_ohlcv_data(storage, result_df, ingest_run_id)
        else:
            logger.warning("ingest_no_data_fetched", ingest_run_id=ingest_run_id, errors=errors)

        return build_ingestion_result(
            task_id=task_id or "direct",
            ingest_run_id=ingest_run_id,
            symbols=symbols,
            rows_inserted=rows_inserted,
            error_count=error_count,
            start_time=start_time,
        )

    except Exception as e:
        logger.error(
            "ingest_historical_ohlcv_failed",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            error=str(e),
            error_type=type(e).__name__,
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
        )
        raise
    finally:
        task_cleanup("refresh_daily_ohlcv")


def refresh_watchlist_ohlcv() -> dict[str, int | str | float]:
    """Refresh latest OHLCV data for all watchlist symbols.

    Fetches the most recent 5 trading days. Uses UPSERT to preserve existing
    historical data while updating recent bars.
    Scheduled daily at 02:15 UTC (after refresh-daily-ohlcv).

    Returns:
        Dict with task results:
        - task_id, ingest_run_id, symbols_count, rows_inserted, errors.

    Example:
        >>> refresh_watchlist_ohlcv()
    """
    task_id = str(uuid.uuid4())
    ingest_run_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)

    try:
        storage = get_storage()
        symbols = load_watchlist_symbols(storage, task_id)

        if not symbols:
            return empty_result(task_id, ingest_run_id)

        logger.info(
            "refresh_watchlist_ohlcv_started",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            symbols=symbols,
            symbols_count=len(symbols),
        )

        fetcher, _ = build_fetcher(symbols)
        start_date, end_date = calculate_date_range(days=5)

        request = DatasetRequest(
            dataset="day",
            profile=None,
            symbols=symbols,
            start=start_date,
            end=end_date,
            timezone="UTC",
            ingest_run_id=ingest_run_id,
        )

        result_df, error_count, errors = fetch_ohlcv_data(fetcher, request, ingest_run_id)
        rows_inserted = upsert_watchlist_data(storage, result_df, ingest_run_id, errors)

        return build_ingestion_result(
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            symbols=symbols,
            rows_inserted=rows_inserted,
            error_count=error_count,
            start_time=start_time,
            log_event="refresh_watchlist_ohlcv_completed",
        )

    except Exception as e:
        logger.error(
            "refresh_watchlist_ohlcv_failed",
            task_id=task_id,
            ingest_run_id=ingest_run_id,
            error=str(e),
            error_type=type(e).__name__,
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
