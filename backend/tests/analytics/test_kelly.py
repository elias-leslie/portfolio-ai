"""Tests for Kelly criterion position sizing (GAP-045)."""

from unittest.mock import MagicMock

import polars as pl
import pytest

from app.analytics.kelly import (
    DEFAULT_KELLY_FRACTION,
    MAX_POSITION_PERCENT,
    MIN_POSITION_PERCENT,
    MIN_TRADES_FOR_KELLY,
    calculate_kelly_fraction,
    calculate_kelly_position_size,
    get_strategy_stats,
)


class TestCalculateKellyFraction:
    """Tests for Kelly fraction calculation."""

    def test_good_edge_strategy(self) -> None:
        """Strategy with good edge gets reasonable Kelly."""
        # 60% win rate, 5% avg win, 3% avg loss
        kelly = calculate_kelly_fraction(
            win_rate=0.60,
            avg_win=0.05,
            avg_loss=-0.03,
            kelly_multiplier=1.0,  # Full Kelly for test
        )

        # Kelly = (0.6 * (5/3) - 0.4) / (5/3) = (1.0 - 0.4) / 1.667 = 0.36
        assert kelly == pytest.approx(0.25, abs=0.05)  # Capped at MAX_POSITION_PERCENT

    def test_fractional_kelly(self) -> None:
        """Fractional Kelly reduces position size."""
        full_kelly = calculate_kelly_fraction(
            win_rate=0.60,
            avg_win=0.05,
            avg_loss=-0.03,
            kelly_multiplier=1.0,
        )

        fractional_kelly = calculate_kelly_fraction(
            win_rate=0.60,
            avg_win=0.05,
            avg_loss=-0.03,
            kelly_multiplier=0.25,
        )

        assert fractional_kelly < full_kelly

    def test_no_edge_returns_minimum(self) -> None:
        """Strategy with no edge gets minimum position."""
        # 40% win rate, 4% avg win, 4% avg loss (no edge)
        kelly = calculate_kelly_fraction(
            win_rate=0.40,
            avg_win=0.04,
            avg_loss=-0.04,
            kelly_multiplier=1.0,
        )

        # Kelly = (0.4 * 1 - 0.6) / 1 = -0.2 (negative = no edge)
        assert kelly == MIN_POSITION_PERCENT

    def test_negative_edge_returns_minimum(self) -> None:
        """Strategy with negative edge gets minimum."""
        # 30% win rate, small wins, big losses
        kelly = calculate_kelly_fraction(
            win_rate=0.30,
            avg_win=0.03,
            avg_loss=-0.05,
        )

        assert kelly == MIN_POSITION_PERCENT

    def test_high_edge_capped(self) -> None:
        """Very high edge still capped at maximum."""
        # 80% win rate, 10% avg win, 2% avg loss (unrealistic but tests cap)
        kelly = calculate_kelly_fraction(
            win_rate=0.80,
            avg_win=0.10,
            avg_loss=-0.02,
            kelly_multiplier=1.0,
        )

        assert kelly == MAX_POSITION_PERCENT

    def test_invalid_inputs(self) -> None:
        """Invalid inputs return minimum position."""
        # Win rate out of bounds
        assert calculate_kelly_fraction(0.0, 0.05, -0.03) == MIN_POSITION_PERCENT
        assert calculate_kelly_fraction(1.0, 0.05, -0.03) == MIN_POSITION_PERCENT

        # Non-positive avg_win
        assert calculate_kelly_fraction(0.6, 0.0, -0.03) == MIN_POSITION_PERCENT
        assert calculate_kelly_fraction(0.6, -0.05, -0.03) == MIN_POSITION_PERCENT

        # Non-negative avg_loss
        assert calculate_kelly_fraction(0.6, 0.05, 0.0) == MIN_POSITION_PERCENT
        assert calculate_kelly_fraction(0.6, 0.05, 0.03) == MIN_POSITION_PERCENT


class TestGetStrategyStats:
    """Tests for strategy statistics retrieval."""

    def test_sufficient_trades(self) -> None:
        """Returns stats when sufficient trade history."""
        storage = MagicMock()
        # 30+ trades with mixed results
        pnl_values = [5.0, -3.0, 4.0, -2.0] * 10  # 40 trades
        storage.query.return_value = pl.DataFrame({"pnl_pct": pnl_values})

        win_rate, avg_win, avg_loss, count = get_strategy_stats(storage)

        assert count == 40
        assert win_rate == 0.5  # 20 wins, 20 losses
        assert avg_win == pytest.approx(0.045, abs=0.001)  # (5+4)/2 / 100
        assert avg_loss == pytest.approx(-0.025, abs=0.001)  # (-3-2)/2 / 100

    def test_insufficient_trades(self) -> None:
        """Returns None when insufficient trades."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({"pnl_pct": [5.0, -3.0]})

        win_rate, avg_win, avg_loss, count = get_strategy_stats(storage)

        assert win_rate is None
        assert avg_win is None
        assert avg_loss is None
        assert count == 2

    def test_no_trades(self) -> None:
        """Returns None when no trades."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame()

        win_rate, avg_win, avg_loss, count = get_strategy_stats(storage)

        assert count == 0


class TestCalculateKellyPositionSize:
    """Tests for Kelly position sizing."""

    def test_position_size_with_good_edge(self) -> None:
        """Calculates position size based on Kelly with good edge."""
        storage = MagicMock()
        # 60% win rate, 5% avg win, 3% avg loss
        pnl_values = [5.0] * 18 + [-3.0] * 12  # 60% win rate
        storage.query.return_value = pl.DataFrame({"pnl_pct": pnl_values})

        shares, details = calculate_kelly_position_size(
            storage,
            portfolio_value=100_000,
            entry_price=50.0,
        )

        assert shares > 0
        assert details["win_rate"] == 0.6
        assert details["kelly_fraction"] is not None
        assert details["position_value"] is not None

    def test_position_size_with_insufficient_data(self) -> None:
        """Uses minimum position when insufficient data."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame({"pnl_pct": [5.0, -3.0]})

        shares, details = calculate_kelly_position_size(
            storage,
            portfolio_value=100_000,
            entry_price=50.0,
        )

        # Minimum position = 1% of $100k = $1000, at $50/share = 20 shares
        assert shares == 20
        assert details["reason"] == "insufficient_data"
        assert details["kelly_fraction"] == MIN_POSITION_PERCENT

    def test_position_size_calculation(self) -> None:
        """Verify shares calculation is correct."""
        storage = MagicMock()
        # Set up for ~10% Kelly fraction
        pnl_values = [10.0] * 24 + [-5.0] * 16  # 60% win rate, 2:1 ratio
        storage.query.return_value = pl.DataFrame({"pnl_pct": pnl_values})

        shares, details = calculate_kelly_position_size(
            storage,
            portfolio_value=100_000,
            entry_price=100.0,
            kelly_multiplier=0.25,  # 25% of full Kelly
        )

        # Position value = portfolio * kelly_fraction
        # Shares = position_value / entry_price
        expected_shares = int(details["position_value"] / 100.0)
        assert shares == expected_shares
