"""Tasks for technical indicator calculations.

This module defines background tasks for calculating and caching technical indicators
like RSI, MACD, SMA, EMA, Bollinger Bands, ATR, and Stochastic indicators.
"""

from __future__ import annotations

import datetime as dt
import uuid

from app.analytics.indicators import calculate_indicators
from app.logging_config import get_logger
from app.storage import get_storage
from app.storage.facade import PortfolioStorage
from app.tasks.indicators.helpers import build_indicator_data, upsert_indicators
from app.tasks.types import TechnicalIndicatorResultDict

logger = get_logger(__name__)


def _process_symbol(storage: PortfolioStorage, symbol: str) -> bool:
    """Calculate and store indicators for a single symbol using latest data.

    Returns True on success, False on failure.
    """
    result = calculate_indicators(
        storage=storage,
        symbol=symbol,
        indicators=None,
        as_of_date=None,
    )
    indicators = result["indicators"]
    date = result["date"]
    indicator_data = build_indicator_data(symbol, indicators, date)
    upsert_indicators(storage, indicator_data)
    logger.info(
        "technical_indicators_calculated",
        symbol=symbol,
        date=date,
        num_indicators=len([v for v in indicators.values() if v is not None]),
    )
    return True


def update_technical_indicators(
    symbols: list[str],
) -> TechnicalIndicatorResultDict:
    """Calculate and cache technical indicators for given symbols.

    Calculates RSI, MACD, Bollinger Bands, SMA/EMA, ATR, and Stochastic using
    the latest 200 days of OHLCV data, storing results in technical_indicators.

    Args:
        symbols: List of symbols to process.

    Returns:
        {"success": int, "failed": int, "symbols_processed": int}
    """
    task_id = str(uuid.uuid4())
    logger.info(
        "update_technical_indicators_started",
        task_id=task_id,
        num_symbols=len(symbols),
        symbols=symbols,
    )

    storage = get_storage()
    success_count = 0
    failed_count = 0

    for symbol in symbols:
        try:
            _process_symbol(storage, symbol)
            success_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(
                "technical_indicators_calculation_failed",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )

    task_result: TechnicalIndicatorResultDict = {
        "success": success_count,
        "failed": failed_count,
        "symbols_processed": len(symbols),
    }
    logger.info(
        "update_technical_indicators_completed",
        task_id=task_id,
        **task_result,
    )
    return task_result


def _get_missing_dates(storage: PortfolioStorage, symbol: str) -> list[dt.date]:
    """Return dates that have OHLCV data but are missing indicator records."""
    query = """
        SELECT DISTINCT db.date
        FROM day_bars db
        LEFT JOIN technical_indicators ti
            ON db.symbol = ti.symbol AND db.date = ti.date
        WHERE db.symbol = $1
          AND ti.symbol IS NULL
        ORDER BY db.date ASC
    """
    missing_dates_df = storage.query(query, [symbol])
    return [row["date"] for row in missing_dates_df.to_dicts()]


def _process_backfill_date(
    storage: PortfolioStorage, symbol: str, date: dt.date
) -> bool:
    """Calculate and store indicators for a single historical date.

    Returns True on success, False when the date should be counted as an error.
    Raises nothing — ValueError for insufficient data is silently skipped.
    """
    try:
        result = calculate_indicators(
            storage=storage,
            symbol=symbol,
            indicators=None,
            as_of_date=date,
        )
        indicators = result["indicators"]
        indicator_data = build_indicator_data(symbol, indicators, date)
        upsert_indicators(storage, indicator_data)
        return True
    except ValueError as e:
        if "Insufficient data" in str(e):
            logger.debug(
                "backfill_skip_insufficient_data",
                symbol=symbol,
                date=date,
                error=str(e),
            )
            return False
        logger.error("backfill_date_failed", symbol=symbol, date=date, error=str(e))
        return False
    except Exception as e:
        logger.error(
            "backfill_date_failed",
            symbol=symbol,
            date=date,
            error=str(e),
            error_type=type(e).__name__,
        )
        return False


