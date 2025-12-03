"""Market data source functions - fetch and aggregate data from storage."""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from app.portfolio.models import PriceData
    from app.storage.facade import PortfolioStorage as Storage


def calculate_daily_change_pct(
    storage: Storage,
    ticker: str,
    current_price: float,
) -> float | None:
    """Calculate daily change percentage from day_bars historical data.

    Args:
        storage: Storage instance for database access
        ticker: Symbol to calculate change for
        current_price: Current price

    Returns:
        Daily change percentage, or None if no historical data
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT close
            FROM day_bars
            WHERE ticker = %s
            ORDER BY date DESC
            LIMIT 1 OFFSET 1
            """,
            [ticker],
        )
        row = result.fetchone()
        if row and row[0]:
            prev_close = float(row[0])
            return ((current_price - prev_close) / prev_close) * 100
    return None


def calculate_weekly_change_pct(
    storage: Storage,
    ticker: str,
    current_price: float,
) -> float | None:
    """Calculate week-over-week change: current price vs last week's close.

    Finds the last trading day of the previous calendar week (typically Friday,
    but could be Thursday if Friday was a holiday) and compares current price to that.

    This answers: "How are we doing this week compared to where we ended last week?"

    Args:
        storage: Storage instance for database access
        ticker: Symbol to calculate change for
        current_price: Current price

    Returns:
        Week-over-week change percentage, or None if no historical data
    """
    with storage.connection() as conn:
        # Find last week's close: the most recent trading day before this week started
        # This week started on the most recent Monday (or today if today is Monday)
        result = conn.execute(
            """
            SELECT close, date
            FROM day_bars
            WHERE ticker = %s
              AND date < date_trunc('week', CURRENT_DATE)::date
            ORDER BY date DESC
            LIMIT 1
            """,
            [ticker],
        )
        row = result.fetchone()
        if row and row[0]:
            last_week_close = float(row[0])
            return ((current_price - last_week_close) / last_week_close) * 100
    return None


def fetch_sector_data_with_changes(
    storage: Storage,
    sector_symbols: list[str],
    sector_price_data: dict[str, PriceData],
) -> dict[str, tuple[float | None, float | None, str | None]]:
    """Fetch sector data with daily change percentages using batch query.

    IMPORTANT: Uses ONLY day_bars historical data for change calculation.
    Never uses cache-to-cache comparison as cache timestamps are unreliable
    (cache may be refreshed without market data actually changing).

    Args:
        storage: Storage instance for database access
        sector_symbols: List of sector ETF symbols
        sector_price_data: Dict of current price data by symbol

    Returns:
        Dict mapping symbol to (price, change_pct, timestamp) tuple
    """
    sector_data: dict[str, tuple[float | None, float | None, str | None]] = {}

    # Get previous closes in a single batch query (avoiding N+1 query problem)
    # Using window function to get second-most-recent close for each ticker
    # This ensures we calculate change from actual market closes, not cache timestamps
    with storage.connection() as conn:
        # Cast list[str] to expected parameter type for ANY operator compatibility
        params: list[
            str | int | float | bool | datetime | list[str | int | float | bool | None] | None
        ] = [cast(list[str | int | float | bool | None], sector_symbols)]

        result = conn.execute(
            """
            SELECT ticker, close
            FROM (
                SELECT ticker, close, ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date DESC) as rn
                FROM day_bars
                WHERE ticker = ANY(%s)
            ) ranked
            WHERE rn = 2
            """,
            params,
        )
        prev_closes: dict[str, float] = {}
        for row in result.fetchall():
            ticker_val = row[0]
            close_val = row[1]
            if isinstance(ticker_val, str) and isinstance(close_val, (int, float)):
                prev_closes[ticker_val] = float(close_val)

    # Calculate change percentages
    for symbol in sector_symbols:
        current_price = sector_price_data.get(symbol)
        if not current_price:
            sector_data[symbol] = (None, None, None)
            continue

        prev_close = prev_closes.get(symbol)
        if prev_close:
            change_pct = ((current_price.price - prev_close) / prev_close) * 100
            sector_timestamp = current_price.cached_at.isoformat()
            sector_data[symbol] = (current_price.price, change_pct, sector_timestamp)
        else:
            # No historical data, just use current price
            sector_timestamp = current_price.cached_at.isoformat()
            sector_data[symbol] = (current_price.price, None, sector_timestamp)

    return sector_data


def get_actual_data_dates(
    storage: Storage,
    symbols: list[str],
) -> dict[str, dt.datetime]:
    """Get ACTUAL data dates from day_bars (not cache timestamps).

    This shows when the market data was created, not when we fetched it.

    Args:
        storage: Storage instance for database access
        symbols: List of symbols to get dates for

    Returns:
        Dict mapping symbol to actual data timestamp
    """
    actual_data_dates: dict[str, dt.datetime] = {}
    with storage.connection() as conn:
        for symbol in symbols:
            result = conn.execute("SELECT MAX(date) FROM day_bars WHERE ticker = %s", [symbol])
            row = result.fetchone()
            if row and row[0]:
                # Convert date to timestamp at market close (21:00 UTC = 4:00 PM ET)
                data_date = row[0]
                if isinstance(data_date, date):
                    data_timestamp = dt.datetime.combine(
                        data_date, dt.time(21, 0, 0), tzinfo=dt.UTC
                    )
                    actual_data_dates[symbol] = data_timestamp
    return actual_data_dates


