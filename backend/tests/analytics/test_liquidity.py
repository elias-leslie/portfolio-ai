"""Tests for liquidity checks (GAP-044)."""

from unittest.mock import MagicMock

import polars as pl
import pytest

from app.analytics.liquidity import (
    apply_liquidity_cap,
    calculate_adv,
    check_position_liquidity,
    get_max_position_shares,
)


class TestCalculateAdv:
    """Tests for Average Daily Volume calculation."""

    def test_adv_calculation(self) -> None:
        """Calculate ADV from 20-day average."""
        storage = MagicMock()
        # Simulate 20 days of volume data averaging 1M shares
        storage.query.return_value = pl.DataFrame(
            {
                "adv": [1_000_000.0],
                "days_count": [20],
            }
        )

        adv = calculate_adv(storage, "AAPL")

        assert adv == 1_000_000.0

    def test_adv_insufficient_data(self) -> None:
        """Returns None when insufficient volume days."""
        storage = MagicMock()
        # Only 10 days of data (need 20)
        storage.query.return_value = pl.DataFrame(
            {
                "adv": [500_000.0],
                "days_count": [10],
            }
        )

        adv = calculate_adv(storage, "NEWSTOCK")

        assert adv is None

    def test_adv_no_data(self) -> None:
        """Returns None when no data."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame()

        adv = calculate_adv(storage, "UNKNOWN")

        assert adv is None


class TestGetMaxPositionShares:
    """Tests for maximum position calculation."""

    def test_max_position_is_1_percent_adv(self) -> None:
        """Max position is 1% of ADV."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame(
            {
                "adv": [10_000_000.0],  # 10M shares/day ADV
                "days_count": [20],
            }
        )

        max_shares, adv = get_max_position_shares(storage, "AAPL", entry_price=150.0)

        # 1% of 10M = 100,000 shares
        assert max_shares == 100_000
        assert adv == 10_000_000.0

    def test_max_position_illiquid_stock(self) -> None:
        """Small ADV means small max position."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame(
            {
                "adv": [50_000.0],  # 50K shares/day ADV (illiquid)
                "days_count": [20],
            }
        )

        max_shares, _adv = get_max_position_shares(storage, "SMALLCAP", entry_price=25.0)

        # 1% of 50K = 500 shares
        assert max_shares == 500

    def test_max_position_no_adv(self) -> None:
        """Returns 0 max shares when no ADV available."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame()

        max_shares, adv = get_max_position_shares(storage, "UNKNOWN", entry_price=100.0)

        assert max_shares == 0
        assert adv is None


class TestCheckPositionLiquidity:
    """Tests for position liquidity checks."""

    def test_position_within_limit(self) -> None:
        """Position within 1% ADV passes check."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame(
            {
                "adv": [1_000_000.0],
                "days_count": [20],
            }
        )

        # 5,000 shares = 0.5% of 1M ADV
        is_ok, message, details = check_position_liquidity(
            storage, "AAPL", proposed_shares=5_000, entry_price=150.0
        )

        assert is_ok is True
        assert "OK" in message
        assert details["position_percent_adv"] == pytest.approx(0.5, abs=0.01)

    def test_position_exceeds_limit(self) -> None:
        """Position > 1% ADV fails check."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame(
            {
                "adv": [100_000.0],  # 100K ADV
                "days_count": [20],
            }
        )

        # 5,000 shares = 5% of 100K ADV (exceeds 1%)
        is_ok, message, details = check_position_liquidity(
            storage, "SMALLCAP", proposed_shares=5_000, entry_price=50.0
        )

        assert is_ok is False
        assert "too large" in message.lower()
        assert details["position_percent_adv"] == pytest.approx(5.0, abs=0.01)

    def test_no_adv_data(self) -> None:
        """No ADV data fails check."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame()

        is_ok, message, _details = check_position_liquidity(
            storage, "UNKNOWN", proposed_shares=100, entry_price=25.0
        )

        assert is_ok is False
        assert "data" in message.lower()


class TestApplyLiquidityCap:
    """Tests for liquidity cap application."""

    def test_position_not_reduced_when_within_limit(self) -> None:
        """Position unchanged when within liquidity limit."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame(
            {
                "adv": [1_000_000.0],
                "days_count": [20],
            }
        )

        final_shares, message = apply_liquidity_cap(
            storage, "AAPL", desired_shares=5_000, entry_price=150.0
        )

        assert final_shares == 5_000
        assert "within" in message.lower()

    def test_position_reduced_to_max_allowed(self) -> None:
        """Position reduced to 1% ADV when exceeds limit."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame(
            {
                "adv": [100_000.0],  # 100K ADV
                "days_count": [20],
            }
        )

        # Want 5,000 but max is 1,000 (1% of 100K)
        final_shares, message = apply_liquidity_cap(
            storage, "SMALLCAP", desired_shares=5_000, entry_price=50.0
        )

        assert final_shares == 1_000
        assert "reduced" in message.lower()
        assert "5,000" in message  # Original
        assert "1,000" in message  # Reduced to

    def test_trade_blocked_when_no_adv(self) -> None:
        """Trade blocked (0 shares) when no ADV data."""
        storage = MagicMock()
        storage.query.return_value = pl.DataFrame()

        final_shares, message = apply_liquidity_cap(
            storage, "UNKNOWN", desired_shares=1_000, entry_price=25.0
        )

        assert final_shares == 0
        assert "blocked" in message.lower()
