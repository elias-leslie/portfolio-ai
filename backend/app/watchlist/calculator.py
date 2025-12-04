"""Watchlist calculator module for entry/exit/stop calculation and position sizing.

This module provides functions for:
- Swing low/high detection (support/resistance levels)
- Entry price calculation
- Stop loss calculation (ATR-based and technical)
- Profit target calculation
- Position sizing based on risk budget
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.storage.types import DatabaseConnection

if TYPE_CHECKING:
    pass


def get_swing_low(conn: DatabaseConnection, symbol: str, days: int = 10) -> float | None:
    """Get the lowest close price over the last N trading days.

    Args:
        conn: Database connection
        symbol: Stock symbol
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
            WHERE symbol = %s
            ORDER BY date DESC
            LIMIT %s
        ) recent_bars
    """

    result = conn.execute(query, [symbol, days])
    row = result.fetchone()

    if row is None or row[0] is None:
        return None

    # Type guard for row[1] (count of rows)
    count = row[1] if isinstance(row[1], int) else 0
    if count < days:
        return None

    return float(row[0])


def get_swing_high(conn: DatabaseConnection, symbol: str, days: int = 30) -> float | None:
    """Get the highest close price over the last N trading days.

    Args:
        conn: Database connection
        symbol: Stock symbol
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
            WHERE symbol = %s
            ORDER BY date DESC
            LIMIT %s
        ) recent_bars
    """

    result = conn.execute(query, [symbol, days])
    row = result.fetchone()

    if row is None or row[0] is None:
        return None

    # Type guard for row[1] (count of rows)
    count = row[1] if isinstance(row[1], int) else 0
    if count < days:
        return None

    return float(row[0])


def calculate_entry_price(current_price: float, signal_type: str) -> float | None:
    """Calculate entry price based on signal type.

    For BUY and HOLD signals, entry is the current price.
    For AVOID signals, no entry is recommended (returns None).

    Args:
        current_price: Current stock price
        signal_type: Signal type ("BUY", "HOLD", or "AVOID")

    Returns:
        Entry price or None if AVOID signal

    Example:
        >>> calculate_entry_price(202.0, "BUY")
        202.0
        >>> calculate_entry_price(100.0, "AVOID")
        None
    """
    if signal_type == "AVOID":
        return None
    return current_price


def calculate_stop_loss(conn: DatabaseConnection, symbol: str, entry_price: float) -> float | None:
    """Calculate stop loss using ATR-based and technical (swing low) methods.

    Uses the tighter (higher) of:
    1. ATR-based stop: entry - (2 x ATR_14)
    2. Technical stop: Recent swing low (10-day low)

    Args:
        conn: Database connection
        symbol: Stock symbol
        entry_price: Entry price for the trade

    Returns:
        Stop loss price or None if cannot calculate

    Example:
        >>> from app.storage.connection import ConnectionManager
        >>> cm = ConnectionManager()
        >>> with cm.connection() as conn:
        ...     stop = calculate_stop_loss(conn, "NVDA", entry_price=202.0)
        >>> # Returns tighter of ATR-based or swing low stop
    """
    # Get ATR from technical indicators
    atr_query = """
        SELECT atr_14
        FROM technical_indicators
        WHERE symbol = %s
        ORDER BY date DESC
        LIMIT 1
    """
    result = conn.execute(atr_query, [symbol])
    row = result.fetchone()

    if row is None or row[0] is None:
        return None

    atr = float(row[0])

    # Calculate ATR-based stop: entry - (2 x ATR)
    atr_stop = entry_price - (2 * atr)

    # Get technical stop (swing low)
    swing_low = get_swing_low(conn, symbol, days=10)

    # Use tighter (higher) stop
    if swing_low is not None:
        return max(atr_stop, swing_low)

    return atr_stop


def calculate_profit_target(
    conn: DatabaseConnection, symbol: str, entry_price: float
) -> float | None:
    """Calculate profit target using ATR-based and technical (swing high) methods.

    Uses the higher of:
    1. ATR-based target: entry + (2 x ATR_14)
    2. Technical target: Recent swing high (30-day high)

    Args:
        conn: Database connection
        symbol: Stock symbol
        entry_price: Entry price for the trade

    Returns:
        Profit target price or None if cannot calculate

    Example:
        >>> from app.storage.connection import ConnectionManager
        >>> cm = ConnectionManager()
        >>> with cm.connection() as conn:
        ...     target = calculate_profit_target(conn, "NVDA", entry_price=202.0)
        >>> # Returns higher of ATR-based or swing high target
    """
    # Get ATR from technical indicators
    atr_query = """
        SELECT atr_14
        FROM technical_indicators
        WHERE symbol = %s
        ORDER BY date DESC
        LIMIT 1
    """
    result = conn.execute(atr_query, [symbol])
    row = result.fetchone()

    if row is None or row[0] is None:
        return None

    atr = float(row[0])

    # Calculate ATR-based target: entry + (2 x ATR)
    atr_target = entry_price + (2 * atr)

    # Get technical target (swing high)
    swing_high = get_swing_high(conn, symbol, days=30)

    # Use higher target
    if swing_high is not None:
        return max(atr_target, swing_high)

    return atr_target


def calculate_position_size(entry_price: float, stop_loss: float, risk_budget: float) -> int | None:
    """Calculate position size (number of shares) based on risk budget.

    Formula: shares = floor(risk_budget / (entry_price - stop_loss))

    Args:
        entry_price: Entry price for the trade
        stop_loss: Stop loss price
        risk_budget: Maximum amount willing to risk (e.g., $500)

    Returns:
        Number of shares to buy, or None if invalid setup (entry <= stop)

    Example:
        >>> calculate_position_size(entry_price=202.0, stop_loss=195.0, risk_budget=500.0)
        71  # floor(500 / (202 - 195)) = floor(500 / 7) = 71 shares
    """
    # Invalid setup: stop should be below entry
    # Also handle None values gracefully
    if stop_loss is None or entry_price <= stop_loss:
        return None

    # Calculate risk per share
    risk_per_share = entry_price - stop_loss

    # Calculate shares
    shares = int(risk_budget / risk_per_share)

    return shares
