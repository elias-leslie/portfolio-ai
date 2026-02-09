"""Fear & Greed indicator pipeline tasks.

Populates fear_greed_inputs table with market data for Fear & Greed Index calculation:
- SPY price data (SMA_200, RSI_14)
- VIX volatility index
- High-Yield spread from FRED
- Market breadth from sector ETFs
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.indicators import calculate_fear_greed
from app.tasks.market_data.fear_greed_data import fetch_market_indicators, fetch_spy_data
from app.tasks.market_data.fear_greed_data import (
import uuid
    fetch_market_indicators as _fetch_market_indicators,
)
from app.tasks.market_data.fear_greed_data import fetch_spy_data as _fetch_spy_data
from app.tasks.market_data.fear_greed_indicators import (
    calculate_market_breadth as _calculate_market_breadth,
)
from app.tasks.market_data.fear_greed_processing import calculate_and_upsert_inputs
from app.tasks.market_data.fear_greed_processing import (
    calculate_and_upsert_inputs as _calculate_and_upsert_inputs,
)
from app.tasks.types import FearGreedPipelineResultDict


    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)

__all__ = [
    "_calculate_and_upsert_inputs",
    "_calculate_market_breadth",
    "_fetch_market_indicators",
    "_fetch_spy_data",
    "populate_fear_greed_inputs",
]


def _validate_and_fetch_data(
    storage: PortfolioStorage, end_date: dt.date, start_date: dt.date, data_start: dt.date
) -> (
    tuple[
        dict[dt.date, float],
        list[dt.date],
        dict[dt.date, float],
        dict[dt.date, float],
        float,
        float,
    ]
    | None
):
    """Validate SPY data and fetch all required market indicators.

    Returns (spy_dict, dates, vix_data, hy_spread_dict, vix_est, hy_fallback) or None on error.
    """
    spy_dict = fetch_spy_data(storage, data_start, end_date)

    if len(spy_dict) < 200:
        return None

    dates = sorted(spy_dict.keys())
    vix_data, hy_spread_dict, vix_estimate, hy_spread_fallback = fetch_market_indicators(
        storage, start_date, end_date
    )

    return spy_dict, dates, vix_data, hy_spread_dict, vix_estimate, hy_spread_fallback


def _process_and_return_results(
    task_id: str,
    storage: PortfolioStorage,
    spy_dict: dict[dt.date, float],
    dates: list[dt.date],
    start_date: dt.date,
    end_date: dt.date,
    vix_data: dict[dt.date, float],
    hy_spread_dict: dict[dt.date, float],
    vix_estimate: float,
    hy_spread_fallback: float,
) -> FearGreedPipelineResultDict:
    """Process market data and return task results."""
    logger.info(
        "populated_market_indicators",
        task_id=task_id,
        vix_count=len(vix_data),
        hy_spread_count=len(hy_spread_dict),
    )

    updates_count = calculate_and_upsert_inputs(
        storage,
        spy_dict,
        dates,
        start_date,
        vix_data,
        hy_spread_dict,
        vix_estimate,
        hy_spread_fallback,
    )

    logger.info(
        "populate_fear_greed_inputs_completed",
        task_id=task_id,
        updates_count=updates_count,
    )

    calculate_fear_greed()

    return {
        "task_id": task_id,
        "updates_count": updates_count,
        "date_range": f"{start_date} to {end_date}",
        "success": True,
    }


def populate_fear_greed_inputs(days: int = 7) -> FearGreedPipelineResultDict:
    """Populate fear_greed_inputs table with latest market data.

    This task replaces the manual script update_fear_greed_inputs.py.
    Runs daily to ensure fear_greed_inputs is up-to-date.

    Process:
    1. Fetch SPY OHLCV from day_bars (last N days + 200 for SMA_200)
    2. Calculate SMA_200 and RSI_14 from SPY data
    3. Fetch VIX from day_bars (if available)
    4. Use estimates for missing VIX/HY_spread data
    5. Upsert fear_greed_inputs for each date
    6. Trigger calculate_fear_greed task

    Args:
        days: Number of days to update (default 7)

    Returns:
        FearGreedPipelineResultDict: Task result with update count and status
    """
    task_id = str(uuid.uuid4())
    logger.info("populate_fear_greed_inputs_started", task_id=task_id, days=days)

    try:
        storage = get_storage()
        end_date = dt.date.today()
        start_date = end_date - dt.timedelta(days=days)
        data_start = end_date - dt.timedelta(days=300)

        result = _validate_and_fetch_data(storage, end_date, start_date, data_start)

        if result is None:
            error_msg = "Insufficient SPY data: need >= 200 days"
            logger.error("populate_fear_greed_inputs_failed", task_id=task_id, error=error_msg)
            return {
                "task_id": task_id,
                "updates_count": 0,
                "error": error_msg,
                "success": False,
            }

        spy_dict, dates, vix_data, hy_spread_dict, vix_estimate, hy_spread_fallback = result

        return _process_and_return_results(
            task_id,
            storage,
            spy_dict,
            dates,
            start_date,
            end_date,
            vix_data,
            hy_spread_dict,
            vix_estimate,
            hy_spread_fallback,
        )

    except Exception as e:
        logger.error(
            "populate_fear_greed_inputs_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        return {
            "task_id": task_id,
            "updates_count": 0,
            "error": str(e),
            "success": False,
        }
