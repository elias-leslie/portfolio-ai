"""Celery tasks for technical indicator calculations.

This module defines background tasks for calculating and caching technical indicators
and market sentiment metrics like Fear & Greed Index.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from app.analytics.indicators import calculate_indicators
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage import get_storage
from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


def _build_indicator_data(ticker: str, indicators: dict[str, Any], date: dt.date) -> dict[str, Any]:
    """Build indicator data dictionary for database insertion.

    Args:
        ticker: Stock ticker symbol
        indicators: Calculated indicators dictionary
        date: Date of the indicator values

    Returns:
        Dictionary with all indicator fields ready for database insertion
    """
    return {
        "ticker": ticker,
        "date": date,
        "rsi_14": indicators.get("rsi_14"),
        "macd": indicators.get("macd_12_26_9", {}).get("macd"),
        "macd_signal": indicators.get("macd_12_26_9", {}).get("signal"),
        "macd_histogram": indicators.get("macd_12_26_9", {}).get("histogram"),
        "bb_upper": indicators.get("bbands_20_2", {}).get("upper"),
        "bb_middle": indicators.get("bbands_20_2", {}).get("middle"),
        "bb_lower": indicators.get("bbands_20_2", {}).get("lower"),
        "sma_5": indicators.get("sma_5"),
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


def _upsert_indicators(storage: PortfolioStorage, indicator_data: dict[str, Any]) -> None:
    """Insert or update technical indicators in database.

    Uses PostgreSQL UPSERT (ON CONFLICT) to update existing records
    or insert new ones based on (ticker, date) unique constraint.

    Args:
        storage: Storage instance with connection context manager
        indicator_data: Dictionary containing all indicator fields
    """
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
        conn.commit()


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

            # Prepare and insert indicator data
            indicator_data = _build_indicator_data(ticker, indicators, date)
            _upsert_indicators(storage, indicator_data)

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


@celery_app.task(name="calculate_fear_greed", bind=True)  # type: ignore[misc]
def calculate_fear_greed(self, as_of_date: str | None = None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Calculate Fear & Greed Index from inputs table.

    This task calculates percentile rankings for each component (VIX, Momentum,
    RSI, Credit Spread) and computes a composite score. The calculation uses
    a 252-day rolling window to determine percentile rankings.

    Args:
        as_of_date: Date to calculate for (YYYY-MM-DD). If None, uses latest available.

    Returns:
        Dict with calculation results and metadata

    Example:
        >>> # Calculate for latest date
        >>> calculate_fear_greed()
        {"score": 42, "label": "Fear", "date": "2025-11-11"}

        >>> # Schedule as background task
        >>> calculate_fear_greed.delay()

    Note:
        This task can be scheduled daily after market close to update the index.
        It requires fear_greed_inputs table to be populated first.
    """
    task_id = self.request.id
    logger.info("calculate_fear_greed_started", task_id=task_id, as_of_date=as_of_date)

    storage = get_storage()

    try:
        with storage.connection() as conn:
            # Get latest date if not specified
            if as_of_date is None:
                result = conn.execute(
                    "SELECT MAX(as_of_date) FROM fear_greed_inputs WHERE vix_close IS NOT NULL"
                )
                row = result.fetchone()
                if not row or row[0] is None:
                    logger.warning("no_fear_greed_inputs_available")
                    return {"error": "No input data available", "success": False}
                as_of_date = row[0].isoformat()

            # Get inputs for target date
            result = conn.execute(
                """
                SELECT vix_close, spy_close, spy_sma_200, rsi_14, hy_spread
                FROM fear_greed_inputs
                WHERE as_of_date = %s
                """,
                (as_of_date,),
            )
            row = result.fetchone()

            if not row:
                logger.warning("no_inputs_for_date", date=as_of_date)
                return {"error": f"No inputs for date {as_of_date}", "success": False}

            vix_close, spy_close, spy_sma_200, rsi_14, hy_spread = row

            # Calculate 252-day percentiles for each component
            window_days = 252

            # VIX Percentile (inverted: lower VIX = higher score)
            result = conn.execute(
                """
                WITH recent_data AS (
                    SELECT vix_close
                    FROM fear_greed_inputs
                    WHERE as_of_date <= %s AND vix_close IS NOT NULL
                    ORDER BY as_of_date DESC
                    LIMIT %s
                )
                SELECT
                    COUNT(*) FILTER (WHERE vix_close >= %s) * 100.0 / COUNT(*) as vix_pct
                FROM recent_data
                """,
                (as_of_date, window_days, vix_close),
            )
            vix_pct = int(result.fetchone()[0] or 50)

            # Momentum Percentile (SPY vs SMA_200)
            momentum = ((spy_close / spy_sma_200) - 1) * 100 if spy_sma_200 else 0
            result = conn.execute(
                """
                WITH recent_data AS (
                    SELECT ((spy_close / spy_sma_200) - 1) * 100 as momentum
                    FROM fear_greed_inputs
                    WHERE as_of_date <= %s AND spy_close IS NOT NULL AND spy_sma_200 IS NOT NULL
                    ORDER BY as_of_date DESC
                    LIMIT %s
                )
                SELECT
                    COUNT(*) FILTER (WHERE momentum <= %s) * 100.0 / COUNT(*) as momentum_pct
                FROM recent_data
                """,
                (as_of_date, window_days, momentum),
            )
            momentum_pct = int(result.fetchone()[0] or 50)

            # RSI Percentile
            result = conn.execute(
                """
                WITH recent_data AS (
                    SELECT rsi_14
                    FROM fear_greed_inputs
                    WHERE as_of_date <= %s AND rsi_14 IS NOT NULL
                    ORDER BY as_of_date DESC
                    LIMIT %s
                )
                SELECT
                    COUNT(*) FILTER (WHERE rsi_14 <= %s) * 100.0 / COUNT(*) as rsi_pct
                FROM recent_data
                """,
                (as_of_date, window_days, rsi_14),
            )
            rsi_pct = int(result.fetchone()[0] or 50)

            # Credit Spread Percentile (inverted: lower spread = higher score)
            result = conn.execute(
                """
                WITH recent_data AS (
                    SELECT hy_spread
                    FROM fear_greed_inputs
                    WHERE as_of_date <= %s AND hy_spread IS NOT NULL
                    ORDER BY as_of_date DESC
                    LIMIT %s
                )
                SELECT
                    COUNT(*) FILTER (WHERE hy_spread >= %s) * 100.0 / COUNT(*) as credit_pct
                FROM recent_data
                """,
                (as_of_date, window_days, hy_spread),
            )
            credit_pct = int(result.fetchone()[0] or 50)

            # Store components
            conn.execute(
                """
                INSERT INTO fear_greed_components
                    (as_of_date, vix_pct, momentum_pct, rsi_pct, credit_pct, window_days)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (as_of_date) DO UPDATE SET
                    vix_pct = EXCLUDED.vix_pct,
                    momentum_pct = EXCLUDED.momentum_pct,
                    rsi_pct = EXCLUDED.rsi_pct,
                    credit_pct = EXCLUDED.credit_pct,
                    window_days = EXCLUDED.window_days
                """,
                (as_of_date, vix_pct, momentum_pct, rsi_pct, credit_pct, window_days),
            )

            # Calculate composite score (equal-weighted average)
            composite_score = int((vix_pct + momentum_pct + rsi_pct + credit_pct) / 4)

            # Map to label
            if composite_score >= 75:
                label = "Extreme Greed"
            elif composite_score >= 55:
                label = "Greed"
            elif composite_score >= 45:
                label = "Neutral"
            elif composite_score >= 25:
                label = "Fear"
            else:
                label = "Extreme Fear"

            # Get previous score for change calculation
            result = conn.execute(
                """
                SELECT score
                FROM fear_greed_daily
                WHERE as_of_date < %s
                ORDER BY as_of_date DESC
                LIMIT 1
                """,
                (as_of_date,),
            )
            prev_row = result.fetchone()
            previous_score = prev_row[0] if prev_row else composite_score
            score_change = composite_score - previous_score

            # Store final score
            conn.execute(
                """
                INSERT INTO fear_greed_daily
                    (as_of_date, score, label, previous_score, score_change, signal_count)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (as_of_date) DO UPDATE SET
                    score = EXCLUDED.score,
                    label = EXCLUDED.label,
                    previous_score = EXCLUDED.previous_score,
                    score_change = EXCLUDED.score_change,
                    signal_count = EXCLUDED.signal_count
                """,
                (as_of_date, composite_score, label, previous_score, score_change, 4),
            )

            conn.commit()

            result_data = {
                "success": True,
                "date": as_of_date,
                "score": composite_score,
                "label": label,
                "score_change": score_change,
                "components": {
                    "vix_pct": vix_pct,
                    "momentum_pct": momentum_pct,
                    "rsi_pct": rsi_pct,
                    "credit_pct": credit_pct,
                },
            }

            logger.info(
                "calculate_fear_greed_completed",
                task_id=task_id,
                **result_data,
            )

            return result_data

    except Exception as e:
        logger.error(
            "calculate_fear_greed_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {"error": str(e), "success": False}
