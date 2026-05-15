"""Tasks for OHLCV price data ingestion.

This module defines background tasks for ingesting historical and daily OHLCV data.
Internal helpers live in _ohlcv_helpers.py.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.constants import ALL_MARKET_SYMBOLS, DEFAULT_DAILY_REFRESH_DAYS, TRADING_DAYS_PER_YEAR
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
    symbols: list[str], days: int = TRADING_DAYS_PER_YEAR, task_id: str | None = None
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
    """Refresh latest OHLCV data for canonical market symbols.

    Fetches the most recent 5 trading days to ensure fresh data,
    scheduled to run daily to keep day_bars current for prediction,
    analytics, dashboards, alerts, and reporting.

    Args:
        symbols: List of symbols (default: canonical market symbols).

    Returns:
        Dict with task results:
        - task_id, ingest_run_id, symbols_count, rows_inserted, errors.

    Example:
        >>> refresh_daily_ohlcv()
        >>> refresh_daily_ohlcv(["SPY", "QQQ", "IWM"])
    """
    if symbols is None:
        symbols = ALL_MARKET_SYMBOLS

    task_id = str(uuid.uuid4())
    logger.info("refresh_daily_ohlcv_started", task_id=task_id, symbols=symbols)

    try:
        return _ingest_historical_ohlcv_impl(
            list(dict.fromkeys(symbols)),
            days=DEFAULT_DAILY_REFRESH_DAYS,
            task_id=task_id,
        )
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


def refresh_household_holdings_prices() -> dict[str, int | str | float]:
    """Warm price_cache for symbols held across non-paper portfolio accounts.

    Runs on a tight cron during US market hours so household reads
    (fetch_price_data via household dashboard / net-worth-trend) hit cache
    instead of waiting on a vendor round-trip. Vendor latency is the only thing
    this task absorbs; the actual cache write happens inside fetch_price_data.
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    lock_key = generate_task_lock_key("refresh_household_holdings_prices", [], 0)

    with task_lock(lock_key, ttl=300) as acquired:
        if not acquired:
            logger.info(
                "refresh_household_holdings_prices_skipped_duplicate",
                task_id=task_id,
            )
            return {
                "task_id": task_id,
                "skipped": True,
                "reason": "duplicate_task_running",
                "symbols_count": 0,
            }

        try:
            from app.portfolio.manager import PortfolioManager
            from app.portfolio.price_fetcher import PriceDataFetcher

            storage = get_storage()
            mgr = PortfolioManager(storage)
            account_ids = {
                str(a.id)
                for a in mgr.get_accounts()
                if getattr(a, "account_type", None) != "paper"
            }
            symbols = sorted({
                str(p.symbol).upper()
                for p in mgr.get_positions()
                if str(getattr(p, "account_id", "")) in account_ids
                and getattr(p, "symbol", None)
            })

            if not symbols:
                logger.info(
                    "refresh_household_holdings_prices_no_symbols",
                    task_id=task_id,
                )
                return {
                    "task_id": task_id,
                    "symbols_count": 0,
                    "duration_ms": int(
                        (dt.datetime.now(dt.UTC) - start_time).total_seconds() * 1000
                    ),
                }

            fetcher = PriceDataFetcher(storage)
            result = fetcher.fetch_price_data(symbols)
            duration_ms = int(
                (dt.datetime.now(dt.UTC) - start_time).total_seconds() * 1000
            )
            errors = sum(1 for p in result.values() if getattr(p, "error", None))
            logger.info(
                "refresh_household_holdings_prices_complete",
                task_id=task_id,
                symbols_count=len(symbols),
                priced_count=len(result) - errors,
                error_count=errors,
                duration_ms=duration_ms,
            )
            return {
                "task_id": task_id,
                "symbols_count": len(symbols),
                "priced_count": len(result) - errors,
                "error_count": errors,
                "duration_ms": duration_ms,
            }
        finally:
            task_cleanup("refresh_household_holdings_prices")


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
    symbols: list[str], days: int = TRADING_DAYS_PER_YEAR
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
