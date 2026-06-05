"""Fear & Greed data processing and storage.

Process market data and store results in fear_greed_inputs table.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from app.logging_config import get_logger
from app.tasks.market_data.fear_greed_indicators import (
    calculate_market_breadth,
    calculate_rsi,
    calculate_sma,
)

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

logger = get_logger(__name__)


def compute_date_indicators(
    spy_close: float,
    prices_up_to_date: list[float],
    date: dt.date,
    vix_data: dict[dt.date, float],
    hy_spread_dict: dict[dt.date, float],
) -> tuple[float, float, float | None, float | None] | None:
    """Compute all indicators for a single date.

    Returns tuple of (sma_200, rsi_14, vix_close, hy_spread) or None if calculation fails.
    Missing observed VIX/HY values stay null so freshness/as-of reporting remains honest.
    """
    sma_200 = calculate_sma(prices_up_to_date, 200)
    rsi_14 = calculate_rsi(prices_up_to_date, 14)

    if sma_200 is None or rsi_14 is None:
        logger.warning("indicator_calculation_failed", date=str(date))
        return None

    vix_close = vix_data.get(date)
    hy_spread = hy_spread_dict.get(date)

    return sma_200, rsi_14, vix_close, hy_spread


def upsert_inputs_record(
    storage: PortfolioStorage,
    date: dt.date,
    spy_close: float,
    sma_200: float,
    rsi_14: float,
    vix_close: float | None,
    hy_spread: float | None,
    breadth_pct: float | None,
) -> None:
    """Upsert a single fear_greed_inputs record to database."""
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO fear_greed_inputs
            (as_of_date, spy_close, spy_sma_200, rsi_14, vix_close, hy_spread, breadth_pct)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (as_of_date)
            DO UPDATE SET
                spy_close = EXCLUDED.spy_close,
                spy_sma_200 = EXCLUDED.spy_sma_200,
                rsi_14 = EXCLUDED.rsi_14,
                vix_close = EXCLUDED.vix_close,
                hy_spread = EXCLUDED.hy_spread,
                breadth_pct = EXCLUDED.breadth_pct
            """,
            [str(date), spy_close, sma_200, rsi_14, vix_close, hy_spread, breadth_pct],
        )
        conn.commit()


def calculate_and_upsert_inputs(
    storage: PortfolioStorage,
    spy_dict: dict[dt.date, float],
    dates: list[dt.date],
    start_date: dt.date,
    vix_data: dict[dt.date, float],
    hy_spread_dict: dict[dt.date, float],
) -> int:
    """Calculate indicators for each date and upsert to database.

    Args:
        storage: Storage instance
        spy_dict: SPY prices by date
        dates: Sorted list of all dates with SPY data
        start_date: Start date for processing
        vix_data: VIX prices by date
        hy_spread_dict: HY spread values by date

    Returns:
        Number of successful updates
    """
    updates_count = 0
    for i, date in enumerate(dates):
        if date < start_date:
            continue

        prices_up_to_date = [spy_dict[d] for d in dates[: i + 1]]

        if len(prices_up_to_date) < 200:
            logger.warning(
                "insufficient_data_for_indicators",
                date=str(date),
                data_points=len(prices_up_to_date),
            )
            continue

        spy_close = spy_dict[date]
        indicators = compute_date_indicators(
            spy_close,
            prices_up_to_date,
            date,
            vix_data,
            hy_spread_dict,
        )

        if indicators is None:
            continue

        sma_200, rsi_14, vix_close, hy_spread = indicators
        breadth_pct = calculate_market_breadth(storage, date)

        upsert_inputs_record(
            storage, date, spy_close, sma_200, rsi_14, vix_close, hy_spread, breadth_pct
        )
        updates_count += 1

    return updates_count
