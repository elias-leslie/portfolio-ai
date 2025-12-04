"""Tests for trade calculation helpers (GAP-042)."""

from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from app.analytics.trade_calculations import (
    calculate_stop_loss,
    get_atr_for_symbol,
)


class TestGetAtrForSymbol:
    """Tests for ATR retrieval from multiple sources."""

    def test_atr_from_technical_indicators(self) -> None:
        """ATR found in technical_indicators table."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({"atr_14": [5.25]})

        atr = get_atr_for_symbol(storage, "AAPL")

        assert atr == 5.25
        storage.query.assert_called_once()

    def test_atr_calculated_on_fly(self) -> None:
        """ATR calculated from day_bars when not in technical_indicators."""
        storage = MagicMock()
        # First call returns empty (no technical_indicators data)
        storage.query.return_value = pl.DataFrame({"atr_14": []})

        with patch("app.analytics.trade_calculations.calculate_indicators") as mock_calc:
            mock_calc.return_value = {"atr_14": 4.50}
            atr = get_atr_for_symbol(storage, "AAPL")

        assert atr == 4.50
        mock_calc.assert_called_once()

    def test_atr_unavailable_returns_none(self) -> None:
        """Returns None when ATR unavailable from all sources."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({"atr_14": []})

        with patch("app.analytics.trade_calculations.calculate_indicators") as mock_calc:
            mock_calc.return_value = {}  # No ATR in result
            atr = get_atr_for_symbol(storage, "NEWSTOCK")

        assert atr is None


class TestCalculateStopLoss:
    """Tests for stop-loss calculation (GAP-042: proper ATR stops)."""

    def test_stop_loss_uses_2x_atr(self) -> None:
        """Stop loss is entry - 2*ATR."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({"atr_14": [5.0]})

        stop_loss = calculate_stop_loss(storage, "AAPL", entry_price=100.0)

        # 100 - 2*5 = 90
        assert stop_loss == 90.0

    def test_stop_loss_never_negative(self) -> None:
        """Stop loss should never be negative (floor at 0.01)."""
        storage = MagicMock()
        # Huge ATR relative to price
        storage.query.return_value = pl.DataFrame({"atr_14": [100.0]})

        stop_loss = calculate_stop_loss(storage, "LOWPRICE", entry_price=10.0)

        # 10 - 2*100 = -190, but floored to 0.01
        assert stop_loss == 0.01

    def test_stop_loss_returns_none_when_no_atr(self) -> None:
        """Returns None when ATR unavailable - blocks trade (GAP-042)."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({"atr_14": []})

        with patch("app.analytics.trade_calculations.calculate_indicators") as mock_calc:
            mock_calc.return_value = {}
            stop_loss = calculate_stop_loss(storage, "NEWSTOCK", entry_price=50.0)

        # Should NOT fall back to 5% - returns None to block trade
        assert stop_loss is None

    def test_stop_loss_realistic_example(self) -> None:
        """Realistic ATR-based stop loss calculation."""
        storage = MagicMock()
        # AAPL at $200 with ATR of $4
        storage.query.return_value = pl.DataFrame({"atr_14": [4.0]})

        stop_loss = calculate_stop_loss(storage, "AAPL", entry_price=200.0)

        # 200 - 2*4 = 192, which is 4% from entry (not flat 5%)
        assert stop_loss == 192.0
        assert (200.0 - stop_loss) / 200.0 == pytest.approx(0.04, abs=0.001)

    def test_stop_loss_volatile_stock(self) -> None:
        """High volatility stock gets wider stop."""
        storage = MagicMock()
        # Biotech with high ATR of $15 on $100 stock
        storage.query.return_value = pl.DataFrame({"atr_14": [15.0]})

        stop_loss = calculate_stop_loss(storage, "BIOTECH", entry_price=100.0)

        # 100 - 2*15 = 70, which is 30% from entry
        assert stop_loss == 70.0
        # Much wider than flat 5% - appropriate for volatile stock
        assert (100.0 - stop_loss) / 100.0 == 0.30

    def test_stop_loss_low_volatility_stock(self) -> None:
        """Low volatility stock gets tighter stop."""
        storage = MagicMock()
        # Utility with low ATR of $0.50 on $50 stock
        storage.query.return_value = pl.DataFrame({"atr_14": [0.50]})

        stop_loss = calculate_stop_loss(storage, "UTILITY", entry_price=50.0)

        # 50 - 2*0.5 = 49, which is 2% from entry
        assert stop_loss == 49.0
        # Much tighter than flat 5% - appropriate for stable utility
        assert (50.0 - stop_loss) / 50.0 == 0.02
