"""Tasks for technical indicator calculations.

This module defines background tasks for calculating and caching technical indicators
like RSI, MACD, SMA, EMA, Bollinger Bands, ATR, and Stochastic indicators.
"""

from __future__ import annotations

import uuid

from app.analytics.indicators import calculate_indicators
from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.indicators.helpers import build_indicator_data, upsert_indicators
from app.tasks.types import TechnicalIndicatorResultDict

logger = get_logger(__name__)


def update_technical_indicators(
    symbols: list[str]
) -> TechnicalIndicatorResultDict:
    """Calculate and cache technical indicators for given symbols.

    This task calculates RSI, MACD, Bollinger Bands, moving averages (SMA/EMA),
    ATR, and Stochastic indicators using the latest 200 days of OHLCV data.
    Results are stored in the technical_indicators table for fast retrieval.

    Args:
        symbols: List of symbols to calculate indicators for

    Returns:
        TechnicalIndicatorResultDict with counts: {"success": int, "failed": int, "symbols_processed": int}

    Example:
        >>> # Run immediately
        >>> update_technical_indicators(["AAPL", "MSFT", "GOOGL"])
        {"success": 3, "failed": 0, "symbols_processed": 3}

        >>> # Schedule as background task
        >>> update_technical_indicators(["AAPL", "MSFT", "GOOGL"])

    Note:
        This task can be scheduled daily at market close + 30 minutes (4:30 PM ET)
        using Celery beat for automated indicator updates.
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
            # Calculate indicators using latest data
            result = calculate_indicators(
                storage=storage,
                symbol=symbol,
                indicators=None,  # Calculate all indicators
                as_of_date=None,  # Use latest available date
            )

            # Extract indicator values from result
            indicators = result["indicators"]
            date = result["date"]

            # Prepare and insert indicator data
            indicator_data = build_indicator_data(symbol, indicators, date)
            upsert_indicators(storage, indicator_data)

            success_count += 1
            logger.info(
                "technical_indicators_calculated",
                symbol=symbol,
                date=date,
                num_indicators=len([v for v in indicators.values() if v is not None]),
            )

        except Exception as e:
            failed_count += 1
            logger.error(
                "technical_indicators_calculation_failed",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Continue with next symbol instead of failing entire task

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


def backfill_technical_indicators(
    symbols: list[str] | None = None, batch_size: int = 50
) -> dict[str, int]:
    """Backfill technical indicators for all historical dates with OHLCV data.

    This task calculates indicators for ALL dates that have OHLCV data but are missing
    indicators. It's designed for one-time backfill or catch-up operations.

    The regular update_technical_indicators task only calculates for the LATEST date.
    Use this task when:
    - Initial setup of indicator data
    - After adding new symbols to watchlist
    - Recovering from data gaps

    Args:
        symbols: List of symbols to backfill. If None, backfills ALL symbols from day_bars.
        batch_size: Number of dates to process per symbol before committing (default: 50)

    Returns:
        Dict with counts: {"symbols_processed": int, "indicators_created": int, "errors": int}

    Example:
        >>> # Backfill all symbols
        >>> backfill_technical_indicators()

        >>> # Backfill specific symbols
        >>> backfill_technical_indicators(["AAPL", "MSFT", "GOOGL"])

    Note:
        This task can take several minutes for large datasets. Run manually or schedule
        during off-hours. Progress is logged for monitoring.
    """
    task_id = str(uuid.uuid4())
    logger.info(
        "backfill_technical_indicators_started",
        task_id=task_id,
        symbols=symbols,
        batch_size=batch_size,
    )

    storage = get_storage()

    # Get all symbols from day_bars if not specified
    if symbols is None:
        query = "SELECT DISTINCT symbol FROM day_bars ORDER BY symbol"
        result_df = storage.query(query, [])
        symbols = [row["symbol"] for row in result_df.to_dicts()]
        logger.info("backfill_auto_discovered_symbols", num_symbols=len(symbols))

    symbols_processed = 0
    indicators_created = 0
    errors = 0

    for symbol in symbols:
        try:
            # Find dates with OHLCV data but NO indicators
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
            missing_dates = [row["date"] for row in missing_dates_df.to_dicts()]

            if not missing_dates:
                logger.info(
                    "backfill_symbol_complete",
                    symbol=symbol,
                    reason="no_missing_dates",
                )
                symbols_processed += 1
                continue

            logger.info(
                "backfill_symbol_started",
                symbol=symbol,
                missing_dates=len(missing_dates),
            )

            # Process dates in batches
            for i in range(0, len(missing_dates), batch_size):
                batch = missing_dates[i : i + batch_size]
                batch_created = 0

                for date in batch:
                    try:
                        # Calculate indicators for this specific date
                        result = calculate_indicators(
                            storage=storage,
                            symbol=symbol,
                            indicators=None,  # Use all default indicators
                            as_of_date=date,  # Calculate for this specific historical date
                        )

                        # Extract and store
                        indicators = result["indicators"]
                        indicator_data = build_indicator_data(symbol, indicators, date)
                        upsert_indicators(storage, indicator_data)

                        batch_created += 1
                        indicators_created += 1

                    except ValueError as e:
                        # Skip dates with insufficient data (e.g., first 200 days for SMA-200)
                        if "Insufficient data" in str(e):
                            logger.debug(
                                "backfill_skip_insufficient_data",
                                symbol=symbol,
                                date=date,
                                error=str(e),
                            )
                        else:
                            logger.error(
                                "backfill_date_failed",
                                symbol=symbol,
                                date=date,
                                error=str(e),
                            )
                            errors += 1
                    except Exception as e:
                        logger.error(
                            "backfill_date_failed",
                            symbol=symbol,
                            date=date,
                            error=str(e),
                            error_type=type(e).__name__,
                        )
                        errors += 1

                # Log batch progress
                logger.info(
                    "backfill_batch_complete",
                    symbol=symbol,
                    batch_num=i // batch_size + 1,
                    batch_size=len(batch),
                    created=batch_created,
                )

            symbols_processed += 1
            logger.info(
                "backfill_symbol_complete",
                symbol=symbol,
                indicators_created=indicators_created,
            )

        except Exception as e:
            logger.error(
                "backfill_symbol_failed",
                symbol=symbol,
                error=str(e),
                error_type=type(e).__name__,
            )
            errors += 1
            # Continue with next symbol

    result = {
        "symbols_processed": symbols_processed,
        "indicators_created": indicators_created,
        "errors": errors,
    }

    logger.info(
        "backfill_technical_indicators_completed",
        task_id=task_id,
        **result,
    )

    return result
