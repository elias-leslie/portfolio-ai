"""Market data source functions - fetch and aggregate data from storage."""

from __future__ import annotations

import datetime as dt
from datetime import date, datetime
from typing import TYPE_CHECKING, cast

# US market close at 4:00 PM ET = 21:00 UTC
_MARKET_CLOSE_UTC = dt.time(21, 0, 0)

if TYPE_CHECKING:
    from app.portfolio.models import PriceData
    from app.storage.facade import PortfolioStorage as Storage


def _date_to_market_close_ts(d: date) -> dt.datetime:
    """Convert a date to a datetime at market close (21:00 UTC)."""
    return dt.datetime.combine(d, _MARKET_CLOSE_UTC, tzinfo=dt.UTC)


def calculate_daily_change_pct(
    storage: Storage,
    symbol: str,
    current_price: float,
) -> float | None:
    """Calculate daily change percentage from day_bars historical data.

    Args:
        storage: Storage instance for database access
        symbol: Symbol to calculate change for
        current_price: Current price

    Returns:
        Daily change percentage, or None if no historical data
    """
    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT close
            FROM day_bars
            WHERE symbol = %s
            ORDER BY date DESC
            LIMIT 1 OFFSET 1
            """,
            [symbol],
        )
        row = result.fetchone()
        if row and row[0]:
            prev_close = float(row[0])
            return ((current_price - prev_close) / prev_close) * 100
    return None


def calculate_weekly_change_pct(
    storage: Storage,
    symbol: str,
    current_price: float,
) -> float | None:
    """Calculate week-over-week change: current price vs last week's close.

    Finds the last trading day of the previous calendar week (typically Friday,
    but could be Thursday if Friday was a holiday) and compares current price to that.

    This answers: "How are we doing this week compared to where we ended last week?"

    Args:
        storage: Storage instance for database access
        symbol: Symbol to calculate change for
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
            WHERE symbol = %s
              AND date < date_trunc('week', CURRENT_DATE)::date
            ORDER BY date DESC
            LIMIT 1
            """,
            [symbol],
        )
        row = result.fetchone()
        if row and row[0]:
            last_week_close = float(row[0])
            return ((current_price - last_week_close) / last_week_close) * 100
    return None


def _fetch_prev_closes_batch(
    storage: Storage,
    sector_symbols: list[str],
) -> dict[str, float]:
    """Fetch previous closes for a list of symbols in a single batch query."""
    params: list[
        str | int | float | bool | date | datetime | list[str | int | float | bool | None] | None
    ] = [cast(list[str | int | float | bool | None], sector_symbols)]

    with storage.connection() as conn:
        result = conn.execute(
            """
            SELECT symbol, close
            FROM (
                SELECT symbol, close, ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) as rn
                FROM day_bars
                WHERE symbol = ANY(%s)
            ) ranked
            WHERE rn = 2
            """,
            params,
        )
        prev_closes: dict[str, float] = {}
        for row in result.fetchall():
            symbol_val = row[0]
            close_val = row[1]
            if isinstance(symbol_val, str) and isinstance(close_val, (int, float)):
                prev_closes[symbol_val] = float(close_val)
    return prev_closes


def _sector_entry(
    current_price: PriceData | None,
    prev_close: float | None,
) -> tuple[float | None, float | None, str | None]:
    """Build a single sector data tuple from price data and previous close."""
    if not current_price:
        return (None, None, None)
    timestamp = current_price.cached_at.isoformat()
    if prev_close:
        change_pct = ((current_price.price - prev_close) / prev_close) * 100
        return (current_price.price, change_pct, timestamp)
    return (current_price.price, None, timestamp)


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
    prev_closes = _fetch_prev_closes_batch(storage, sector_symbols)
    return {
        symbol: _sector_entry(sector_price_data.get(symbol), prev_closes.get(symbol))
        for symbol in sector_symbols
    }


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
            result = conn.execute("SELECT MAX(date) FROM day_bars WHERE symbol = %s", [symbol])
            row = result.fetchone()
            if row and row[0] and isinstance(row[0], date):
                actual_data_dates[symbol] = _date_to_market_close_ts(row[0])
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
        if row and row[0] and isinstance(row[0], date):
            # Use the actual market data date (as_of_date) for the timestamp
            # This shows users the age of the underlying market data, not the cache
            return _date_to_market_close_ts(row[0]).isoformat()
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
                putcall_timestamp = _date_to_market_close_ts(putcall_date_val).isoformat()
                return (float(put_call_ratio_val), putcall_timestamp)
    return None


def _near_term_signal(pct: float) -> str:
    """Classify near-term options percentage into a signal label."""
    if pct > 65:
        return "High"
    if pct >= 45:
        return "Normal"
    return "Low"


def _concentration_signal(pct: float) -> str:
    """Classify concentration percentage into a signal label."""
    if pct > 80:
        return "Focused"
    if pct >= 50:
        return "Balanced"
    return "Dispersed"


def _top_sectors(sector_weights: dict[str, float], n: int = 3) -> list[dict[str, float | str]]:
    """Return the top-n sectors by weight as a list of dicts."""
    items = sorted(sector_weights.items(), key=lambda x: x[1], reverse=True)[:n]
    return [{"sector": sector, "weight_pct": weight} for sector, weight in items]


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

    if not row:
        return None

    near_term_val, concentration_val, sector_weights_val, source_timestamp_val = row

    if not isinstance(near_term_val, (int, float)) or not isinstance(concentration_val, (int, float)):
        return None
    if not isinstance(sector_weights_val, dict):
        return None

    source_timestamp_iso = getattr(source_timestamp_val, "isoformat", None)
    if not callable(source_timestamp_iso):
        return None

    near_term_pct = float(near_term_val)
    concentration_pct = float(concentration_val)

    return {
        "near_term_pct": near_term_pct,
        "near_term_signal": _near_term_signal(near_term_pct),
        "concentration_pct": concentration_pct,
        "concentration_signal": _concentration_signal(concentration_pct),
        "top_sectors": _top_sectors(sector_weights_val),
        "last_updated": source_timestamp_iso(),
    }
