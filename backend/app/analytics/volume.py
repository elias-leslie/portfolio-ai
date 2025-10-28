"""Volume analysis functions for trading intelligence.

This module provides functions for calculating relative volume (RVOL)
and other volume-based indicators.
"""

from __future__ import annotations

import datetime as dt

from app.logging_config import get_logger
from app.storage import DuckDBStorage

logger = get_logger(__name__)


def calculate_rvol(
    storage: DuckDBStorage,
    ticker: str,
    date: dt.date | str,
    lookback_days: int = 20,
) -> float | None:
    """Calculate Relative Volume (RVOL) for a ticker on a specific date.

    RVOL measures current trading volume relative to the average volume
    over a lookback period. Values > 1.0 indicate above-average volume,
    while values < 1.0 indicate below-average volume.

    Formula: current_volume / avg(volume, lookback_days)

    Args:
        storage: DuckDBStorage instance for database access
        ticker: Stock ticker symbol (e.g., "AAPL")
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
    # Convert string date to date object if needed
    if isinstance(date, str):
        target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
    else:
        target_date = date

    # Calculate lookback period start date
    # Add extra calendar days to account for weekends/holidays
    # Approximate: 20 trading days ≈ 28-30 calendar days
    calendar_days = int(lookback_days * 1.5)
    lookback_start = target_date - dt.timedelta(days=calendar_days)

    logger.debug(
        "calculate_rvol_start",
        ticker=ticker,
        date=str(target_date),
        lookback_days=lookback_days,
        lookback_start=str(lookback_start),
    )

    # Query current day's volume
    current_volume_query = """
        SELECT volume
        FROM day_bars
        WHERE ticker = ?
          AND date = ?
        LIMIT 1
    """

    current_result = storage.query(
        current_volume_query,
        [ticker, target_date],
    )

    if current_result is None or len(current_result) == 0:
        logger.warning(
            "calculate_rvol_no_current_data",
            ticker=ticker,
            date=str(target_date),
        )
        return None

    current_volume = current_result["volume"][0]

    if current_volume == 0:
        logger.warning(
            "calculate_rvol_zero_volume",
            ticker=ticker,
            date=str(target_date),
        )
        return None

    # Query average volume over lookback period (excluding current day)
    avg_volume_query = """
        SELECT AVG(volume) as avg_volume
        FROM day_bars
        WHERE ticker = ?
          AND date >= ?
          AND date < ?
          AND volume > 0
    """

    avg_result = storage.query(
        avg_volume_query,
        [ticker, lookback_start, target_date],
    )

    if avg_result is None or len(avg_result) == 0:
        logger.warning(
            "calculate_rvol_no_lookback_data",
            ticker=ticker,
            lookback_start=str(lookback_start),
            date=str(target_date),
        )
        return None

    avg_volume = avg_result["avg_volume"][0]

    if avg_volume is None or avg_volume == 0:
        logger.warning(
            "calculate_rvol_zero_avg_volume",
            ticker=ticker,
            lookback_start=str(lookback_start),
            date=str(target_date),
        )
        return None

    # Calculate RVOL
    rvol = float(current_volume) / float(avg_volume)

    logger.info(
        "calculate_rvol_complete",
        ticker=ticker,
        date=str(target_date),
        current_volume=current_volume,
        avg_volume=float(avg_volume),
        rvol=round(rvol, 2),
    )

    return rvol


def get_high_volume_tickers(
    storage: DuckDBStorage,
    date: dt.date | str,
    rvol_threshold: float = 1.5,
    lookback_days: int = 20,
    min_tickers: int = 10,
) -> list[dict[str, float | str]]:
    """Find tickers with unusually high volume on a specific date.

    Args:
        storage: DuckDBStorage instance for database access
        date: Date to analyze (YYYY-MM-DD format or date object)
        rvol_threshold: Minimum RVOL to be considered high volume (default: 1.5)
        lookback_days: Number of trading days for RVOL calculation (default: 20)
        min_tickers: Minimum number of tickers to return (default: 10)

    Returns:
        List of dicts with ticker, rvol, current_volume, avg_volume
        Sorted by RVOL descending

    Example:
        >>> storage = get_storage()
        >>> high_vol = get_high_volume_tickers(storage, "2025-01-15", rvol_threshold=2.0)
        >>> for item in high_vol[:5]:
        ...     print(f"{item['ticker']}: RVOL={item['rvol']:.2f}x")
    """
    # Convert string date to date object if needed
    if isinstance(date, str):
        target_date = dt.datetime.strptime(date, "%Y-%m-%d").date()
    else:
        target_date = date

    # Get all tickers that have data for the target date
    tickers_query = """
        SELECT DISTINCT ticker
        FROM day_bars
        WHERE date = ?
    """

    tickers_result = storage.query(tickers_query, [target_date])

    if tickers_result is None or len(tickers_result) == 0:
        logger.warning(
            "get_high_volume_tickers_no_data",
            date=str(target_date),
        )
        return []

    tickers = tickers_result["ticker"].to_list()

    # Calculate RVOL for each ticker
    high_volume_list: list[dict[str, float | str]] = []

    for ticker in tickers:
        rvol = calculate_rvol(storage, ticker, target_date, lookback_days)

        if rvol is not None and rvol >= rvol_threshold:
            # Get current and average volume for reporting
            current_volume_query = """
                SELECT volume
                FROM day_bars
                WHERE ticker = ? AND date = ?
                LIMIT 1
            """
            current_result = storage.query(current_volume_query, [ticker, target_date])
            current_volume = current_result["volume"][0] if current_result is not None else 0

            # Calculate average volume
            calendar_days = int(lookback_days * 1.5)
            lookback_start = target_date - dt.timedelta(days=calendar_days)
            avg_volume_query = """
                SELECT AVG(volume) as avg_volume
                FROM day_bars
                WHERE ticker = ? AND date >= ? AND date < ? AND volume > 0
            """
            avg_result = storage.query(avg_volume_query, [ticker, lookback_start, target_date])
            avg_volume = avg_result["avg_volume"][0] if avg_result is not None else 0

            high_volume_list.append(
                {
                    "ticker": ticker,
                    "rvol": round(rvol, 2),
                    "current_volume": int(current_volume),
                    "avg_volume": int(avg_volume) if avg_volume else 0,
                }
            )

    # Sort by RVOL descending
    high_volume_list.sort(key=lambda x: x["rvol"], reverse=True)

    # Return at least min_tickers if available
    result = high_volume_list[: max(min_tickers, len(high_volume_list))]

    logger.info(
        "get_high_volume_tickers_complete",
        date=str(target_date),
        threshold=rvol_threshold,
        total_tickers=len(tickers),
        high_volume_count=len(high_volume_list),
        returned_count=len(result),
    )

    return result
