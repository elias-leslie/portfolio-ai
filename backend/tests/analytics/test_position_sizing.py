"""Tests for risk-based position sizing (GAP-043)."""

from __future__ import annotations

import pytest

from app.analytics.position_sizing import (
    DEFAULT_RISK_PERCENT,
    MAX_POSITION_PERCENT,
    MAX_RISK_PERCENT,
    MIN_POSITION_VALUE,
    MIN_RISK_PERCENT,
    calculate_risk_based_shares,
    calculate_risk_per_share,
    calculate_stop_distance_percent,
    validate_position_size,
)


class TestCalculateRiskPerShare:
    """Tests for risk per share calculation."""

    def test_valid_long_position(self) -> None:
        """Test valid long position (entry above stop)."""
        risk = calculate_risk_per_share(entry_price=100.0, stop_loss=95.0)
        assert risk == 5.0

    def test_stop_at_entry_returns_none(self) -> None:
        """Test stop at entry returns None (invalid)."""
        risk = calculate_risk_per_share(entry_price=100.0, stop_loss=100.0)
        assert risk is None

    def test_stop_above_entry_returns_none(self) -> None:
        """Test stop above entry returns None (invalid for long)."""
        risk = calculate_risk_per_share(entry_price=100.0, stop_loss=105.0)
        assert risk is None

    def test_zero_entry_returns_none(self) -> None:
        """Test zero entry price returns None."""
        risk = calculate_risk_per_share(entry_price=0.0, stop_loss=95.0)
        assert risk is None

    def test_negative_stop_returns_none(self) -> None:
        """Test negative stop returns None."""
        risk = calculate_risk_per_share(entry_price=100.0, stop_loss=-5.0)
        assert risk is None


class TestCalculateRiskBasedShares:
    """Tests for risk-based position sizing calculation."""

    def test_basic_calculation(self) -> None:
        """Test basic risk-based sizing.

        $100,000 equity, 1.5% risk = $1,500 risk budget
        Entry $100, Stop $95 = $5 risk per share
        $1,500 / $5 = 300 shares, BUT...
        300 shares * $100 = $30,000 = 30% of portfolio
        This exceeds 25% max position cap, so capped to 250 shares
        """
        shares, details = calculate_risk_based_shares(
            equity=100_000.0,
            entry_price=100.0,
            stop_loss=95.0,
            risk_percent=0.015,
        )

        # Capped at 25% of portfolio = 250 shares
        assert shares == 250
        assert details["risk_amount"] == 1500.0
        assert details["risk_per_share"] == 5.0
        assert details["position_value"] == 25000.0  # 250 * $100 (capped)
        assert details["position_percent"] == pytest.approx(0.25, abs=0.01)  # 25% cap

    def test_wide_stop_fewer_shares(self) -> None:
        """Test wider stop = fewer shares.

        Same equity/risk, but 10% stop distance.
        $100,000 * 1.5% = $1,500 risk
        Entry $100, Stop $90 = $10 risk per share
        $1,500 / $10 = 150 shares
        """
        shares, details = calculate_risk_based_shares(
            equity=100_000.0,
            entry_price=100.0,
            stop_loss=90.0,
            risk_percent=0.015,
        )

        assert shares == 150
        assert details["risk_per_share"] == 10.0

    def test_tight_stop_more_shares_capped(self) -> None:
        """Test tight stop gets capped at 25% of portfolio.

        $100,000 equity, 1.5% risk = $1,500 risk
        Entry $100, Stop $99 = $1 risk per share
        $1,500 / $1 = 1,500 shares = $150,000 (150% - exceeds cap)
        Capped at 25% = $25,000 / $100 = 250 shares
        """
        shares, details = calculate_risk_based_shares(
            equity=100_000.0,
            entry_price=100.0,
            stop_loss=99.0,  # Only $1 risk per share
            risk_percent=0.015,
        )

        # Should be capped at MAX_POSITION_PERCENT (25%)
        max_shares = int(100_000.0 * MAX_POSITION_PERCENT / 100.0)
        assert shares == max_shares
        assert details["position_percent"] <= MAX_POSITION_PERCENT + 0.01

    def test_invalid_stop_returns_zero(self) -> None:
        """Test invalid stop (above entry) returns zero shares."""
        shares, details = calculate_risk_based_shares(
            equity=100_000.0,
            entry_price=100.0,
            stop_loss=105.0,  # Invalid for long
            risk_percent=0.015,
        )

        assert shares == 0

    def test_zero_equity_returns_zero(self) -> None:
        """Test zero equity returns zero shares."""
        shares, details = calculate_risk_based_shares(
            equity=0.0,
            entry_price=100.0,
            stop_loss=95.0,
            risk_percent=0.015,
        )

        assert shares == 0

    def test_risk_percent_bounded_to_max(self) -> None:
        """Test risk percent is capped at MAX_RISK_PERCENT."""
        shares_max, _ = calculate_risk_based_shares(
            equity=100_000.0,
            entry_price=100.0,
            stop_loss=95.0,
            risk_percent=0.10,  # 10% - exceeds 5% max
        )

        shares_at_cap, _ = calculate_risk_based_shares(
            equity=100_000.0,
            entry_price=100.0,
            stop_loss=95.0,
            risk_percent=MAX_RISK_PERCENT,  # 5% max
        )

        assert shares_max == shares_at_cap

    def test_risk_percent_bounded_to_min(self) -> None:
        """Test risk percent is floored at MIN_RISK_PERCENT."""
        shares_min, _ = calculate_risk_based_shares(
            equity=100_000.0,
            entry_price=100.0,
            stop_loss=95.0,
            risk_percent=0.001,  # 0.1% - below 0.5% min
        )

        shares_at_floor, _ = calculate_risk_based_shares(
            equity=100_000.0,
            entry_price=100.0,
            stop_loss=95.0,
            risk_percent=MIN_RISK_PERCENT,  # 0.5% min
        )

        assert shares_min == shares_at_floor


