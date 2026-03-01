"""Database and cache operations for Fear & Greed Index.

This module handles reading inputs from and writing results to the database,
as well as invalidating related cache entries.
"""

from __future__ import annotations

import datetime as dt

import redis

from app.logging_config import get_logger
from app.storage.types import DatabaseConnection

logger = get_logger(__name__)


def _get_fear_greed_inputs(
    conn: DatabaseConnection, as_of_date: str | None
) -> tuple[str, float, float, float, float, float, float | None]:
    """Get inputs for target date (or latest if None).

    Returns:
        Tuple of (as_of_date, vix_close, spy_close, spy_sma_200, rsi_14, hy_spread, breadth_pct)
    """
    if as_of_date is None:
        result = conn.execute(
            "SELECT MAX(as_of_date) FROM fear_greed_inputs WHERE vix_close IS NOT NULL"
        )
        row = result.fetchone()
        if not row or row[0] is None:
            raise ValueError("No input data available")
        as_of_date = row[0].isoformat() if isinstance(row[0], dt.date) else str(row[0])

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

    vix_close = float(row[0]) if row[0] is not None else 0.0
    spy_close = float(row[1]) if row[1] is not None else 0.0
    spy_sma_200 = float(row[2]) if row[2] is not None else 0.0
    rsi_14 = float(row[3]) if row[3] is not None else 0.0
    hy_spread = float(row[4]) if row[4] is not None else 0.0
    breadth_pct = float(row[5]) if row[5] is not None else None

    return (as_of_date, vix_close, spy_close, spy_sma_200, rsi_14, hy_spread, breadth_pct)


def _get_label(composite_score: int) -> str:
    """Map composite score to sentiment label."""
    if composite_score >= 75:
        return "Extreme Greed"
    if composite_score >= 55:
        return "Greed"
    if composite_score >= 45:
        return "Neutral"
    if composite_score >= 25:
        return "Fear"
    return "Extreme Fear"


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

    composite_score = int((vix_pct + momentum_pct + rsi_pct + credit_pct + breadth_pct) / 5)
    label = _get_label(composite_score)

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
    previous_score = int(prev_row[0]) if prev_row and prev_row[0] is not None else composite_score
    score_change = composite_score - previous_score

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

    try:
        from app.middleware.cache import invalidate_fear_greed_cache

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
