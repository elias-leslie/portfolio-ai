"""Tasks for Fear & Greed Index calculation.

This module defines background tasks for calculating market sentiment metrics
based on VIX, momentum, RSI, credit spreads, and market breadth.

Implementation is split across sub-modules:
- fear_greed_percentiles: per-component percentile queries
- fear_greed_storage: DB reads/writes and cache invalidation

All private helpers are re-exported here so existing callers (e.g.
backfill_fear_greed.py) can continue importing from this path.
"""

from __future__ import annotations

import uuid

from app.logging_config import get_logger
from app.storage import get_storage
from app.storage.types import DatabaseConnection
from app.tasks.indicators.fear_greed_percentiles import (
    _calculate_percentile_breadth,
    _calculate_percentile_credit,
    _calculate_percentile_momentum,
    _calculate_percentile_rsi,
    _calculate_percentile_vix,
)
from app.tasks.indicators.fear_greed_storage import (
    _get_fear_greed_inputs,
    _invalidate_redis_cache,
    _store_components_and_score,
)
from app.tasks.types import FearGreedCalculationDict

# Re-export private helpers so existing importers keep working
__all__ = [
    "_calculate_percentile_breadth",
    "_calculate_percentile_credit",
    "_calculate_percentile_momentum",
    "_calculate_percentile_rsi",
    "_calculate_percentile_vix",
    "_get_fear_greed_inputs",
    "_invalidate_redis_cache",
    "_store_components_and_score",
    "calculate_fear_greed",
]

from app.constants import TRADING_DAYS_PER_YEAR

logger = get_logger(__name__)

_WINDOW_DAYS = TRADING_DAYS_PER_YEAR


def _compute_percentiles(
    conn: DatabaseConnection,
    as_of_date: str,
    vix_close: float,
    spy_close: float,
    spy_sma_200: float,
    rsi_14: float,
    hy_spread: float,
    breadth_pct: float | None,
    window_days: int,
) -> tuple[float, float, float, float, float]:
    """Compute all five component percentiles and return them as a tuple."""
    vix_pct = _calculate_percentile_vix(conn, as_of_date, vix_close, window_days)
    momentum_pct = _calculate_percentile_momentum(
        conn, as_of_date, spy_close, spy_sma_200, window_days
    )
    rsi_pct = _calculate_percentile_rsi(conn, as_of_date, rsi_14, window_days)
    credit_pct = _calculate_percentile_credit(conn, as_of_date, hy_spread, window_days)
    breadth_percentile = _calculate_percentile_breadth(
        conn, as_of_date, breadth_pct, window_days
    )
    return vix_pct, momentum_pct, rsi_pct, credit_pct, breadth_percentile


def _build_success_result(
    as_of_date: str,
    composite_score: int,
    label: str,
    score_change: int,
    vix_pct: float,
    momentum_pct: float,
    rsi_pct: float,
    credit_pct: float,
    breadth_percentile: float,
) -> FearGreedCalculationDict:
    """Assemble a successful FearGreedCalculationDict."""
    result: FearGreedCalculationDict = {
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
    return result


def _run_calculation(
    conn: DatabaseConnection,
    as_of_date: str | None,
) -> FearGreedCalculationDict:
    """Execute the full fear & greed calculation within an open connection."""
    as_of_date, vix_close, spy_close, spy_sma_200, rsi_14, hy_spread, breadth_pct = (
        _get_fear_greed_inputs(conn, as_of_date)
    )

    vix_pct, momentum_pct, rsi_pct, credit_pct, breadth_percentile = _compute_percentiles(
        conn,
        as_of_date,
        vix_close,
        spy_close,
        spy_sma_200,
        rsi_14,
        hy_spread,
        breadth_pct,
        _WINDOW_DAYS,
    )

    composite_score, label, score_change = _store_components_and_score(
        conn,
        as_of_date,
        vix_pct,
        momentum_pct,
        rsi_pct,
        credit_pct,
        breadth_percentile,
        _WINDOW_DAYS,
    )

    conn.commit()
    _invalidate_redis_cache()

    return _build_success_result(
        as_of_date,
        composite_score,
        label,
        score_change,
        vix_pct,
        momentum_pct,
        rsi_pct,
        credit_pct,
        breadth_percentile,
    )


def calculate_fear_greed(
    as_of_date: str | None = None,
) -> FearGreedCalculationDict:
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

    Note:
        This task can be scheduled daily after market close to update the index.
        It requires fear_greed_inputs table to be populated first.
    """
    task_id = str(uuid.uuid4())
    logger.info("calculate_fear_greed_started", task_id=task_id, as_of_date=as_of_date)

    storage = get_storage()

    try:
        with storage.connection() as conn:
            result_data = _run_calculation(conn, as_of_date)
        logger.info("calculate_fear_greed_completed", task_id=task_id, **result_data)
        return result_data

    except ValueError as e:
        logger.warning("calculate_fear_greed_input_error", task_id=task_id, error=str(e))
        error_result_value: FearGreedCalculationDict = {"error": str(e), "success": False}
        return error_result_value
    except Exception as e:
        logger.error(
            "calculate_fear_greed_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )
        error_result_exception: FearGreedCalculationDict = {"error": str(e), "success": False}
        return error_result_exception
