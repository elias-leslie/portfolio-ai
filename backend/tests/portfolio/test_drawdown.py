"""Tests for portfolio drawdown tracking (GAP-023).

Tests cover:
- Drawdown calculation from peak
- Underwater days tracking
- Portfolio-level trading halt at -10%
- Historical drawdown retrieval
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.portfolio.drawdown import (
    DRAWDOWN_WARNING_LEVEL_1,
    DRAWDOWN_WARNING_LEVEL_2,
    PORTFOLIO_DRAWDOWN_HALT_PCT,
    DrawdownMetrics,
    calculate_drawdown,
    calculate_drawdown_metrics,
    calculate_position_drawdown,
    check_portfolio_drawdown_halt,
    get_recovery_estimate,
)


class TestCalculateDrawdown:
    """Tests for basic drawdown calculation."""

    def test_no_drawdown_at_peak(self) -> None:
        """Current equals peak means 0% drawdown."""
        result = calculate_drawdown(10000.0, 10000.0)
        assert result == 0.0

    def test_ten_percent_drawdown(self) -> None:
        """10% decline from peak."""
        result = calculate_drawdown(10000.0, 9000.0)
        assert result == pytest.approx(10.0, rel=0.001)

    def test_fifty_percent_drawdown(self) -> None:
        """50% decline from peak."""
        result = calculate_drawdown(10000.0, 5000.0)
        assert result == pytest.approx(50.0, rel=0.001)

    def test_zero_peak_returns_zero(self) -> None:
        """Zero peak equity returns 0% drawdown."""
        result = calculate_drawdown(0.0, 5000.0)
        assert result == 0.0

    def test_negative_peak_returns_zero(self) -> None:
        """Negative peak returns 0% drawdown."""
        result = calculate_drawdown(-1000.0, 5000.0)
        assert result == 0.0

    def test_current_above_peak_negative_drawdown(self) -> None:
        """Current above peak gives negative drawdown (gain)."""
        result = calculate_drawdown(10000.0, 11000.0)
        assert result == pytest.approx(-10.0, rel=0.001)


class TestDrawdownMetrics:
    """Tests for comprehensive drawdown metrics calculation."""

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage with standard responses."""
        storage = MagicMock()
        return storage

    def test_metrics_at_peak_no_drawdown(self, mock_storage: MagicMock) -> None:
        """Portfolio at peak should show 0% drawdown."""
        # Mock portfolio equity at $10,000
        mock_storage.query.side_effect = [
            # Cash balance query
            MagicMock(is_empty=lambda: False, get_column=lambda x: [10000.0]),
            # Position value query
            MagicMock(is_empty=lambda: False, get_column=lambda x: [0]),
            # Peak equity query (same as current)
            MagicMock(is_empty=lambda: True),
            # Cash for peak calculation
            MagicMock(is_empty=lambda: False, get_column=lambda x: [10000.0]),
            # Positions for peak
            MagicMock(is_empty=lambda: False, get_column=lambda x: [0]),
            # Underwater days query
            MagicMock(is_empty=lambda: True),
            # First snapshot
            MagicMock(is_empty=lambda: True),
            # Max drawdown query
            MagicMock(is_empty=lambda: False, get_column=lambda x: [0]),
        ]

        metrics = calculate_drawdown_metrics(mock_storage, "test-account")

        assert metrics.current_drawdown_pct == 0.0
        assert metrics.is_halted is False
        assert metrics.halt_reason is None

    def test_metrics_halt_at_ten_percent(self, mock_storage: MagicMock) -> None:
        """Trading should halt at 10% drawdown."""
        # Current equity $9,000, peak $10,000 = 10% drawdown
        mock_storage.query.side_effect = [
            # Cash balance
            MagicMock(is_empty=lambda: False, get_column=lambda x: [9000.0]),
            # Position value
            MagicMock(is_empty=lambda: False, get_column=lambda x: [0]),
            # Peak equity from snapshots
            MagicMock(
                is_empty=lambda: False,
                get_column=lambda col: [10000.0]
                if "equity" in col
                else [date.today() - timedelta(days=5)],
            ),
            # Underwater days - no peak at current
            MagicMock(is_empty=lambda: True),
            # First snapshot
            MagicMock(
                is_empty=lambda: False, get_column=lambda x: [date.today() - timedelta(days=10)]
            ),
            # Max drawdown
            MagicMock(is_empty=lambda: False, get_column=lambda x: [8.0]),
        ]

        metrics = calculate_drawdown_metrics(mock_storage, "test-account")

        assert metrics.current_drawdown_pct == pytest.approx(10.0, rel=0.01)
        assert metrics.is_halted is True
        assert "10%" in (metrics.halt_reason or "")


