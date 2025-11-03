"""Celery tasks for technical indicator calculations.

This module defines background tasks for calculating and caching technical indicators.
"""

from __future__ import annotations

import datetime as dt

from app.analytics.indicators import calculate_indicators
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)


@celery_app.task(name="update_technical_indicators", bind=True)  # type: ignore[misc]
def update_technical_indicators(  # type: ignore[no-untyped-def]
    self, tickers: list[str]
) -> dict[str, int]:
    """Calculate and cache technical indicators for given tickers.

    This task calculates RSI, MACD, Bollinger Bands, moving averages (SMA/EMA),
    ATR, and Stochastic indicators using the latest 200 days of OHLCV data.
    Results are stored in the technical_indicators table for fast retrieval.

    Args:
        tickers: List of ticker symbols to calculate indicators for

    Returns:
        Dict with counts: {"success": int, "failed": int, "tickers_processed": int}

    Example:
        >>> # Run immediately
        >>> update_technical_indicators(["AAPL", "MSFT", "GOOGL"])
        {"success": 3, "failed": 0, "tickers_processed": 3}

        >>> # Schedule as background task
        >>> update_technical_indicators.delay(["AAPL", "MSFT", "GOOGL"])

    Note:
        This task can be scheduled daily at market close + 30 minutes (4:30 PM ET)
        using Celery beat for automated indicator updates.
    """
    task_id = self.request.id
    logger.info(
        "update_technical_indicators_started",
        task_id=task_id,
        num_tickers=len(tickers),
        tickers=tickers,
    )

    storage = get_storage()
    success_count = 0
    failed_count = 0

    for ticker in tickers:
        try:
            # Calculate indicators using latest data
            result = calculate_indicators(
                storage=storage,
                ticker=ticker,
                indicators=None,  # Calculate all indicators
                as_of_date=None,  # Use latest available date
            )

            # Extract indicator values from result
            indicators = result["indicators"]
            date = result["date"]

            # Prepare data for insertion
            indicator_data = {
                "ticker": ticker,
                "date": date,
                "rsi_14": indicators.get("rsi_14"),
                "macd": indicators.get("macd_12_26_9", {}).get("macd"),
                "macd_signal": indicators.get("macd_12_26_9", {}).get("signal"),
                "macd_histogram": indicators.get("macd_12_26_9", {}).get("histogram"),
                "bb_upper": indicators.get("bbands_20_2", {}).get("upper"),
                "bb_middle": indicators.get("bbands_20_2", {}).get("middle"),
                "bb_lower": indicators.get("bbands_20_2", {}).get("lower"),
                "sma_5": indicators.get("sma_5"),  # Added missing field
                "sma_20": indicators.get("sma_20"),
                "sma_50": indicators.get("sma_50"),
                "sma_200": indicators.get("sma_200"),
                "ema_20": indicators.get("ema_20"),
                "ema_50": indicators.get("ema_50"),
                "ema_200": indicators.get("ema_200"),
                "atr_14": indicators.get("atr_14"),
                "stoch_k": indicators.get("stoch_14_3_3", {}).get("k"),
                "stoch_d": indicators.get("stoch_14_3_3", {}).get("d"),
                "calculated_at": dt.datetime.now(dt.UTC),
            }

            # Insert/update in technical_indicators table
            # Using UPSERT pattern (PostgreSQL ON CONFLICT)
            with storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO technical_indicators (
                        ticker, date, rsi_14, macd, macd_signal, macd_histogram,
                        bb_upper, bb_middle, bb_lower,
                        sma_5, sma_20, sma_50, sma_200,
                        ema_20, ema_50, ema_200,
                        atr_14, stoch_k, stoch_d,
                        calculated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?
                    )
                    ON CONFLICT (ticker, date) DO UPDATE SET
                        rsi_14 = EXCLUDED.rsi_14,
                        macd = EXCLUDED.macd,
                        macd_signal = EXCLUDED.macd_signal,
                        macd_histogram = EXCLUDED.macd_histogram,
                        bb_upper = EXCLUDED.bb_upper,
                        bb_middle = EXCLUDED.bb_middle,
                        bb_lower = EXCLUDED.bb_lower,
                        sma_5 = EXCLUDED.sma_5,
                        sma_20 = EXCLUDED.sma_20,
                        sma_50 = EXCLUDED.sma_50,
                        sma_200 = EXCLUDED.sma_200,
                        ema_20 = EXCLUDED.ema_20,
                        ema_50 = EXCLUDED.ema_50,
                        ema_200 = EXCLUDED.ema_200,
                        atr_14 = EXCLUDED.atr_14,
                        stoch_k = EXCLUDED.stoch_k,
                        stoch_d = EXCLUDED.stoch_d,
                        calculated_at = EXCLUDED.calculated_at
                    """,
                    [
                        indicator_data["ticker"],
                        indicator_data["date"],
                        indicator_data["rsi_14"],
                        indicator_data["macd"],
                        indicator_data["macd_signal"],
                        indicator_data["macd_histogram"],
                        indicator_data["bb_upper"],
                        indicator_data["bb_middle"],
                        indicator_data["bb_lower"],
                        indicator_data["sma_5"],
                        indicator_data["sma_20"],
                        indicator_data["sma_50"],
                        indicator_data["sma_200"],
                        indicator_data["ema_20"],
                        indicator_data["ema_50"],
                        indicator_data["ema_200"],
                        indicator_data["atr_14"],
                        indicator_data["stoch_k"],
                        indicator_data["stoch_d"],
                        indicator_data["calculated_at"],
                    ],
                )
                conn.commit()  # Commit the upsert

            success_count += 1
            logger.info(
                "technical_indicators_calculated",
                ticker=ticker,
                date=date,
                num_indicators=len([v for v in indicators.values() if v is not None]),
            )

        except Exception as e:
            failed_count += 1
            logger.error(
                "technical_indicators_calculation_failed",
                ticker=ticker,
                error=str(e),
                error_type=type(e).__name__,
            )
            # Continue with next ticker instead of failing entire task

    result = {
        "success": success_count,
        "failed": failed_count,
        "tickers_processed": len(tickers),
    }

    logger.info(
        "update_technical_indicators_completed",
        task_id=task_id,
        **result,
    )

    return result
