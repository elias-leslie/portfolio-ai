"""Watchlist calculator module for entry/exit/stop calculation and position sizing.

This module provides functions for:
- Swing low/high detection (support/resistance levels)
- Entry price calculation
- Stop loss calculation (ATR-based and technical)
- Profit target calculation
- Position sizing based on risk budget
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def get_swing_low(conn: Any, symbol: str, days: int = 10) -> float | None:
    """Get the lowest close price over the last N trading days.

    Args:
        conn: Database connection
        symbol: Stock ticker symbol
        days: Number of trading days to look back (default: 10)

    Returns:
        Lowest close price over the period, or None if insufficient data

    Example:
        >>> from app.storage.connection import ConnectionManager
        >>> cm = ConnectionManager()
        >>> with cm.connection() as conn:
        ...     swing_low = get_swing_low(conn, "NVDA", days=10)
        >>> # Returns the lowest close price in the last 10 trading days
    """
    query = """
        SELECT MIN(close) as swing_low, COUNT(*) as count
        FROM (
            SELECT close
            FROM day_bars
            WHERE ticker = %s
            ORDER BY date DESC
            LIMIT %s
        ) recent_bars
    """

    result = conn.execute(query, [symbol, days])
    row = result.fetchone()

    if row is None or row[1] < days or row[0] is None:
        return None

    return float(row[0])


def get_swing_high(conn: Any, symbol: str, days: int = 30) -> float | None:
    """Get the highest close price over the last N trading days.

    Args:
        conn: Database connection
        symbol: Stock ticker symbol
        days: Number of trading days to look back (default: 30)

    Returns:
        Highest close price over the period, or None if insufficient data

    Example:
        >>> from app.storage.connection import ConnectionManager
        >>> cm = ConnectionManager()
        >>> with cm.connection() as conn:
        ...     swing_high = get_swing_high(conn, "NVDA", days=30)
        >>> # Returns the highest close price in the last 30 trading days
    """
    query = """
        SELECT MAX(close) as swing_high, COUNT(*) as count
        FROM (
            SELECT close
            FROM day_bars
            WHERE ticker = %s
            ORDER BY date DESC
            LIMIT %s
        ) recent_bars
    """

    result = conn.execute(query, [symbol, days])
    row = result.fetchone()

    if row is None or row[1] < days or row[0] is None:
        return None

    return float(row[0])
