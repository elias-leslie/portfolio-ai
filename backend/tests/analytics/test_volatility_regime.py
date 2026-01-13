"""Tests for volatility regime detection (GAP-018)."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import polars as pl

from app.analytics.volatility_regime import (
    REGIME_ADJUSTMENTS,
    VIX_THRESHOLDS,
    VolatilityRegime,
    analyze_volatility_regime,
    calculate_vix_percentile,
    classify_vix_regime,
    detect_regime_transition,
    get_regime_history,
    get_regime_score,
)


class TestClassifyVixRegime:
    """Tests for classify_vix_regime function."""

    def test_low_regime(self) -> None:
        """VIX under 15 = LOW regime."""
        assert classify_vix_regime(10) == VolatilityRegime.LOW
        assert classify_vix_regime(14.9) == VolatilityRegime.LOW

    def test_normal_regime(self) -> None:
        """VIX 15-20 = NORMAL regime."""
        assert classify_vix_regime(15) == VolatilityRegime.NORMAL
        assert classify_vix_regime(17) == VolatilityRegime.NORMAL
        assert classify_vix_regime(19.9) == VolatilityRegime.NORMAL

    def test_elevated_regime(self) -> None:
        """VIX 20-30 = ELEVATED regime."""
        assert classify_vix_regime(20) == VolatilityRegime.ELEVATED
        assert classify_vix_regime(25) == VolatilityRegime.ELEVATED
        assert classify_vix_regime(29.9) == VolatilityRegime.ELEVATED

    def test_high_regime(self) -> None:
        """VIX 30-50 = HIGH regime."""
        assert classify_vix_regime(30) == VolatilityRegime.HIGH
        assert classify_vix_regime(40) == VolatilityRegime.HIGH
        assert classify_vix_regime(49.9) == VolatilityRegime.HIGH

    def test_extreme_regime(self) -> None:
        """VIX 50+ = EXTREME regime."""
        assert classify_vix_regime(50) == VolatilityRegime.EXTREME
        assert classify_vix_regime(80) == VolatilityRegime.EXTREME
        assert classify_vix_regime(100) == VolatilityRegime.EXTREME


class TestVixThresholds:
    """Tests for VIX threshold configuration."""

    def test_all_regimes_have_thresholds(self) -> None:
        """All regimes should have defined thresholds."""
        for regime in VolatilityRegime:
            assert regime in VIX_THRESHOLDS

    def test_thresholds_continuous(self) -> None:
        """Thresholds should be continuous (no gaps)."""
        sorted_regimes = sorted(VIX_THRESHOLDS.items(), key=lambda x: x[1][0])
        for i in range(len(sorted_regimes) - 1):
            _, (_, high) = sorted_regimes[i]
            _, (low, _) = sorted_regimes[i + 1]
            assert high == low


class TestRegimeAdjustments:
    """Tests for regime-specific trading adjustments."""

    def test_all_regimes_have_adjustments(self) -> None:
        """All regimes should have trading adjustments."""
        for regime in VolatilityRegime:
            assert regime in REGIME_ADJUSTMENTS
            adj = REGIME_ADJUSTMENTS[regime]
            assert "position_size_multiplier" in adj
            assert "stop_loss_multiplier" in adj
            assert "correlation_threshold" in adj

    def test_extreme_has_smallest_position_size(self) -> None:
        """EXTREME regime should have smallest position size."""
        extreme_size = REGIME_ADJUSTMENTS[VolatilityRegime.EXTREME]["position_size_multiplier"]
        for regime in VolatilityRegime:
            if regime != VolatilityRegime.EXTREME:
                assert REGIME_ADJUSTMENTS[regime]["position_size_multiplier"] >= extreme_size

    def test_extreme_has_widest_stops(self) -> None:
        """EXTREME regime should have widest stops."""
        extreme_stop = REGIME_ADJUSTMENTS[VolatilityRegime.EXTREME]["stop_loss_multiplier"]
        for regime in VolatilityRegime:
            if regime != VolatilityRegime.EXTREME:
                assert REGIME_ADJUSTMENTS[regime]["stop_loss_multiplier"] <= extreme_stop


class TestCalculateVixPercentile:
    """Tests for calculate_vix_percentile function."""

    def test_with_historical_data(self) -> None:
        """Should calculate percentile from historical data."""
        mock_storage = MagicMock()
        # Historical VIX values: 10, 15, 18, 20, 25, 30
        mock_df = pl.DataFrame({"vix": [10, 15, 18, 20, 25, 30]})
        mock_storage.query.return_value = mock_df

        percentile = calculate_vix_percentile(18, mock_storage)
        # 18 is greater than 10, 15 (2 values), so 2/6 = 33.3%
        assert 30 <= percentile <= 35

    def test_fallback_without_data(self) -> None:
        """Should use fallback distribution without data."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = pl.DataFrame()

        # Test various VIX levels
        assert calculate_vix_percentile(10, mock_storage) == 10.0  # Very low
        assert calculate_vix_percentile(17, mock_storage) == 50.0  # Median
        assert calculate_vix_percentile(35, mock_storage) == 95.0  # High


