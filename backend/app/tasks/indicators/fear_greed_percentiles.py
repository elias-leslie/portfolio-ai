"""Percentile calculation functions for Fear & Greed Index components.

Each function queries a rolling window of historical data and returns an integer
percentile (0-100) representing where the current value falls in the distribution.
"""

from __future__ import annotations

from app.storage.types import DatabaseConnection


def _calculate_percentile_vix(
    conn: DatabaseConnection, as_of_date: str, vix_close: float, window: int
) -> int:
    """Calculate VIX percentile (inverted: lower VIX = higher score)."""
    result = conn.execute(
        """
        WITH recent_data AS (
            SELECT vix_close
            FROM fear_greed_inputs
            WHERE as_of_date <= %s AND vix_close IS NOT NULL
            ORDER BY as_of_date DESC
            LIMIT %s
        )
        SELECT
            COUNT(*) FILTER (WHERE vix_close >= %s) * 100.0 / COUNT(*) as vix_pct
        FROM recent_data
        """,
        (as_of_date, window, vix_close),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50


def _calculate_percentile_momentum(
    conn: DatabaseConnection, as_of_date: str, spy_close: float, spy_sma_200: float, window: int
) -> int:
    """Calculate momentum percentile (SPY vs SMA_200)."""
    momentum = ((spy_close / spy_sma_200) - 1) * 100 if spy_sma_200 else 0
    result = conn.execute(
        """
        WITH recent_data AS (
            SELECT ((spy_close / spy_sma_200) - 1) * 100 as momentum
            FROM fear_greed_inputs
            WHERE as_of_date <= %s AND spy_close IS NOT NULL AND spy_sma_200 IS NOT NULL
            ORDER BY as_of_date DESC
            LIMIT %s
        )
        SELECT
            COUNT(*) FILTER (WHERE momentum <= %s) * 100.0 / COUNT(*) as momentum_pct
        FROM recent_data
        """,
        (as_of_date, window, momentum),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50


def _calculate_percentile_rsi(
    conn: DatabaseConnection, as_of_date: str, rsi_14: float, window: int
) -> int:
    """Calculate RSI percentile."""
    result = conn.execute(
        """
        WITH recent_data AS (
            SELECT rsi_14
            FROM fear_greed_inputs
            WHERE as_of_date <= %s AND rsi_14 IS NOT NULL
            ORDER BY as_of_date DESC
            LIMIT %s
        )
        SELECT
            COUNT(*) FILTER (WHERE rsi_14 <= %s) * 100.0 / COUNT(*) as rsi_pct
        FROM recent_data
        """,
        (as_of_date, window, rsi_14),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50


def _calculate_percentile_credit(
    conn: DatabaseConnection, as_of_date: str, hy_spread: float, window: int
) -> int:
    """Calculate credit spread percentile (inverted: lower spread = higher score)."""
    result = conn.execute(
        """
        WITH recent_data AS (
            SELECT hy_spread
            FROM fear_greed_inputs
            WHERE as_of_date <= %s AND hy_spread IS NOT NULL
            ORDER BY as_of_date DESC
            LIMIT %s
        )
        SELECT
            COUNT(*) FILTER (WHERE hy_spread >= %s) * 100.0 / COUNT(*) as credit_pct
        FROM recent_data
        """,
        (as_of_date, window, hy_spread),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50


def _calculate_percentile_breadth(
    conn: DatabaseConnection, as_of_date: str, breadth_pct: float | None, window: int
) -> int:
    """Calculate market breadth percentile."""
    if breadth_pct is None:
        return 50  # Default neutral if breadth_pct is None

    result = conn.execute(
        """
        WITH recent_data AS (
            SELECT breadth_pct
            FROM fear_greed_inputs
            WHERE as_of_date <= %s AND breadth_pct IS NOT NULL
            ORDER BY as_of_date DESC
            LIMIT %s
        )
        SELECT
            COUNT(*) FILTER (WHERE breadth_pct <= %s) * 100.0 / COUNT(*) as breadth_percentile
        FROM recent_data
        """,
        (as_of_date, window, breadth_pct),
    )
    row = result.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    return 50
