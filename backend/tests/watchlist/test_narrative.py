"""Tests for narrative generation and signal classification."""

import pytest
from pydantic import ValidationError

from app.watchlist.models import SignalClassification, SignalStrength, SignalType


class TestSignalType:
    """Tests for SignalType enum."""

    def test_signal_type_values(self) -> None:
        """Test that SignalType has BUY, HOLD, AVOID values."""
        assert SignalType.BUY.value == "BUY"
        assert SignalType.HOLD.value == "HOLD"
        assert SignalType.AVOID.value == "AVOID"

    def test_signal_type_members(self) -> None:
        """Test that all expected members exist."""
        assert hasattr(SignalType, "BUY")
        assert hasattr(SignalType, "HOLD")
        assert hasattr(SignalType, "AVOID")


class TestSignalStrength:
    """Tests for SignalStrength class."""

    def test_signal_strength_valid_values(self) -> None:
        """Test SignalStrength accepts values 0-10."""
        for i in range(11):  # 0-10 inclusive
            strength = SignalStrength(value=i)
            assert strength.value == i

    def test_signal_strength_below_range(self) -> None:
        """Test SignalStrength rejects values below 0."""
        with pytest.raises(ValidationError):
            SignalStrength(value=-1)

    def test_signal_strength_above_range(self) -> None:
        """Test SignalStrength rejects values above 10."""
        with pytest.raises(ValidationError):
            SignalStrength(value=11)


class TestSignalClassification:
    """Tests for SignalClassification model."""

    def test_signal_classification_creation(self) -> None:
        """Test creating a SignalClassification with all fields."""
        classification = SignalClassification(
            signal_type=SignalType.BUY,
            strength=SignalStrength(value=9),
            reasons=[
                "Price > 20-day EMA (uptrend)",
                "RSI at 55 (healthy)",
                "MACD positive (momentum)",
            ],
        )
        assert classification.signal_type == SignalType.BUY
        assert classification.strength.value == 9
        assert len(classification.reasons) == 3

    def test_signal_classification_validation(self) -> None:
        """Test that SignalClassification validates required fields."""
        # Test missing signal_type
        with pytest.raises(ValidationError):
            SignalClassification(
                signal_type=None,  # type: ignore
                strength=SignalStrength(value=5),
                reasons=[],
            )

        # Test missing strength
        with pytest.raises(ValidationError):
            SignalClassification(
                signal_type=SignalType.HOLD,
                strength=None,
                reasons=[],  # type: ignore
            )


class TestClassifySignal:
    """Tests for classify_signal function."""

    def test_classify_buy_signal_nvda_style(self) -> None:
        """Test BUY signal classification for NVDA-style setup.

        NVDA example: Strong uptrend + healthy RSI + positive momentum + good volume
        + excellent company health + positive news sentiment.
        """
        from app.watchlist.narrative import classify_signal

        # NVDA-style inputs: All indicators positive
        inputs = {
            "price": 202.0,
            "ema_20": 195.0,  # Price > EMA (uptrend)
            "rsi_14": 55.0,  # RSI between 30-70 (healthy)
            "macd": 2.5,  # MACD > 0 (positive momentum)
            "volume": 100_000_000,
            "volume_avg_20": 80_000_000,  # Volume >= 70% of avg (strong)
            "company_health": "EXCELLENT",
            "news_sentiment": 0.4,  # >= 0.2 (positive)
        }

        result = classify_signal(inputs)

        # Should classify as BUY with high strength (9/10)
        assert result.signal_type == SignalType.BUY
        assert result.strength.value == 9

        # Should have reasons explaining the classification
        assert len(result.reasons) > 0
        assert any("uptrend" in reason.lower() for reason in result.reasons)

    def test_classify_avoid_signal_meta_style(self) -> None:
        """Test AVOID signal classification for META-style setup.

        META example: Downtrend + negative news + weak company + earnings risk.
        """
        from app.watchlist.narrative import classify_signal

        # META-style inputs: Multiple negative indicators
        inputs = {
            "price": 180.0,
            "ema_20": 195.0,  # Price < EMA (downtrend)
            "sma_5": 185.0,  # 5-day SMA
            "sma_5_prev": 190.0,  # 5-day SMA declining
            "rsi_14": 40.0,  # Neutral RSI
            "macd": -1.5,  # MACD negative
            "volume": 50_000_000,
            "volume_avg_20": 80_000_000,  # Low volume
            "company_health": "WEAK",
            "news_sentiment": -0.5,  # Significantly negative
            "earnings_days_away": 3,  # Earnings in 3 days (high risk)
        }

        result = classify_signal(inputs)

        # Should classify as AVOID with low strength (2/10)
        assert result.signal_type == SignalType.AVOID
        assert result.strength.value == 2

        # Should have reasons explaining the classification
        assert len(result.reasons) > 0
        assert any(
            "downtrend" in reason.lower() or "below" in reason.lower() for reason in result.reasons
        )

    def test_classify_hold_signal_mixed_conditions(self) -> None:
        """Test HOLD signal classification for mixed-conditions setup.

        Mixed example: Some positive indicators, some negative, or RSI overbought.
        """
        from app.watchlist.narrative import classify_signal

        # Mixed conditions: Price in uptrend but RSI overbought
        inputs = {
            "price": 210.0,
            "ema_20": 200.0,  # Price > EMA (uptrend)
            "rsi_14": 75.0,  # RSI > 70 (overbought)
            "macd": 1.0,  # MACD positive
            "volume": 60_000_000,
            "volume_avg_20": 80_000_000,  # Lower volume
            "company_health": "GOOD",
            "news_sentiment": 0.1,  # Slightly positive but not >= 0.2
        }

        result = classify_signal(inputs)

        # Should classify as HOLD with moderate strength (4-6/10)
        assert result.signal_type == SignalType.HOLD
        assert 4 <= result.strength.value <= 6

        # Should have some reasons
        assert len(result.reasons) > 0
