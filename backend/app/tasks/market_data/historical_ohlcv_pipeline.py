"""Historical OHLCV pipeline tasks.

Maintains 1260 trading days (5 years) of historical market data for backtesting and analysis.
Runs daily to ensure data is current and complete.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.constants import ALL_MARKET_SYMBOLS
from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.ingestion import ingest_historical_ohlcv

logger = get_logger(__name__)

# Target: 1260 trading days (approximately 5 years)
TARGET_DAYS = 1260


def _check_symbol_data(symbol: str) -> tuple[bool, int]:
    """Check if symbol has sufficient historical data AND is current.

    Returns:
        Tuple of (needs_backfill, days_available)
    """
    storage = get_storage()
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT COUNT(*) as days, MAX(date) as latest_date FROM day_bars WHERE symbol = %s",
            [symbol],
        ).fetchone()

    days_available_raw = result[0] if result else 0
    latest_date_raw = result[1] if result and result[1] else None

    days_available: int = days_available_raw if isinstance(days_available_raw, int) else 0
    latest_date: dt.date | None = latest_date_raw if isinstance(latest_date_raw, dt.date) else None

    is_stale = latest_date is None or latest_date < dt.date.today()
    needs_backfill: bool = bool(days_available < TARGET_DAYS or is_stale)
    return needs_backfill, days_available


def _get_all_symbols() -> list[str]:
    """Get all symbols that need historical data: market symbols + watchlist symbols."""
    storage = get_storage()
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT DISTINCT symbol FROM watchlist_items WHERE symbol IS NOT NULL"
        ).fetchall()

    watchlist_symbols = [str(row[0]) for row in result] if result else []
    all_symbols = list(set(ALL_MARKET_SYMBOLS + watchlist_symbols))

    logger.info(
        "historical_data_symbols_resolved",
        market_symbols=len(ALL_MARKET_SYMBOLS),
        watchlist_symbols=len(watchlist_symbols),
        total_unique=len(all_symbols),
    )
    return all_symbols


def _categorize_symbols(all_symbols: list[str]) -> tuple[list[str], int]:
    """Categorize symbols into those needing backfill vs those that are current.

    Returns:
        Tuple of (symbols_to_backfill, symbols_ok_count)
    """
    symbols_to_backfill = []
    symbols_ok = 0
    for symbol in all_symbols:
        needs_backfill, days_available = _check_symbol_data(symbol)
        if needs_backfill:
            symbols_to_backfill.append(symbol)
            logger.info("market_data_maintenance_needs_backfill", symbol=symbol,
                        days_available=days_available, target_days=TARGET_DAYS)
        else:
            symbols_ok += 1
            logger.info("market_data_maintenance_ok", symbol=symbol, days_available=days_available)
    return symbols_to_backfill, symbols_ok


def _backfill_symbols(symbols_to_backfill: list[str]) -> int:
    """Run backfill for symbols that need it and return count backfilled."""
    if not symbols_to_backfill:
        return 0
    logger.info("market_data_maintenance_backfilling",
                symbols_count=len(symbols_to_backfill), symbols=symbols_to_backfill)
    backfill_result = ingest_historical_ohlcv(symbols=symbols_to_backfill, days=TARGET_DAYS)
    logger.info("market_data_maintenance_backfill_complete", backfill_result=backfill_result)
    return len(symbols_to_backfill)


def maintain_historical_market_data() -> dict[str, int | str | float]:
    """Maintain historical market data for all required indicators and sectors.

    This task is idempotent and self-healing:
    - Checks each symbol for sufficient data (1260 trading days / 5 years)
    - Backfills if missing or incomplete (uses ingest_historical_ohlcv)
    - Daily refresh handled by separate refresh-daily-ohlcv task
    - Safe to run repeatedly (scheduled daily at 04:00 UTC)

    Returns:
        Dict with task_id, symbols_checked, symbols_backfilled, symbols_ok, duration_seconds.
    """
    task_id = str(uuid.uuid4())
    start_time = dt.datetime.now(dt.UTC)
    all_symbols = _get_all_symbols()
    logger.info("market_data_maintenance_started", task_id=task_id, symbols_count=len(all_symbols))

    try:
        symbols_to_backfill, symbols_ok = _categorize_symbols(all_symbols)
        symbols_backfilled = _backfill_symbols(symbols_to_backfill)
        duration = (dt.datetime.now(dt.UTC) - start_time).total_seconds()
        result: dict[str, int | str | float] = {
            "task_id": task_id,
            "symbols_checked": len(all_symbols),
            "symbols_backfilled": symbols_backfilled,
            "symbols_ok": symbols_ok,
            "duration_seconds": duration,
        }
        logger.info("market_data_maintenance_completed", **result)
        return result
    except Exception as e:
        logger.error("market_data_maintenance_failed", task_id=task_id,
                     error=str(e), error_type=type(e).__name__, exc_info=True)
        raise