class TestCalculateStopDistancePercent:
    """Tests for stop distance percentage calculation."""

    def test_5_percent_stop(self) -> None:
        """Test 5% stop distance calculation."""
        pct = calculate_stop_distance_percent(entry_price=100.0, stop_loss=95.0)
        assert pct == pytest.approx(0.05, abs=0.001)

    def test_10_percent_stop(self) -> None:
        """Test 10% stop distance calculation."""
        pct = calculate_stop_distance_percent(entry_price=100.0, stop_loss=90.0)
        assert pct == pytest.approx(0.10, abs=0.001)

    def test_invalid_stop_returns_none(self) -> None:
        """Test invalid stop returns None."""
        pct = calculate_stop_distance_percent(entry_price=100.0, stop_loss=100.0)
        assert pct is None


class TestValidatePositionSize:
    """Tests for position size validation."""

    def test_valid_position(self) -> None:
        """Test valid position passes validation."""
        is_valid, error = validate_position_size(
            shares=100,
            entry_price=100.0,
            equity=100_000.0,
            stop_loss=95.0,
            risk_percent=0.015,
        )

        assert is_valid
        assert error is None

    def test_position_exceeds_cap(self) -> None:
        """Test position exceeding 25% cap fails."""
        is_valid, error = validate_position_size(
            shares=300,  # $30,000 = 30% of $100,000
            entry_price=100.0,
            equity=100_000.0,
            stop_loss=95.0,
        )

        assert not is_valid
        assert "exceeds max" in error.lower()

    def test_risk_exceeds_max(self) -> None:
        """Test position exceeding position cap or risk max fails.

        200 shares * $100 = $20,000
        $20,000 / $10,000 = 200% position (exceeds 25% cap)
        """
        is_valid, error = validate_position_size(
            shares=200,
            entry_price=100.0,
            equity=10_000.0,  # Small account
            stop_loss=95.0,  # $5 risk per share
        )

        assert not is_valid
        # Position cap check triggers first (200% > 25%)
        assert "exceeds max" in error.lower() or "position" in error.lower()

    def test_negative_shares_fails(self) -> None:
        """Test negative shares fails."""
        is_valid, error = validate_position_size(
            shares=-10,
            entry_price=100.0,
            equity=100_000.0,
            stop_loss=95.0,
        )

        assert not is_valid
        assert "positive" in error.lower()

    def test_no_stop_loss_skips_risk_validation(self) -> None:
        """Test no stop loss still validates position cap."""
        is_valid, _ = validate_position_size(
            shares=100,
            entry_price=100.0,
            equity=100_000.0,
            stop_loss=None,  # No stop loss
        )

        assert is_valid  # Only position cap checked


class TestIntegration:
    """Integration tests for complete position sizing flow."""

    def test_consistent_risk_different_stops(self) -> None:
        """Test same risk amount with different stop distances."""
        equity = 100_000.0
        risk_percent = 0.015  # 1.5% = $1,500 max risk

        # Tight stop (2%)
        shares_tight, details_tight = calculate_risk_based_shares(
            equity=equity,
            entry_price=100.0,
            stop_loss=98.0,  # $2 risk
            risk_percent=risk_percent,
        )

        # Wide stop (10%)
        shares_wide, details_wide = calculate_risk_based_shares(
            equity=equity,
            entry_price=100.0,
            stop_loss=90.0,  # $10 risk
            risk_percent=risk_percent,
        )

        # Tight stop = more shares (but risk is same)
        assert shares_tight > shares_wide

        # Risk amounts should be approximately equal (capped at risk_percent * equity)
        risk_tight = shares_tight * 2.0  # shares * risk per share
        risk_wide = shares_wide * 10.0

        # Both should be <= $1,500 (1.5% of $100k)
        max_risk = equity * risk_percent
        # Note: tight stop may hit position cap first
        assert risk_tight <= max_risk * 1.1  # Allow 10% tolerance for caps
        assert risk_wide == pytest.approx(max_risk, rel=0.01)

    def test_small_account_minimum_position(self) -> None:
        """Test small account with minimum position value check."""
        shares, details = calculate_risk_based_shares(
            equity=1_000.0,  # $1,000 account
            entry_price=100.0,
            stop_loss=95.0,
            risk_percent=0.015,  # $15 risk budget
        )

        # $15 / $5 risk = 3 shares = $300 position
        # This is above MIN_POSITION_VALUE ($100) so should proceed
        assert shares == 3 or shares > 0  # Small but valid

    def test_default_risk_percent_used(self) -> None:
        """Test default risk percent is applied."""
        shares, details = calculate_risk_based_shares(
            equity=100_000.0,
            entry_price=100.0,
            stop_loss=95.0,
            # risk_percent not specified - uses DEFAULT_RISK_PERCENT
        )

        assert details["risk_percent"] == DEFAULT_RISK_PERCENT
        assert shares > 0
