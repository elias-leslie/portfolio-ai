"""Unit tests for multi-timeframe alignment analysis."""

from __future__ import annotations

from app.watchlist.timeframe import calculate_timeframe_alignment, calculate_volume_relative


class TestCalculateTimeframeAlignment:
    """Tests for calculate_timeframe_alignment function."""

    def test_both_aligned_bullish_trend(self) -> None:
        """Test both timeframes aligned when price > SMA_20 > SMA_50 > SMA_200."""
        # Strong bullish setup: price > sma20 > sma50 > sma200
        short, long = calculate_timeframe_alignment(
            price=150.0,
            sma_20=140.0,
            sma_50=130.0,
            sma_200=120.0,
        )
        assert short is True
        assert long is True

    def test_neither_aligned_bearish_trend(self) -> None:
        """Test neither timeframe aligned when price < SMA_20 < SMA_50 < SMA_200."""
        # Bearish setup: price < sma20 < sma50 < sma200
        short, long = calculate_timeframe_alignment(
            price=100.0,
            sma_20=110.0,
            sma_50=120.0,
            sma_200=130.0,
        )
        assert short is False
        assert long is False

    def test_short_aligned_long_not(self) -> None:
        """Test short-term aligned but long-term not."""
        # Price > SMA_20 > SMA_50, but SMA_50 < SMA_200
        short, long = calculate_timeframe_alignment(
            price=150.0,
            sma_20=140.0,
            sma_50=130.0,
            sma_200=140.0,  # Above SMA_50
        )
        assert short is True
        assert long is False

    def test_long_aligned_short_not(self) -> None:
        """Test long-term aligned but short-term not."""
        # SMA_50 > SMA_200, but Price < SMA_20
        short, long = calculate_timeframe_alignment(
            price=130.0,
            sma_20=140.0,  # Above price
            sma_50=150.0,
            sma_200=140.0,
        )
        assert short is False
        assert long is True

    def test_missing_sma_20_returns_short_false(self) -> None:
        """Test missing SMA_20 returns short_aligned=False."""
        short, long = calculate_timeframe_alignment(
            price=150.0,
            sma_20=None,
            sma_50=130.0,
            sma_200=120.0,
        )
        assert short is False
        assert long is True

    def test_missing_sma_50_returns_both_false(self) -> None:
        """Test missing SMA_50 returns both False (needed for both checks)."""
        short, long = calculate_timeframe_alignment(
            price=150.0,
            sma_20=140.0,
            sma_50=None,
            sma_200=120.0,
        )
        assert short is False
        assert long is False

    def test_missing_sma_200_returns_long_false(self) -> None:
        """Test missing SMA_200 returns long_aligned=False."""
        short, long = calculate_timeframe_alignment(
            price=150.0,
            sma_20=140.0,
            sma_50=130.0,
            sma_200=None,
        )
        assert short is True
        assert long is False

    def test_all_smas_none_returns_both_false(self) -> None:
        """Test all SMAs None returns both False."""
        short, long = calculate_timeframe_alignment(
            price=150.0,
            sma_20=None,
            sma_50=None,
            sma_200=None,
        )
        assert short is False
        assert long is False

    def test_price_equals_sma_20_not_aligned(self) -> None:
        """Test price equals SMA_20 is not short-aligned (not strictly greater)."""
        short, long = calculate_timeframe_alignment(
            price=140.0,
            sma_20=140.0,  # Equal to price
            sma_50=130.0,
            sma_200=120.0,
        )
        assert short is False  # Price must be > SMA_20
        assert long is True

    def test_sma_50_equals_sma_200_not_long_aligned(self) -> None:
        """Test SMA_50 equals SMA_200 is not long-aligned."""
        short, long = calculate_timeframe_alignment(
            price=150.0,
            sma_20=140.0,
            sma_50=130.0,
            sma_200=130.0,  # Equal to SMA_50
        )
        assert short is True
        assert long is False  # SMA_50 must be > SMA_200


class TestCalculateVolumeRelative:
    """Tests for calculate_volume_relative function."""

    def test_volume_above_average(self) -> None:
        """Test volume 2x average returns 2.0."""
        result = calculate_volume_relative(
            current_volume=2_000_000,
            avg_volume_50d=1_000_000,
        )
        assert result == 2.0

    def test_volume_below_average(self) -> None:
        """Test volume 0.5x average returns 0.5."""
        result = calculate_volume_relative(
            current_volume=500_000,
            avg_volume_50d=1_000_000,
        )
        assert result == 0.5

    def test_volume_equals_average(self) -> None:
        """Test volume equals average returns 1.0."""
        result = calculate_volume_relative(
            current_volume=1_000_000,
            avg_volume_50d=1_000_000,
        )
        assert result == 1.0

    def test_missing_avg_volume_returns_none(self) -> None:
        """Test missing average volume returns None."""
        result = calculate_volume_relative(
            current_volume=1_000_000,
            avg_volume_50d=None,
        )
        assert result is None

    def test_zero_avg_volume_returns_none(self) -> None:
        """Test zero average volume returns None (avoid division by zero)."""
        result = calculate_volume_relative(
            current_volume=1_000_000,
            avg_volume_50d=0,
        )
        assert result is None

    def test_negative_avg_volume_returns_none(self) -> None:
        """Test negative average volume returns None."""
        result = calculate_volume_relative(
            current_volume=1_000_000,
            avg_volume_50d=-100_000,
        )
        assert result is None

    def test_zero_current_volume(self) -> None:
        """Test zero current volume returns 0.0."""
        result = calculate_volume_relative(
            current_volume=0,
            avg_volume_50d=1_000_000,
        )
        assert result == 0.0

    def test_high_volume_spike(self) -> None:
        """Test high volume spike (10x average)."""
        result = calculate_volume_relative(
            current_volume=10_000_000,
            avg_volume_50d=1_000_000,
        )
        assert result == 10.0