class TestGetRegimeHistory:
    """Tests for get_regime_history function."""

    def test_returns_regime_history(self) -> None:
        """Should return regime history tuples."""
        mock_storage = MagicMock()
        today = date.today()
        mock_df = pl.DataFrame(
            {
                "date": [today, today - timedelta(days=1), today - timedelta(days=2)],
                "vix": [25, 22, 18],
            }
        )
        mock_storage.query.return_value = mock_df

        history = get_regime_history(mock_storage)

        assert len(history) == 3
        assert history[0][1] == VolatilityRegime.ELEVATED
        assert history[2][1] == VolatilityRegime.NORMAL


class TestDetectRegimeTransition:
    """Tests for detect_regime_transition function."""

    def test_detects_entering_elevated(self) -> None:
        """Should detect transition into higher regime."""
        today = date.today()
        history = [
            (today, VolatilityRegime.HIGH),  # Just entered HIGH
            (today - timedelta(days=1), VolatilityRegime.HIGH),
            (today - timedelta(days=2), VolatilityRegime.ELEVATED),
        ]

        signal, duration, prev = detect_regime_transition(VolatilityRegime.HIGH, history)

        assert signal == "entering_high"
        assert duration == 2
        assert prev == VolatilityRegime.ELEVATED

    def test_no_transition_in_stable_regime(self) -> None:
        """Should not signal transition in stable regime."""
        today = date.today()
        history = [(today - timedelta(days=i), VolatilityRegime.NORMAL) for i in range(10)]

        signal, duration, prev = detect_regime_transition(VolatilityRegime.NORMAL, history)

        assert signal is None
        assert duration == 10
        assert prev is None

    def test_empty_history(self) -> None:
        """Should handle empty history."""
        signal, duration, prev = detect_regime_transition(VolatilityRegime.NORMAL, [])

        assert signal is None
        assert duration == 0
        assert prev is None


class TestAnalyzeVolatilityRegime:
    """Tests for analyze_volatility_regime function."""

    def test_returns_complete_analysis(self) -> None:
        """Should return complete RegimeAnalysis."""
        mock_storage = MagicMock()
        today = date.today()
        # Configure mock for multiple query calls
        mock_storage.query.side_effect = [
            pl.DataFrame({"vix": [25.0]}),  # Current VIX
            pl.DataFrame({"vix": [20, 22, 18, 25, 30]}),  # Historical for percentile
            pl.DataFrame(
                {
                    "date": [today, today - timedelta(days=1)],
                    "vix": [25, 22],
                }
            ),  # History
        ]

        analysis = analyze_volatility_regime(mock_storage)

        assert analysis.current_vix == 25.0
        assert analysis.regime == VolatilityRegime.ELEVATED
        assert 0 <= analysis.vix_percentile <= 100
        assert analysis.trading_adjustments == REGIME_ADJUSTMENTS[VolatilityRegime.ELEVATED]

    def test_uses_override_vix(self) -> None:
        """Should use provided VIX override."""
        mock_storage = MagicMock()
        mock_storage.query.return_value = pl.DataFrame()  # No data

        analysis = analyze_volatility_regime(mock_storage, current_vix=40.0)

        assert analysis.current_vix == 40.0
        assert analysis.regime == VolatilityRegime.HIGH


class TestGetRegimeScore:
    """Tests for get_regime_score function."""

    def test_low_regime_positive(self) -> None:
        """LOW regime should have positive score."""
        assert get_regime_score(VolatilityRegime.LOW) == 2

    def test_extreme_regime_negative(self) -> None:
        """EXTREME regime should have negative score."""
        assert get_regime_score(VolatilityRegime.EXTREME) == -2

    def test_normal_regime_positive(self) -> None:
        """NORMAL regime should be positive."""
        assert get_regime_score(VolatilityRegime.NORMAL) == 1

    def test_elevated_regime_neutral(self) -> None:
        """ELEVATED regime should be neutral."""
        assert get_regime_score(VolatilityRegime.ELEVATED) == 0

    def test_scores_decrease_with_volatility(self) -> None:
        """Scores should decrease as volatility increases."""
        regimes = [
            VolatilityRegime.LOW,
            VolatilityRegime.NORMAL,
            VolatilityRegime.ELEVATED,
            VolatilityRegime.HIGH,
            VolatilityRegime.EXTREME,
        ]
        scores = [get_regime_score(r) for r in regimes]
        assert scores == sorted(scores, reverse=True)
