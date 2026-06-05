"""Fear & Greed data fetching functions.

Fetch market data from database and external sources:
- SPY price data from day_bars
- VIX volatility index
- High-Yield spread from FRED
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from app.portfolio.price_fetcher import PriceDataFetcher
from app.sources.fred import FREDSource
from app.utils.market_hours import NY_TZ

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
) -> tuple[dict[dt.date, float], dict[dt.date, float]]:
    """Fetch observed VIX and HY spread values.

    Args:
        storage: Storage instance
        start_date: Start date for data fetch
        end_date: End date for data fetch

    Returns:
        Tuple of (vix_dict, hy_spread_dict)
    """
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

    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT as_of_date, vix_close
            FROM fear_greed_inputs
            WHERE vix_close IS NOT NULL
              AND as_of_date >= %s
              AND as_of_date <= %s
            ORDER BY as_of_date ASC
            """,
            [str(start_date), str(end_date)],
        )
        for row in result.fetchall():
            date_value = row[0]
            vix_value = row[1]
            if isinstance(date_value, dt.date) and vix_value is not None:
                vix_dict.setdefault(date_value, float(vix_value))

    current_vix = PriceDataFetcher(storage).fetch_price_data(["^VIX"]).get("^VIX")
    if current_vix and current_vix.price > 0 and current_vix.cached_at:
        quote_ts = (
            current_vix.cached_at
            if current_vix.cached_at.tzinfo
            else current_vix.cached_at.replace(tzinfo=dt.UTC)
        )
        quote_date = quote_ts.astimezone(NY_TZ).date()
        if start_date <= quote_date <= end_date:
            vix_dict[quote_date] = float(current_vix.price)

    hy_spread_dict: dict[dt.date, float] = {}
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT as_of_date, hy_spread
            FROM fear_greed_inputs
            WHERE hy_spread IS NOT NULL
              AND as_of_date >= %s
              AND as_of_date <= %s
            ORDER BY as_of_date ASC
            """,
            [str(start_date), str(end_date)],
        )
        for row in result.fetchall():
            date_value = row[0]
            hy_value = row[1]
            if isinstance(date_value, dt.date) and hy_value is not None:
                hy_spread_dict[date_value] = float(hy_value)

    # Fetch observed HY spread data from FRED and overlay any fresh official prints.
    fred_source = FREDSource()
    hy_spread_data = fred_source.fetch_series("HY_SPREAD", start_date, end_date)
    if hy_spread_data:
        latest_official_hy_date = max(row[0] for row in hy_spread_data)
        hy_spread_dict = {
            day: value
            for day, value in hy_spread_dict.items()
            if day <= latest_official_hy_date
        }
    hy_spread_dict.update(dict(hy_spread_data))

    return vix_dict, hy_spread_dict
