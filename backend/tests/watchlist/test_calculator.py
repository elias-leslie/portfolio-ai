"""Tests for watchlist calculator module (entry/exit/stop calculation + position sizing)."""

from __future__ import annotations

from datetime import date, timedelta

from app.storage.connection import ConnectionManager
from app.watchlist.calculator import get_swing_high, get_swing_low


def test_get_swing_low_returns_lowest_close_in_10_days() -> None:
    """Test that swing_low returns the lowest close price over 10 trading days."""
    cm = ConnectionManager()

    with cm.connection() as conn:
        # Setup: Insert 15 days of data with known lowest point
        symbol = "NVDA"
        today = date.today()

        # Create price data with lowest close in last 10 records (192.0 at day 5)
        prices = [
            (today - timedelta(days=14), 220.0),  # 14 days ago
            (today - timedelta(days=13), 218.0),  # 13 days ago
            (today - timedelta(days=12), 216.0),  # 12 days ago
            (today - timedelta(days=11), 214.0),  # 11 days ago
            (today - timedelta(days=10), 212.0),  # 10 days ago
            (today - timedelta(days=9), 210.0),  # 9 days ago
            (today - timedelta(days=8), 208.0),  # 8 days ago
            (today - timedelta(days=7), 206.0),  # 7 days ago
            (today - timedelta(days=6), 204.0),  # 6 days ago
            (today - timedelta(days=5), 192.0),  # 5 days ago ← Lowest in last 10 days
            (today - timedelta(days=4), 194.0),  # 4 days ago
            (today - timedelta(days=3), 196.0),  # 3 days ago
            (today - timedelta(days=2), 198.0),  # 2 days ago
            (today - timedelta(days=1), 200.0),  # Yesterday
            (today, 202.0),  # Today
        ]

        for price_date, close_price in prices:
            conn.execute(
                """
                INSERT INTO day_bars (ticker, date, open, high, low, close, volume, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    symbol,
                    price_date,
                    close_price,
                    close_price + 2,
                    close_price - 2,
                    close_price,
                    1000000,
                    "test",
                ),
            )

        # Execute
        result = get_swing_low(conn, symbol, days=10)

        # Verify: Should return 192.0 (lowest close in last 10 days)
        assert result == 192.0


def test_get_swing_low_returns_none_for_insufficient_data() -> None:
    """Test that swing_low returns None when less than 10 days of data available."""
    cm = ConnectionManager()

    with cm.connection() as conn:
        symbol = "TSLA"
        today = date.today()

        # Insert only 5 days of data
        for i in range(5):
            price_date = today - timedelta(days=i)
            conn.execute(
                """
                INSERT INTO day_bars (ticker, date, open, high, low, close, volume, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (symbol, price_date, 200.0, 202.0, 198.0, 200.0, 1000000, "test"),
            )

        # Execute
        result = get_swing_low(conn, symbol, days=10)

        # Verify: Should return None (insufficient data)
        assert result is None


def test_get_swing_high_returns_highest_close_in_30_days() -> None:
    """Test that swing_high returns the highest close price over 30 trading days."""
    cm = ConnectionManager()

    with cm.connection() as conn:
        symbol = "AAPL"
        today = date.today()

        # Create 35 days of data with highest close on day 15 (30 days ago)
        prices = []
        for i in range(35, 0, -1):
            price_date = today - timedelta(days=i)
            if i == 15:
                # Highest close 15 days ago (within 30-day window)
                close_price = 250.0
            else:
                # Other prices lower
                close_price = 220.0 + (i % 20)
            prices.append((price_date, close_price))

        for price_date, close_price in prices:
            conn.execute(
                """
                INSERT INTO day_bars (ticker, date, open, high, low, close, volume, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    symbol,
                    price_date,
                    close_price,
                    close_price + 2,
                    close_price - 2,
                    close_price,
                    1000000,
                    "test",
                ),
            )

        # Execute
        result = get_swing_high(conn, symbol, days=30)

        # Verify: Should return 250.0 (highest close in last 30 days)
        assert result == 250.0


def test_get_swing_high_returns_none_for_insufficient_data() -> None:
    """Test that swing_high returns None when less than 30 days of data available."""
    cm = ConnectionManager()

    with cm.connection() as conn:
        symbol = "GOOGL"
        today = date.today()

        # Insert only 20 days of data
        for i in range(20):
            price_date = today - timedelta(days=i)
            conn.execute(
                """
                INSERT INTO day_bars (ticker, date, open, high, low, close, volume, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (symbol, price_date, 150.0, 152.0, 148.0, 150.0, 1000000, "test"),
            )

        # Execute
        result = get_swing_high(conn, symbol, days=30)

        # Verify: Should return None (insufficient data)
        assert result is None


def test_get_swing_low_with_no_data_returns_none() -> None:
    """Test that swing_low returns None when no data exists for symbol."""
    cm = ConnectionManager()

    with cm.connection() as conn:
        # Execute with symbol that has no data
        result = get_swing_low(conn, "NONEXISTENT", days=10)

        # Verify
        assert result is None


def test_get_swing_high_with_no_data_returns_none() -> None:
    """Test that swing_high returns None when no data exists for symbol."""
    cm = ConnectionManager()

    with cm.connection() as conn:
        # Execute with symbol that has no data
        result = get_swing_high(conn, "NONEXISTENT", days=30)

        # Verify
        assert result is None
