"""Celery tasks for Fear & Greed Index calculation.

This module defines background tasks for calculating market sentiment metrics
based on VIX, momentum, RSI, credit spreads, and market breadth.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from celery import Task

import redis

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage import get_storage
from app.storage.types import DatabaseConnection
from app.tasks.types import FearGreedCalculationDict

logger = get_logger(__name__)


def _get_fear_greed_inputs(
    conn: DatabaseConnection, as_of_date: str | None
) -> tuple[str, float, float, float, float, float, float | None]:
    """Get inputs for target date (or latest if None).

    Returns:
        Tuple of (as_of_date, vix_close, spy_close, spy_sma_200, rsi_14, hy_spread, breadth_pct)
    """
    # Get latest date if not specified
    if as_of_date is None:
        result = conn.execute(
            "SELECT MAX(as_of_date) FROM fear_greed_inputs WHERE vix_close IS NOT NULL"
        )
        row = result.fetchone()
        if not row or row[0] is None:
            raise ValueError("No input data available")
        as_of_date = row[0].isoformat() if isinstance(row[0], dt.date) else str(row[0])

    # Get inputs for target date
    result = conn.execute(
        """
        SELECT vix_close, spy_close, spy_sma_200, rsi_14, hy_spread, breadth_pct
        FROM fear_greed_inputs
        WHERE as_of_date = %s
        """,
        (as_of_date,),
    )
    row = result.fetchone()
    if not row:
        raise ValueError(f"No inputs for date {as_of_date}")

    # Cast row values to proper types
    vix_close = float(row[0]) if row[0] is not None else 0.0
    spy_close = float(row[1]) if row[1] is not None else 0.0
    spy_sma_200 = float(row[2]) if row[2] is not None else 0.0
    rsi_14 = float(row[3]) if row[3] is not None else 0.0
    hy_spread = float(row[4]) if row[4] is not None else 0.0
    breadth_pct = float(row[5]) if row[5] is not None else None

    return (as_of_date, vix_close, spy_close, spy_sma_200, rsi_14, hy_spread, breadth_pct)


def _calculate_percentile_vix(
    conn: DatabaseConnection, as_of_date: str, vix_close: float, window: int
) -> int:
    """Calculate VIX percentile (inverted: lower VIX = higher score)."""
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
        (as_of_date, window, vix_close),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50


def _calculate_percentile_momentum(
    conn: DatabaseConnection, as_of_date: str, spy_close: float, spy_sma_200: float, window: int
) -> int:
    """Calculate momentum percentile (SPY vs SMA_200)."""
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
        (as_of_date, window, momentum),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50


def _calculate_percentile_rsi(
    conn: DatabaseConnection, as_of_date: str, rsi_14: float, window: int
) -> int:
    """Calculate RSI percentile."""
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
        (as_of_date, window, rsi_14),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50


def _calculate_percentile_credit(
    conn: DatabaseConnection, as_of_date: str, hy_spread: float, window: int
) -> int:
    """Calculate credit spread percentile (inverted: lower spread = higher score)."""
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
        (as_of_date, window, hy_spread),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50


def _calculate_percentile_breadth(
    conn: DatabaseConnection, as_of_date: str, breadth_pct: float | None, window: int
) -> int:
    """Calculate market breadth percentile."""
    if breadth_pct is None:
        return 50  # Default neutral if breadth_pct is None

    result = conn.execute(
        """
        WITH recent_data AS (
            SELECT breadth_pct
            FROM fear_greed_inputs
            WHERE as_of_date <= %s AND breadth_pct IS NOT NULL
            ORDER BY as_of_date DESC
            LIMIT %s
        )
        SELECT
            COUNT(*) FILTER (WHERE breadth_pct <= %s) * 100.0 / COUNT(*) as breadth_percentile
        FROM recent_data
        """,
        (as_of_date, window, breadth_pct),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50


def _store_components_and_score(
    conn: DatabaseConnection,
    as_of_date: str,
    vix_pct: int,
    momentum_pct: int,
    rsi_pct: int,
    credit_pct: int,
    breadth_pct: int,
    window_days: int,
) -> tuple[int, str, int]:
    """Store components, calculate composite score, get previous score.

    Returns:
        (composite_score, label, score_change)
    """
    # Store components
    conn.execute(
        """
        INSERT INTO fear_greed_components
            (as_of_date, vix_pct, momentum_pct, rsi_pct, credit_pct, breadth_pct, window_days)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (as_of_date) DO UPDATE SET
            vix_pct = EXCLUDED.vix_pct,
            momentum_pct = EXCLUDED.momentum_pct,
            rsi_pct = EXCLUDED.rsi_pct,
            credit_pct = EXCLUDED.credit_pct,
            breadth_pct = EXCLUDED.breadth_pct,
            window_days = EXCLUDED.window_days
        """,
        (as_of_date, vix_pct, momentum_pct, rsi_pct, credit_pct, breadth_pct, window_days),
    )

    # Calculate composite score (equal-weighted average of 5 components)
    composite_score = int((vix_pct + momentum_pct + rsi_pct + credit_pct + breadth_pct) / 5)

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
    if prev_row and prev_row[0] is not None:
        previous_score = int(prev_row[0])
    else:
        previous_score = composite_score
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
        (as_of_date, composite_score, label, previous_score, score_change, 5),
    )

    return (composite_score, label, score_change)


def _invalidate_redis_cache() -> None:
    """Invalidate Redis cache for fear_greed:latest key."""
    try:
        redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
        deleted = redis_client.delete("fear_greed:latest")
        logger.info(
            "fear_greed_cache_invalidated",
            cache_key="fear_greed:latest",
            deleted=deleted,
        )
    except Exception as cache_error:
        logger.warning(
            "fear_greed_cache_invalidation_failed",
            error=str(cache_error),
        )

    # Also invalidate FastAPI response cache for market endpoints
    try:
        from app.middleware.cache import invalidate_fear_greed_cache  # noqa: PLC0415

        invalidated = invalidate_fear_greed_cache()
        logger.info(
            "fear_greed_response_cache_invalidated",
            entries_cleared=invalidated,
        )
    except Exception as cache_error:
        logger.warning(
            "fear_greed_response_cache_invalidation_failed",
            error=str(cache_error),
        )


@celery_app.task(
    bind=True,
    name="calculate_fear_greed",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)  # type: ignore[misc]
def calculate_fear_greed(self: Task, as_of_date: str | None = None) -> FearGreedCalculationDict:
    """Calculate Fear & Greed Index from inputs table.

    This task calculates percentile rankings for each component (VIX, Momentum,
    RSI, Credit Spread) and computes a composite score. The calculation uses
    a 252-day rolling window to determine percentile rankings.

    Args:
        as_of_date: Date to calculate for (YYYY-MM-DD). If None, uses latest available.

    Returns:
        FearGreedCalculationDict with calculation results and metadata

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
            # Get inputs
            as_of_date, vix_close, spy_close, spy_sma_200, rsi_14, hy_spread, breadth_pct = (
                _get_fear_greed_inputs(conn, as_of_date)
            )

            # Calculate percentiles
            window_days = 252
            vix_pct = _calculate_percentile_vix(conn, as_of_date, vix_close, window_days)
            momentum_pct = _calculate_percentile_momentum(
                conn, as_of_date, spy_close, spy_sma_200, window_days
            )
            rsi_pct = _calculate_percentile_rsi(conn, as_of_date, rsi_14, window_days)
            credit_pct = _calculate_percentile_credit(conn, as_of_date, hy_spread, window_days)
            breadth_percentile = _calculate_percentile_breadth(
                conn, as_of_date, breadth_pct, window_days
            )

            # Store components and calculate score
            composite_score, label, score_change = _store_components_and_score(
                conn,
                as_of_date,
                vix_pct,
                momentum_pct,
                rsi_pct,
                credit_pct,
                breadth_percentile,
                window_days,
            )

            conn.commit()

            # Invalidate cache
            _invalidate_redis_cache()

            result_data: FearGreedCalculationDict = {
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
                    "breadth_pct": breadth_percentile,
                },
            }

            logger.info(
                "calculate_fear_greed_completed",
                task_id=task_id,
                **result_data,
            )

            return result_data

    except ValueError as e:
        logger.warning(
            "calculate_fear_greed_input_error",
            task_id=task_id,
            error=str(e),
        )
        error_result_value: FearGreedCalculationDict = {
            "error": str(e),
            "success": False,
        }
        return error_result_value
    except Exception as e:
        logger.error(
            "calculate_fear_greed_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        error_result_exception: FearGreedCalculationDict = {
            "error": str(e),
            "success": False,
        }
        return error_result_exception
