"""Tests for watchlist calculator module (entry/exit/stop calculation + position sizing)."""

from __future__ import annotations

from datetime import date, timedelta

from app.storage.connection import ConnectionManager
from app.watchlist.calculator import (
    calculate_entry_price,
    calculate_position_size,
    calculate_profit_target,
    calculate_stop_loss,
    get_swing_high,
    get_swing_low,
)


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
                INSERT INTO day_bars (symbol, date, open, high, low, close, volume, source)
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
                INSERT INTO day_bars (symbol, date, open, high, low, close, volume, source)
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
                INSERT INTO day_bars (symbol, date, open, high, low, close, volume, source)
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
                INSERT INTO day_bars (symbol, date, open, high, low, close, volume, source)
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


class TestCalculateEntryPrice:
    """Test entry price calculation."""

    def test_entry_price_for_buy_signal_uses_current_price(self) -> None:
        """Test that BUY signal uses current price as entry."""
        # For BUY signals, entry is simply the current price
        entry = calculate_entry_price(current_price=202.0, signal_type="BUY")
        assert entry == 202.0

    def test_entry_price_for_hold_signal_uses_current_price(self) -> None:
        """Test that HOLD signal uses current price as conditional entry."""
        entry = calculate_entry_price(current_price=150.5, signal_type="HOLD")
        assert entry == 150.5

    def test_entry_price_for_avoid_signal_returns_none(self) -> None:
        """Test that AVOID signal returns None (no entry recommended)."""
        entry = calculate_entry_price(current_price=100.0, signal_type="AVOID")
        assert entry is None


class TestCalculateStopLoss:
    """Test stop loss calculation (ATR-based and technical)."""

    def test_stop_loss_atr_based(self) -> None:
        """Test ATR-based stop loss: entry - (2 x ATR)."""
        cm = ConnectionManager()
        with cm.connection() as conn:
            # Setup: Create technical indicators with ATR
            symbol = "NVDA"
            today = date.today()

            conn.execute(
                """
                INSERT INTO technical_indicators (
                    symbol, date, atr_14, ema_20, rsi_14, macd, macd_signal, calculated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (symbol, today, 7.0, 200.0, 55.0, 2.5, 1.5),
            )

            # Entry $202, ATR $7 → Stop should be $202 - (2 x $7) = $188
            stop = calculate_stop_loss(conn, symbol, entry_price=202.0)
            assert stop == 188.0

    def test_stop_loss_uses_tighter_of_atr_or_swing_low(self) -> None:
        """Test that stop uses tighter (higher) of ATR-based or swing low."""
        cm = ConnectionManager()
        with cm.connection() as conn:
            symbol = "AAPL"
            today = date.today()

            # ATR-based stop: 150 - (2 x 3) = 144
            conn.execute(
                """
                INSERT INTO technical_indicators (
                    symbol, date, atr_14, ema_20, rsi_14, macd, macd_signal, calculated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (symbol, today, 3.0, 145.0, 50.0, 1.0, 0.5),
            )

            # Swing low at 146 (higher/tighter than ATR stop of 144)
            for i in range(10):
                price_date = today - timedelta(days=i)
                close_price = 146.0 if i == 5 else 148.0 + i
                conn.execute(
                    """
                    INSERT INTO day_bars (symbol, date, open, high, low, close, volume, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        symbol,
                        price_date,
                        close_price,
                        close_price + 1,
                        close_price - 1,
                        close_price,
                        100000,
                        "test",
                    ),
                )

            # Should use swing low (146) as it's tighter
            stop = calculate_stop_loss(conn, symbol, entry_price=150.0)
            assert stop == 146.0


class TestCalculateProfitTarget:
    """Test profit target calculation (ATR-based and swing high)."""

    def test_profit_target_atr_based(self) -> None:
        """Test ATR-based profit target: entry + (2 x ATR)."""
        cm = ConnectionManager()
        with cm.connection() as conn:
            symbol = "META"
            today = date.today()

            conn.execute(
                """
                INSERT INTO technical_indicators (
                    symbol, date, atr_14, ema_20, rsi_14, macd, macd_signal, calculated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (symbol, today, 8.0, 300.0, 60.0, 3.0, 2.0),
            )

            # Entry $300, ATR $8 → Target should be $300 + (2 x $8) = $316
            target = calculate_profit_target(conn, symbol, entry_price=300.0)
            assert target == 316.0

    def test_profit_target_uses_higher_of_atr_or_swing_high(self) -> None:
        """Test that target uses higher of ATR-based or swing high."""
        cm = ConnectionManager()
        with cm.connection() as conn:
            symbol = "GOOGL"
            today = date.today()

            # ATR-based target: 160 + (2 x 4) = 168
            conn.execute(
                """
                INSERT INTO technical_indicators (
                    symbol, date, atr_14, ema_20, rsi_14, macd, macd_signal, calculated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (symbol, today, 4.0, 155.0, 52.0, 1.5, 1.0),
            )

            # Swing high at 170 (higher than ATR target of 168)
            for i in range(30):
                price_date = today - timedelta(days=i)
                close_price = 170.0 if i == 15 else 158.0 + (i % 10)
                conn.execute(
                    """
                    INSERT INTO day_bars (symbol, date, open, high, low, close, volume, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        symbol,
                        price_date,
                        close_price,
                        close_price + 1,
                        close_price - 1,
                        close_price,
                        100000,
                        "test",
                    ),
                )

            # Should use swing high (170) as it's higher
            target = calculate_profit_target(conn, symbol, entry_price=160.0)
            assert target == 170.0


class TestCalculatePositionSize:
    """Test position sizing based on risk budget."""

    def test_position_size_calculation(self) -> None:
        """Test position sizing formula: shares = floor(risk_budget / (entry - stop))."""
        # Entry $202, Stop $195, Risk $500
        # Risk per share = $202 - $195 = $7
        # Shares = floor($500 / $7) = 71 shares
        shares = calculate_position_size(entry_price=202.0, stop_loss=195.0, risk_budget=500.0)
        assert shares == 71

    def test_position_size_with_different_risk_budget(self) -> None:
        """Test position sizing with larger risk budget."""
        # Entry $100, Stop $95, Risk $1000
        # Risk per share = $5
        # Shares = floor($1000 / $5) = 200 shares
        shares = calculate_position_size(entry_price=100.0, stop_loss=95.0, risk_budget=1000.0)
        assert shares == 200

    def test_position_size_handles_invalid_setup_entry_below_stop(self) -> None:
        """Test that invalid setup (entry <= stop) returns None."""
        # Entry $100, Stop $105 (invalid: stop above entry)
        shares = calculate_position_size(entry_price=100.0, stop_loss=105.0, risk_budget=500.0)
        assert shares is None

    def test_position_size_handles_zero_shares_expensive_stock(self) -> None:
        """Test that expensive stock with tight stop returns 0 shares."""
        # Entry $1000, Stop $998, Risk $10
        # Risk per share = $2, Shares = floor($10 / $2) = 5
        shares = calculate_position_size(entry_price=1000.0, stop_loss=998.0, risk_budget=10.0)
        assert shares == 5

        # But if risk is too small, returns 0
        shares_small = calculate_position_size(entry_price=1000.0, stop_loss=999.0, risk_budget=0.5)
        assert shares_small == 0