class TestCheckPortfolioDrawdownHalt:
    """Tests for portfolio drawdown halt check."""

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage."""
        return MagicMock()

    def test_can_trade_below_threshold(self, mock_storage: MagicMock) -> None:
        """Should allow trading below 10% drawdown."""
        # 5% drawdown - below halt threshold
        with patch("app.portfolio.drawdown.calculate_drawdown_metrics") as mock_calc:
            mock_calc.return_value = DrawdownMetrics(
                current_drawdown_pct=5.0,
                max_drawdown_pct=5.0,
                peak_equity=10000.0,
                peak_date=date.today(),
                current_equity=9500.0,
                underwater_days=2,
                is_halted=False,
                halt_reason=None,
            )

            can_trade, reason = check_portfolio_drawdown_halt(mock_storage, "test-account")

            assert can_trade is True
            assert reason is None

    def test_halt_at_threshold(self, mock_storage: MagicMock) -> None:
        """Should halt trading at 10% drawdown."""
        with patch("app.portfolio.drawdown.calculate_drawdown_metrics") as mock_calc:
            mock_calc.return_value = DrawdownMetrics(
                current_drawdown_pct=10.0,
                max_drawdown_pct=10.0,
                peak_equity=10000.0,
                peak_date=date.today() - timedelta(days=5),
                current_equity=9000.0,
                underwater_days=5,
                is_halted=True,
                halt_reason="Portfolio drawdown of 10.0% exceeds 10% limit. Trading halted.",
            )

            can_trade, reason = check_portfolio_drawdown_halt(mock_storage, "test-account")

            assert can_trade is False
            assert reason is not None
            assert "10" in reason

    def test_halt_above_threshold(self, mock_storage: MagicMock) -> None:
        """Should halt trading above 10% drawdown."""
        with patch("app.portfolio.drawdown.calculate_drawdown_metrics") as mock_calc:
            mock_calc.return_value = DrawdownMetrics(
                current_drawdown_pct=15.0,
                max_drawdown_pct=15.0,
                peak_equity=10000.0,
                peak_date=date.today() - timedelta(days=10),
                current_equity=8500.0,
                underwater_days=10,
                is_halted=True,
                halt_reason="Portfolio drawdown of 15.0% exceeds 10% limit. Trading halted.",
            )

            can_trade, reason = check_portfolio_drawdown_halt(mock_storage, "test-account")

            assert can_trade is False
            assert reason is not None


class TestPositionDrawdown:
    """Tests for position-level drawdown tracking."""

    def test_position_at_entry_no_excursion(self) -> None:
        """Position at entry price has no excursion."""
        result = calculate_position_drawdown(
            entry_price=100.0,
            current_price=100.0,
            peak_price=100.0,
        )

        assert result.current_pnl_pct == 0.0
        assert result.max_favorable_excursion == 0.0
        assert result.max_adverse_excursion == 0.0

    def test_position_with_gain(self) -> None:
        """Position with 10% gain."""
        result = calculate_position_drawdown(
            entry_price=100.0,
            current_price=110.0,
            peak_price=115.0,  # Was up 15% at peak
        )

        assert result.current_pnl_pct == pytest.approx(10.0, rel=0.01)
        assert result.max_favorable_excursion == pytest.approx(15.0, rel=0.01)
        assert result.max_adverse_excursion == 0.0  # Never went below entry

    def test_position_with_loss(self) -> None:
        """Position with 10% loss."""
        result = calculate_position_drawdown(
            entry_price=100.0,
            current_price=90.0,
            peak_price=105.0,  # Was up 5% before dropping
        )

        assert result.current_pnl_pct == pytest.approx(-10.0, rel=0.01)
        assert result.max_favorable_excursion == pytest.approx(5.0, rel=0.01)
        assert result.max_adverse_excursion == pytest.approx(10.0, rel=0.01)

    def test_zero_entry_price(self) -> None:
        """Zero entry price returns empty metrics."""
        result = calculate_position_drawdown(
            entry_price=0.0,
            current_price=100.0,
            peak_price=100.0,
        )

        assert result.current_pnl_pct == 0.0
        assert result.max_favorable_excursion == 0.0


class TestRecoveryEstimate:
    """Tests for drawdown recovery estimation."""

    def test_no_drawdown_zero_days(self) -> None:
        """No drawdown needs 0 days to recover."""
        result = get_recovery_estimate(0.0)
        assert result == 0

    def test_ten_percent_drawdown(self) -> None:
        """10% drawdown recovery estimate."""
        # 10% drawdown needs ~11.11% gain to break even
        # At 0.05% daily avg = 222 days
        result = get_recovery_estimate(10.0, 0.05)
        assert result is not None
        assert result > 200  # Should be several months

    def test_small_drawdown_quick_recovery(self) -> None:
        """Small drawdown recovers faster."""
        result = get_recovery_estimate(2.0, 0.05)
        assert result is not None
        assert result < 50  # Less than 2 months

    def test_zero_daily_return(self) -> None:
        """Zero daily return means no recovery."""
        result = get_recovery_estimate(10.0, 0.0)
        assert result == 0


class TestConstants:
    """Tests for drawdown threshold constants."""

    def test_halt_threshold(self) -> None:
        """Verify halt threshold is 10%."""
        assert PORTFOLIO_DRAWDOWN_HALT_PCT == 10.0

    def test_warning_levels(self) -> None:
        """Verify warning levels are reasonable."""
        assert DRAWDOWN_WARNING_LEVEL_1 == 5.0
        assert DRAWDOWN_WARNING_LEVEL_2 == 7.5
        assert DRAWDOWN_WARNING_LEVEL_1 < DRAWDOWN_WARNING_LEVEL_2
        assert DRAWDOWN_WARNING_LEVEL_2 < PORTFOLIO_DRAWDOWN_HALT_PCT