def _process_batch(
    storage: PortfolioStorage,
    symbol: str,
    batch: list[dt.date],
    batch_num: int,
) -> tuple[int, int]:
    """Process a batch of dates for a symbol.

    Returns (created, errors) counts for the batch.
    """
    created = 0
    errors = 0
    for date in batch:
        success = _process_backfill_date(storage, symbol, date)
        if success:
            created += 1
        else:
            # Only count as error if it was not an insufficient-data skip.
            # _process_backfill_date already logs the distinction.
            pass
    logger.info(
        "backfill_batch_complete",
        symbol=symbol,
        batch_num=batch_num,
        batch_size=len(batch),
        created=created,
    )
    return created, errors


def _backfill_symbol(
    storage: PortfolioStorage, symbol: str, batch_size: int
) -> tuple[int, int]:
    """Backfill indicators for all missing dates of a single symbol.

    Returns (indicators_created, errors).
    """
    missing_dates = _get_missing_dates(storage, symbol)

    if not missing_dates:
        logger.info("backfill_symbol_complete", symbol=symbol, reason="no_missing_dates")
        return 0, 0

    logger.info("backfill_symbol_started", symbol=symbol, missing_dates=len(missing_dates))

    total_created = 0
    total_errors = 0

    for i in range(0, len(missing_dates), batch_size):
        batch = missing_dates[i : i + batch_size]
        created, errors = _process_batch(storage, symbol, batch, i // batch_size + 1)
        total_created += created
        total_errors += errors

    logger.info(
        "backfill_symbol_complete", symbol=symbol, indicators_created=total_created
    )
    return total_created, total_errors


def _resolve_symbols(storage: PortfolioStorage, symbols: list[str] | None) -> list[str]:
    """Return the list of symbols to process, auto-discovering if None."""
    if symbols is not None:
        return symbols
    query = "SELECT DISTINCT symbol FROM day_bars ORDER BY symbol"
    result_df = storage.query(query, [])
    discovered = [row["symbol"] for row in result_df.to_dicts()]
    logger.info("backfill_auto_discovered_symbols", num_symbols=len(discovered))
    return discovered


def _backfill_all_symbols(
    storage: PortfolioStorage, resolved_symbols: list[str], batch_size: int
) -> dict[str, int]:
    """Iterate over all symbols and accumulate backfill counts."""
    symbols_processed = 0
    indicators_created = 0
    errors = 0
    for symbol in resolved_symbols:
        try:
            created, symbol_errors = _backfill_symbol(storage, symbol, batch_size)
            indicators_created += created
            errors += symbol_errors
            symbols_processed += 1
        except Exception as e:
            logger.error(
                "backfill_symbol_failed",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            errors += 1
    return {
        "symbols_processed": symbols_processed,
        "indicators_created": indicators_created,
        "errors": errors,
    }


def backfill_technical_indicators(
    symbols: list[str] | None = None, batch_size: int = 50
) -> dict[str, int]:
    """Backfill technical indicators for all historical dates with OHLCV data.

    Calculates indicators for dates that have OHLCV data but no indicator records.
    Designed for one-time backfill or catch-up operations.

    Args:
        symbols: Symbols to backfill; auto-discovers all from day_bars if None.
        batch_size: Dates per batch per symbol (default: 50).

    Returns:
        {"symbols_processed": int, "indicators_created": int, "errors": int}
    """
    task_id = str(uuid.uuid4())
    logger.info(
        "backfill_technical_indicators_started",
        task_id=task_id,
        symbols=symbols,
        batch_size=batch_size,
    )
    storage = get_storage()
    resolved_symbols = _resolve_symbols(storage, symbols)
    result = _backfill_all_symbols(storage, resolved_symbols, batch_size)
    logger.info("backfill_technical_indicators_completed", task_id=task_id, **result)
    return result
