"""Tests for multi-horizon momentum calculations (GAP-012).

Tests cover:
- Momentum calculation for multiple horizons
- Regime detection
- Trend alignment
- Momentum score for signal classification
"""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from app.analytics.momentum import (
    MOMENTUM_HORIZONS,
    MomentumMetrics,
    _check_trend_alignment,
    _determine_regime,
    calculate_momentum,
    calculate_momentum_score,
)


class TestDetermineRegime:
    """Tests for regime detection based on 252d momentum."""

    def test_strong_uptrend(self) -> None:
        """Strong uptrend at >20% annual momentum."""
        assert _determine_regime(25.0) == "STRONG_UP"
        assert _determine_regime(50.0) == "STRONG_UP"

    def test_weak_uptrend(self) -> None:
        """Weak uptrend at 5-20% annual momentum."""
        assert _determine_regime(10.0) == "UP"
        assert _determine_regime(19.9) == "UP"

    def test_choppy_regime(self) -> None:
        """Choppy/range-bound at -5% to 5%."""
        assert _determine_regime(0.0) == "CHOPPY"
        assert _determine_regime(4.9) == "CHOPPY"
        assert _determine_regime(-4.9) == "CHOPPY"

    def test_weak_downtrend(self) -> None:
        """Weak downtrend at -20% to -5%."""
        assert _determine_regime(-10.0) == "DOWN"
        assert _determine_regime(-19.9) == "DOWN"

    def test_strong_downtrend(self) -> None:
        """Strong downtrend at <-20%."""
        assert _determine_regime(-25.0) == "STRONG_DOWN"
        assert _determine_regime(-50.0) == "STRONG_DOWN"

    def test_none_returns_unknown(self) -> None:
        """None momentum returns UNKNOWN."""
        assert _determine_regime(None) == "UNKNOWN"


class TestCheckTrendAlignment:
    """Tests for trend alignment detection."""

    def test_all_positive_aligned(self) -> None:
        """All positive values are aligned."""
        result = _check_trend_alignment({5: 2.0, 20: 5.0, 60: 10.0, 252: 15.0})
        assert result is True

    def test_all_negative_aligned(self) -> None:
        """All negative values are aligned."""
        result = _check_trend_alignment({5: -2.0, 20: -5.0, 60: -10.0, 252: -15.0})
        assert result is True

    def test_mixed_not_aligned(self) -> None:
        """Mixed positive/negative not aligned."""
        result = _check_trend_alignment({5: 2.0, 20: -5.0, 60: 10.0, 252: -15.0})
        assert result is False

    def test_insufficient_data(self) -> None:
        """Less than 2 values returns False."""
        result = _check_trend_alignment({5: 2.0})
        assert result is False
        result = _check_trend_alignment({})
        assert result is False

    def test_with_none_values(self) -> None:
        """None values are ignored."""
        result = _check_trend_alignment({5: 2.0, 20: None, 60: 5.0, 252: 10.0})
        assert result is True


