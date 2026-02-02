"""Fear & Greed data fetching functions.

Fetch market data from database and external sources:
- SPY price data from day_bars
- VIX volatility index
- High-Yield spread from FRED
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from app.sources.fred import FREDSource

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage


def fetch_spy_data(
    storage: PortfolioStorage, start_date: dt.date, end_date: dt.date
) -> dict[dt.date, float]:
    """Fetch SPY OHLCV data from day_bars table.

    Args:
        storage: Storage instance
        start_date: Start date for data fetch
        end_date: End date for data fetch

    Returns:
        Dict mapping date to closing price
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT date, close
            FROM day_bars
            WHERE symbol = 'SPY'
              AND date >= %s
              AND date <= %s
            ORDER BY date ASC
            """,
            [str(start_date), str(end_date)],
        )
        spy_data = result.fetchall()

    spy_dict: dict[dt.date, float] = {}
    for row in spy_data:
        date_value = row[0]
        close_value = row[1]
        if isinstance(date_value, dt.date) and close_value is not None:
            spy_dict[date_value] = float(close_value)

    return spy_dict


def fetch_market_indicators(
    storage: PortfolioStorage, start_date: dt.date, end_date: dt.date
) -> tuple[dict[dt.date, float], dict[dt.date, float], float, float]:
    """Fetch VIX, HY spread, and fallback estimates.

    Args:
        storage: Storage instance
        start_date: Start date for data fetch
        end_date: End date for data fetch

    Returns:
        Tuple of (vix_dict, hy_spread_dict, vix_estimate, hy_spread_fallback)
    """
    # Get latest VIX and HY_spread for fallback estimates
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT vix_close, hy_spread
            FROM fear_greed_inputs
            WHERE vix_close IS NOT NULL
            ORDER BY as_of_date DESC
            LIMIT 1
            """
        )
        latest = result.fetchone()
        vix_estimate = float(latest[0]) if latest and latest[0] is not None else 19.5
        hy_spread_fallback = float(latest[1]) if latest and latest[1] is not None else 3.13

    # Fetch VIX data from database if available
    vix_dict: dict[dt.date, float] = {}
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT date, close
            FROM day_bars
            WHERE symbol = '^VIX'
              AND date >= %s
              AND date <= %s
            ORDER BY date ASC
            """,
            [str(start_date), str(end_date)],
        )
        for row in result.fetchall():
            date_value = row[0]
            close_value = row[1]
            if isinstance(date_value, dt.date) and close_value is not None:
                vix_dict[date_value] = float(close_value)

    # Fetch HY spread data from FRED
    fred_source = FREDSource()
    hy_spread_data = fred_source.fetch_series("HY_SPREAD", start_date, end_date)
    hy_spread_dict = dict(hy_spread_data)

    return vix_dict, hy_spread_dict, vix_estimate, hy_spread_fallback
