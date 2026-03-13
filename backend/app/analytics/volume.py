"""Volume analysis functions for trading intelligence.

This module provides functions for calculating relative volume (RVOL)
and other volume-based indicators.
"""

from __future__ import annotations

import datetime as dt

from app.logging_config import get_logger
from app.storage import PortfolioStorage

from ._date_utils import parse_target_date as _parse_target_date

logger = get_logger(__name__)


def _calculate_lookback_start(target_date: dt.date, lookback_days: int) -> dt.date:
    """Calculate lookback start date accounting for weekends/holidays.

    Args:
        target_date: Target analysis date
        lookback_days: Number of trading days to look back

    Returns:
        Start date for lookback period
    """
    calendar_days = int(lookback_days * 1.5)
    return target_date - dt.timedelta(days=calendar_days)


def _fetch_current_volume(
    storage: PortfolioStorage, symbol: str, target_date: dt.date
) -> int | None:
    """Fetch current day's volume for a symbol.

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        target_date: Date to fetch volume for

    Returns:
        Volume as integer, or None if no data or zero volume
    """
    current_volume_query = """
        SELECT volume
        FROM day_bars
        WHERE symbol = ?
          AND date = ?
        LIMIT 1
    """
    current_result = storage.query(current_volume_query, [symbol, target_date.isoformat()])

    if current_result is None or len(current_result) == 0:
        return None

    current_volume = current_result["volume"][0]
    return int(current_volume) if current_volume > 0 else None


def _fetch_average_volume(
    storage: PortfolioStorage,
    symbol: str,
    lookback_start: dt.date,
    target_date: dt.date,
) -> float | None:
    """Fetch average volume over lookback period.

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        lookback_start: Start of lookback period
        target_date: End of lookback period (exclusive)

    Returns:
        Average volume as float, or None if no data or zero average
    """
    avg_volume_query = """
        SELECT AVG(volume) as avg_volume
        FROM day_bars
        WHERE symbol = ?
          AND date >= ?
          AND date < ?
          AND volume > 0
    """
    avg_result = storage.query(
        avg_volume_query, [symbol, lookback_start.isoformat(), target_date.isoformat()]
    )

    if avg_result is None or len(avg_result) == 0:
        return None

    avg_volume = avg_result["avg_volume"][0]
    return float(avg_volume) if avg_volume and avg_volume > 0 else None


def calculate_rvol(
    storage: PortfolioStorage,
    symbol: str,
    date: dt.date | str,
    lookback_days: int = 20,
) -> float | None:
    """Calculate Relative Volume (RVOL) for a symbol on a specific date.

    RVOL measures current trading volume relative to the average volume
    over a lookback period. Values > 1.0 indicate above-average volume,
    while values < 1.0 indicate below-average volume.

    Formula: current_volume / avg(volume, lookback_days)

    Args:
        storage: PortfolioStorage instance for database access
        symbol: Stock symbol (e.g., "AAPL")
        date: Date to calculate RVOL for (YYYY-MM-DD format or date object)
        lookback_days: Number of trading days to average (default: 20)

    Returns:
        RVOL value as float, or None if insufficient data
        - 1.0 = normal volume
        - 2.0 = 2x normal volume (high activity)
        - 0.5 = 50% of normal volume (low activity)

    Example:
        >>> storage = get_storage()
        >>> rvol = calculate_rvol(storage, "AAPL", "2025-01-15", lookback_days=20)
        >>> if rvol and rvol > 1.5:
        ...     print("High volume detected!")
    """
    target_date = _parse_target_date(date)
    lookback_start = _calculate_lookback_start(target_date, lookback_days)

    logger.debug(
        "calculate_rvol_start",
        symbol=symbol,
        date=str(target_date),
        lookback_days=lookback_days,
        lookback_start=str(lookback_start),
    )

    # Get current day's volume
    current_volume = _fetch_current_volume(storage, symbol, target_date)
    if current_volume is None:
        logger.warning("calculate_rvol_no_current_data", symbol=symbol, date=str(target_date))
        return None

    # Get average volume over lookback period
    avg_volume = _fetch_average_volume(storage, symbol, lookback_start, target_date)
    if avg_volume is None:
        logger.warning(
            "calculate_rvol_no_lookback_data",
            symbol=symbol,
            lookback_start=str(lookback_start),
            date=str(target_date),
        )
        return None

    # Calculate RVOL
    rvol = float(current_volume) / avg_volume

    logger.info(
        "calculate_rvol_complete",
        symbol=symbol,
        date=str(target_date),
        current_volume=current_volume,
        avg_volume=avg_volume,
        rvol=round(rvol, 2),
    )

    return rvol