class TestCalculateMomentumScore:
    """Tests for momentum score calculation."""

    def test_none_momentum_returns_zero(self) -> None:
        """No momentum data returns 0 score."""
        score, reasons = calculate_momentum_score(None)
        assert score == 0
        assert reasons == []

    def test_strong_positive_momentum(self) -> None:
        """Strong positive 252d momentum gets 2+ points."""
        metrics = MomentumMetrics(
            symbol="AAPL",
            as_of_date=date.today(),
            momentum_5d=1.0,
            momentum_20d=5.0,
            momentum_60d=10.0,
            momentum_252d=25.0,
            regime="STRONG_UP",
            trend_alignment=True,
        )
        score, reasons = calculate_momentum_score(metrics)
        # 2 (strong 252d) + 1 (aligned) = 3 minimum
        assert score >= 3
        assert any("252d" in r for r in reasons)

    def test_weak_positive_momentum(self) -> None:
        """Weak positive momentum gets 1 point."""
        metrics = MomentumMetrics(
            symbol="AAPL",
            as_of_date=date.today(),
            momentum_5d=0.5,
            momentum_20d=1.0,
            momentum_60d=2.0,
            momentum_252d=3.0,
            regime="CHOPPY",
            trend_alignment=True,
        )
        score, _reasons = calculate_momentum_score(metrics)
        # 1 (weak 252d) + 1 (aligned) = 2
        assert score >= 1
        assert score <= 4

    def test_strong_negative_momentum(self) -> None:
        """Strong negative momentum subtracts points."""
        metrics = MomentumMetrics(
            symbol="AAPL",
            as_of_date=date.today(),
            momentum_5d=-3.0,
            momentum_20d=-8.0,
            momentum_60d=-15.0,
            momentum_252d=-25.0,
            regime="STRONG_DOWN",
            trend_alignment=True,
        )
        score, reasons = calculate_momentum_score(metrics)
        # -1 (strong down) + 1 (aligned) = 0 (clamped)
        assert score >= 0
        assert any("downtrend" in r.lower() for r in reasons)

    def test_accelerating_momentum_bonus(self) -> None:
        """Accelerating momentum (5d > 20d > 0) gets bonus."""
        metrics = MomentumMetrics(
            symbol="AAPL",
            as_of_date=date.today(),
            momentum_5d=5.0,  # Higher than 20d
            momentum_20d=3.0,  # Positive
            momentum_60d=8.0,
            momentum_252d=15.0,
            regime="UP",
            trend_alignment=True,
        )
        _score, reasons = calculate_momentum_score(metrics)
        # Should get acceleration bonus
        assert any("accelerating" in r.lower() for r in reasons)

    def test_score_clamped_to_range(self) -> None:
        """Score is clamped to 0-5 range."""
        # Best case scenario
        metrics = MomentumMetrics(
            symbol="AAPL",
            as_of_date=date.today(),
            momentum_5d=10.0,
            momentum_20d=8.0,
            momentum_60d=20.0,
            momentum_252d=50.0,
            regime="STRONG_UP",
            trend_alignment=True,
        )
        score, _ = calculate_momentum_score(metrics)
        assert 0 <= score <= 5


class TestMomentumHorizons:
    """Tests for momentum horizon constants."""

    def test_horizons_defined(self) -> None:
        """Verify all required horizons are defined."""
        assert 5 in MOMENTUM_HORIZONS
        assert 20 in MOMENTUM_HORIZONS
        assert 60 in MOMENTUM_HORIZONS
        assert 252 in MOMENTUM_HORIZONS

    def test_horizons_ordered(self) -> None:
        """Horizons should be in ascending order."""
        assert sorted(MOMENTUM_HORIZONS) == MOMENTUM_HORIZONS


class TestCalculateMomentum:
    """Tests for momentum calculation from database."""

    @pytest.fixture
    def mock_storage(self) -> MagicMock:
        """Create mock storage."""
        return MagicMock()

    def test_no_data_returns_none(self, mock_storage: MagicMock) -> None:
        """No price data returns None."""
        mock_storage.query.return_value = MagicMock(is_empty=lambda: True)

        result = calculate_momentum(mock_storage, "AAPL")
        assert result is None

    def test_calculates_from_price_data(self, mock_storage: MagicMock) -> None:
        """Calculates momentum from price history."""
        # Create mock result with 300 days of prices
        today = date.today()
        mock_data = []
        base_price = 100.0

        for i in range(300):
            d = today - timedelta(days=i)
            # Price increases over time (positive momentum)
            price = base_price + (299 - i) * 0.1  # Older dates have lower prices
            mock_data.append({"date": d, "close": price})

        mock_result = MagicMock()
        mock_result.is_empty.return_value = False
        mock_result.iter_rows.return_value = iter(mock_data)
        mock_storage.query.return_value = mock_result

        result = calculate_momentum(mock_storage, "AAPL")

        assert result is not None
        assert result.symbol == "AAPL"
        # All momentum should be positive (prices increasing)
        assert result.momentum_5d is not None and result.momentum_5d > 0
        assert result.momentum_20d is not None and result.momentum_20d > 0