def get_market_data_timestamp(storage: Storage) -> str:
    """Get actual market data timestamp from Fear & Greed data.

    This represents when the underlying market data is from, not when we cached it.

    Args:
        storage: Storage instance for database access

    Returns:
        ISO format timestamp string
    """
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT as_of_date FROM fear_greed_daily ORDER BY as_of_date DESC LIMIT 1"
        )
        row = result.fetchone()
        if row and row[0]:
            # Use the actual market data date (as_of_date) for the timestamp
            # This shows users the age of the underlying market data, not the cache
            market_data_date = row[0]
            # Set time to market close (4:00 PM ET = 21:00 UTC) for consistency
            if isinstance(market_data_date, date):
                market_close_time = dt.datetime.combine(
                    market_data_date, dt.time(21, 0, 0), tzinfo=dt.UTC
                )
                return market_close_time.isoformat()
    # Return empty string if no data found (caller should handle fallback)
    return ""


def get_put_call_ratio_data(
    storage: Storage,
) -> tuple[float, str] | None:
    """Get latest Put/Call Ratio from fear_greed_inputs.

    Args:
        storage: Storage instance for database access

    Returns:
        Tuple of (ratio, timestamp) if found, None otherwise
    """
    with storage.connection() as conn:
        result = conn.execute(
            "SELECT put_call_ratio, as_of_date FROM fear_greed_inputs WHERE put_call_ratio IS NOT NULL ORDER BY as_of_date DESC LIMIT 1"
        )
        row = result.fetchone()
        if row and row[0]:
            put_call_ratio_val = row[0]
            putcall_date_val = row[1]
            # Type narrowing: ensure put_call_ratio is float and putcall_date is date
            if isinstance(put_call_ratio_val, (int, float)) and isinstance(putcall_date_val, date):
                put_call_ratio = float(put_call_ratio_val)
                putcall_date = putcall_date_val
                # Set time to market close (4:00 PM ET = 21:00 UTC) for consistency
                putcall_timestamp = dt.datetime.combine(
                    putcall_date, dt.time(21, 0, 0), tzinfo=dt.UTC
                ).isoformat()
                return (put_call_ratio, putcall_timestamp)
    return None


def get_options_activity_metrics(
    storage: Storage,
) -> dict[str, float | str | list[dict[str, float | str]]] | None:
    """Get latest options activity metrics from options_market_metrics table.

    Args:
        storage: Storage instance for database access

    Returns:
        Dict with metrics data if found, None otherwise
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT near_term_pct, concentration_pct, sector_weights, source_timestamp
            FROM options_market_metrics
            ORDER BY as_of_date DESC
            LIMIT 1
            """
        )
        row = result.fetchone()
        if row:
            near_term_val = row[0]
            concentration_val = row[1]
            sector_weights_val = row[2]  # JSONB
            source_timestamp_val = row[3]

            # Type narrowing: ensure proper types
            if isinstance(near_term_val, (int, float)) and isinstance(
                concentration_val, (int, float)
            ):
                near_term_pct = float(near_term_val)
                concentration_pct = float(concentration_val)

                # Calculate signals based on thresholds
                # Near-term: >65% = High (event-driven), 45-65% = Normal, <45% = Low
                if near_term_pct > 65:
                    near_term_signal = "High"
                elif near_term_pct >= 45:
                    near_term_signal = "Normal"
                else:
                    near_term_signal = "Low"

                # Concentration: >80% = Focused, 50-80% = Balanced, <50% = Dispersed
                if concentration_pct > 80:
                    concentration_signal = "Focused"
                elif concentration_pct >= 50:
                    concentration_signal = "Balanced"
                else:
                    concentration_signal = "Dispersed"

                # Get top 3 sectors by weight - ensure sector_weights is dict-like
                if isinstance(sector_weights_val, dict):
                    sector_items = sorted(
                        sector_weights_val.items(), key=lambda x: x[1], reverse=True
                    )[:3]
                    top_sectors = [
                        {"sector": sector, "weight_pct": weight} for sector, weight in sector_items
                    ]

                    # Ensure source_timestamp has isoformat method
                    if hasattr(source_timestamp_val, "isoformat"):
                        return {
                            "near_term_pct": near_term_pct,
                            "near_term_signal": near_term_signal,
                            "concentration_pct": concentration_pct,
                            "concentration_signal": concentration_signal,
                            "top_sectors": top_sectors,
                            "last_updated": source_timestamp_val.isoformat(),
                        }
    return None


# Sector ETF constants
SECTOR_ETFS = {
    "XLK": "Technology",
    "XLF": "Financials",
    "XLE": "Energy",
    "XLV": "Healthcare",
    "XLY": "Consumer Discretionary",
    "XLP": "Consumer Staples",
    "XLI": "Industrials",
    "XLU": "Utilities",
    "XLRE": "Real Estate",
    "XLB": "Materials",
    "XLC": "Communication Services",
}