def _fetch_all_symbols(storage: PortfolioStorage, target_date: dt.date) -> list[str]:
    """Fetch all symbols with data for a specific date.

    Args:
        storage: PortfolioStorage instance
        target_date: Date to check for symbol data

    Returns:
        List of symbols
    """
    symbols_query = """
        SELECT DISTINCT symbol
        FROM day_bars
        WHERE date = ?
    """
    symbols_result = storage.query(symbols_query, [target_date.isoformat()])

    if symbols_result is None or len(symbols_result) == 0:
        return []

    return symbols_result["symbol"].to_list()


def _build_rvol_entry(
    storage: PortfolioStorage,
    symbol: str,
    rvol: float,
    target_date: dt.date,
    lookback_days: int,
) -> dict[str, float | str]:
    """Build RVOL entry with volume details for a symbol.

    Args:
        storage: PortfolioStorage instance
        symbol: Stock symbol
        rvol: Calculated RVOL value
        target_date: Analysis date
        lookback_days: Lookback period for average calculation

    Returns:
        Dict with symbol, rvol, current_volume, and avg_volume
    """
    # Get current volume
    current_volume = _fetch_current_volume(storage, symbol, target_date)

    # Get average volume
    lookback_start = _calculate_lookback_start(target_date, lookback_days)
    avg_volume = _fetch_average_volume(storage, symbol, lookback_start, target_date)

    return {
        "symbol": symbol,
        "rvol": round(rvol, 2),
        "current_volume": int(current_volume) if current_volume else 0,
        "avg_volume": int(avg_volume) if avg_volume else 0,
    }


def get_high_volume_symbols(
    storage: PortfolioStorage,
    date: dt.date | str,
    rvol_threshold: float = 1.5,
    lookback_days: int = 20,
    min_symbols: int = 10,
) -> list[dict[str, float | str]]:
    """Find symbols with unusually high volume on a specific date.

    Args:
        storage: PortfolioStorage instance for database access
        date: Date to analyze (YYYY-MM-DD format or date object)
        rvol_threshold: Minimum RVOL to be considered high volume (default: 1.5)
        lookback_days: Number of trading days for RVOL calculation (default: 20)
        min_symbols: Minimum number of symbols to return (default: 10)

    Returns:
        List of dicts with symbol, rvol, current_volume, avg_volume
        Sorted by RVOL descending

    Example:
        >>> storage = get_storage()
        >>> high_vol = get_high_volume_symbols(storage, "2025-01-15", rvol_threshold=2.0)
        >>> for item in high_vol[:5]:
        ...     print(f"{item['symbol']}: RVOL={item['rvol']:.2f}x")
    """
    target_date = _parse_target_date(date)

    # Get all symbols that have data for the target date
    symbols = _fetch_all_symbols(storage, target_date)
    if not symbols:
        logger.warning("get_high_volume_symbols_no_data", date=str(target_date))
        return []

    # Calculate RVOL for each symbol and filter by threshold
    high_volume_list: list[dict[str, float | str]] = []

    for symbol in symbols:
        rvol = calculate_rvol(storage, symbol, target_date, lookback_days)

        if rvol is not None and rvol >= rvol_threshold:
            entry = _build_rvol_entry(storage, symbol, rvol, target_date, lookback_days)
            high_volume_list.append(entry)

    # Sort by RVOL descending
    high_volume_list.sort(key=lambda x: x["rvol"], reverse=True)

    # Return at least min_symbols if available
    result = high_volume_list[: max(min_symbols, len(high_volume_list))]

    logger.info(
        "get_high_volume_symbols_complete",
        date=str(target_date),
        threshold=rvol_threshold,
        total_symbols=len(symbols),
        high_volume_count=len(high_volume_list),
        returned_count=len(result),
    )

    return result
