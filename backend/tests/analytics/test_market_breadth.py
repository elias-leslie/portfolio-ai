"""Tests for enhanced market breadth analysis (GAP-017)."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import polars as pl
import pytest

from app.analytics.market_breadth import (
    SECTOR_ETFS,
    BreadthReading,
    BreadthSignal,
    analyze_market_breadth,
    calculate_breadth_reading,
    calculate_breadth_score,
    classify_breadth_signal,
    detect_divergence,
    get_breadth_history,
    get_spy_returns,
)


class TestSectorETFs:
    """Tests for sector ETF configuration."""

    def test_has_11_sectors(self) -> None:
        """Should have all 11 S&P sectors."""
        assert len(SECTOR_ETFS) == 11

    def test_includes_major_sectors(self) -> None:
        """Should include major sector ETFs."""
        assert "XLK" in SECTOR_ETFS  # Technology
        assert "XLF" in SECTOR_ETFS  # Financials
        assert "XLE" in SECTOR_ETFS  # Energy
        assert "XLV" in SECTOR_ETFS  # Healthcare


class TestClassifyBreadthSignal:
    """Tests for classify_breadth_signal function."""

    def test_thrust_up(self) -> None:
        """90%+ should be THRUST_UP."""
        assert classify_breadth_signal(95) == BreadthSignal.THRUST_UP
        assert classify_breadth_signal(90) == BreadthSignal.THRUST_UP

    def test_strong_up(self) -> None:
        """70-90% should be STRONG_UP."""
        assert classify_breadth_signal(75) == BreadthSignal.STRONG_UP
        assert classify_breadth_signal(89.9) == BreadthSignal.STRONG_UP

    def test_moderate_up(self) -> None:
        """55-70% should be MODERATE_UP."""
        assert classify_breadth_signal(60) == BreadthSignal.MODERATE_UP
        assert classify_breadth_signal(55) == BreadthSignal.MODERATE_UP

    def test_neutral(self) -> None:
        """45-55% should be NEUTRAL."""
        assert classify_breadth_signal(50) == BreadthSignal.NEUTRAL
        assert classify_breadth_signal(45) == BreadthSignal.NEUTRAL

    def test_moderate_down(self) -> None:
        """30-45% should be MODERATE_DOWN."""
        assert classify_breadth_signal(35) == BreadthSignal.MODERATE_DOWN

    def test_strong_down(self) -> None:
        """10-30% should be STRONG_DOWN."""
        assert classify_breadth_signal(20) == BreadthSignal.STRONG_DOWN

    def test_thrust_down(self) -> None:
        """<10% should be THRUST_DOWN."""
        assert classify_breadth_signal(5) == BreadthSignal.THRUST_DOWN
        assert classify_breadth_signal(9.9) == BreadthSignal.THRUST_DOWN


class TestDetectDivergence:
    """Tests for detect_divergence function."""

    def test_bullish_divergence(self) -> None:
        """Breadth improving + SPY falling = bullish."""
        result = detect_divergence(10.0, -5.0)
        assert result == "bullish_divergence"

    def test_bearish_divergence(self) -> None:
        """Breadth weakening + SPY rising = bearish."""
        result = detect_divergence(-10.0, 5.0)
        assert result == "bearish_divergence"

    def test_no_divergence_aligned(self) -> None:
        """Both improving = no divergence."""
        result = detect_divergence(10.0, 5.0)
        assert result is None

    def test_no_divergence_small_moves(self) -> None:
        """Small moves = no divergence."""
        result = detect_divergence(2.0, -1.0)
        assert result is None


class TestCalculateBreadthScore:
    """Tests for calculate_breadth_score function."""

    def test_thrust_up_score(self) -> None:
        """THRUST_UP should score +2."""
        score = calculate_breadth_score(BreadthSignal.THRUST_UP, 0, None)
        assert score == 2

    def test_thrust_down_score(self) -> None:
        """THRUST_DOWN should score -2."""
        score = calculate_breadth_score(BreadthSignal.THRUST_DOWN, 0, None)
        assert score == -2

    def test_neutral_score(self) -> None:
        """NEUTRAL should score 0."""
        score = calculate_breadth_score(BreadthSignal.NEUTRAL, 0, None)
        assert score == 0

    def test_bullish_divergence_adds_point(self) -> None:
        """Bullish divergence should add 1."""
        score = calculate_breadth_score(
            BreadthSignal.MODERATE_DOWN, 0, "bullish_divergence"
        )
        assert score == 0  # -1 + 1 = 0

    def test_bearish_divergence_subtracts(self) -> None:
        """Bearish divergence should subtract 1."""
        score = calculate_breadth_score(
            BreadthSignal.MODERATE_UP, 0, "bearish_divergence"
        )
        assert score == 0  # 1 - 1 = 0

    def test_score_capped_at_2(self) -> None:
        """Score should not exceed 2."""
        score = calculate_breadth_score(
            BreadthSignal.THRUST_UP, 20, "bullish_divergence"
        )
        assert score <= 2

    def test_score_min_minus_2(self) -> None:
        """Score should not go below -2."""
        score = calculate_breadth_score(
            BreadthSignal.THRUST_DOWN, -20, "bearish_divergence"
        )
        assert score >= -2


class TestCalculateBreadthReading:
    """Tests for calculate_breadth_reading function."""

    def test_calculates_from_db_data(self) -> None:
        """Should calculate breadth from database."""
        mock_storage = MagicMock()
        # 8 sectors: 6 up, 2 down
        mock_df = pl.DataFrame({
            "ticker": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU"],
            "current_close": [100.0, 50.0, 60.0, 120.0, 90.0, 70.0, 80.0, 55.0],
            "prev_close": [95.0, 48.0, 58.0, 118.0, 88.0, 68.0, 82.0, 57.0],
        })
        mock_storage.query.return_value = mock_df

        result = calculate_breadth_reading(mock_storage, date(2025, 1, 15))

        assert result is not None
        assert result.advancing == 6
        assert result.declining == 2
        assert result.breadth_pct == 75.0  # 6/8

    def test_returns_none_insufficient_data(self) -> None:
        """Should return None with < 8 sectors."""
        mock_storage = MagicMock()
        mock_df = pl.DataFrame({
            "ticker": ["XLK", "XLF"],
            "current_close": [100.0, 50.0],
            "prev_close": [95.0, 48.0],
        })
        mock_storage.query.return_value = mock_df

        result = calculate_breadth_reading(mock_storage, date(2025, 1, 15))
        assert result is None


class TestGetSpyReturns:
    """Tests for get_spy_returns function."""

    def test_calculates_returns(self) -> None:
        """Should calculate 1d and 5d returns."""
        mock_storage = MagicMock()
        # Newest first: 100, 99, 98, 97, 96, 95 (going back)
        mock_df = pl.DataFrame({
            "date": [date(2025, 1, 6), date(2025, 1, 5), date(2025, 1, 4),
                    date(2025, 1, 3), date(2025, 1, 2), date(2025, 1, 1)],
            "close": [100.0, 99.0, 98.0, 97.0, 96.0, 95.0],
        })
        mock_storage.query.return_value = mock_df

        return_1d, return_5d = get_spy_returns(mock_storage, date(2025, 1, 6))

        assert abs(return_1d - 1.01) < 0.1  # 100/99 - 1 ≈ 1%
        assert abs(return_5d - 5.26) < 0.1  # 100/95 - 1 ≈ 5.26%


class TestAnalyzeMarketBreadth:
    """Tests for analyze_market_breadth function."""

    def test_returns_complete_analysis(self) -> None:
        """Should return complete BreadthAnalysis."""
        mock_storage = MagicMock()

        # Breadth data DataFrame
        breadth_df = pl.DataFrame({
            "ticker": ["XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLI", "XLU"],
            "current_close": [100.0, 50.0, 60.0, 120.0, 90.0, 70.0, 80.0, 55.0],
            "prev_close": [95.0, 48.0, 58.0, 118.0, 88.0, 68.0, 78.0, 53.0],
        })

        # SPY data DataFrame
        spy_df = pl.DataFrame({
            "date": [date(2025, 1, 15) - timedelta(days=i) for i in range(20)],
            "close": [100.0 - i for i in range(20)],
        })

        # Latest date DataFrame
        latest_df = pl.DataFrame({"max": [date(2025, 1, 15)]})

        # Create list of responses: latest date + breadth queries + SPY query
        responses = [latest_df]  # Latest date
        responses.extend([breadth_df] * 30)  # Breadth for each day
        responses.append(spy_df)  # SPY returns

        mock_storage.query.side_effect = responses

        result = analyze_market_breadth(mock_storage)

        assert result is not None
        assert result.breadth_1d > 0
        assert 0 <= result.breadth_5d_avg <= 100
        assert result.signal in list(BreadthSignal)
        assert -2 <= result.breadth_score <= 2

    def test_returns_none_insufficient_data(self) -> None:
        """Should return None with insufficient history."""
        mock_storage = MagicMock()

        # Latest date DataFrame
        latest_df = pl.DataFrame({"max": [date(2025, 1, 15)]})

        # Empty breadth data
        empty_df = pl.DataFrame()

        responses = [latest_df]
        responses.extend([empty_df] * 30)  # No breadth data

        mock_storage.query.side_effect = responses

        result = analyze_market_breadth(mock_storage)
        # Will return None because history is too short
        assert result is None
