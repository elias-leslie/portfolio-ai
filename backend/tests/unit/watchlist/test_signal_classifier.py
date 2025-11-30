"""Unit tests for signal_classifier module (Task 0074).

Tests the new graded confidence scoring system:
- Fundamental component scoring (-3 to +5 points)
- Analyst component scoring (0 to +5 points)
- Continuous news sentiment scoring (0 to +5 points)
- Integrated signal classification
"""

from __future__ import annotations

import pytest

from app.watchlist.signal_classifier import (
    _calculate_analyst_component_score,
    _calculate_fundamental_component_score,
    _calculate_news_sentiment_score,
    _calculate_signal_strength,
    classify_signal,
)
from app.watchlist.models import SignalType


class TestFundamentalComponentScore:
    """Tests for _calculate_fundamental_component_score (Task 0074 - Task 1)."""

    def test_excellent_fundamentals_max_score(self) -> None:
        """Test that excellent fundamentals (high margins, growth, low debt) get max score."""
        score, reasons = _calculate_fundamental_component_score(
            profit_margin=0.35,  # 35% = +2
            revenue_growth=0.25,  # 25% = +2
            debt_to_equity=0.3,  # Low debt = +1
        )
        assert score == 5  # Maximum score
        assert len(reasons) == 3
        assert any("Very profitable" in r for r in reasons)
        assert any("Strong growth" in r for r in reasons)
        assert any("Low debt" in r for r in reasons)

    def test_good_fundamentals_medium_score(self) -> None:
        """Test that good fundamentals (moderate margins, growth) get medium score."""
        score, reasons = _calculate_fundamental_component_score(
            profit_margin=0.15,  # 15% = +1
            revenue_growth=0.10,  # 10% = +1
            debt_to_equity=1.0,  # Moderate debt = 0
        )
        assert score == 2
        assert len(reasons) == 2  # Two positive reasons
        assert any("Profitable" in r for r in reasons)
        assert any("Growing" in r for r in reasons)

    def test_weak_fundamentals_negative_score(self) -> None:
        """Test that weak fundamentals (negative margins, debt) get negative score."""
        score, reasons = _calculate_fundamental_component_score(
            profit_margin=-0.05,  # Negative = -1
            revenue_growth=-0.10,  # Negative = -1
            debt_to_equity=2.0,  # High debt = -1
        )
        assert score == -3  # Minimum score
        assert len(reasons) == 3
        assert any("Unprofitable" in r for r in reasons)
        assert any("Revenue declining" in r for r in reasons)
        assert any("High debt" in r for r in reasons)

    def test_none_values_zero_contribution(self) -> None:
        """Test that None values contribute 0 points."""
        score, reasons = _calculate_fundamental_component_score(
            profit_margin=None,
            revenue_growth=None,
            debt_to_equity=None,
        )
        assert score == 0
        assert len(reasons) == 0

    def test_partial_data(self) -> None:
        """Test with only some data available."""
        score, reasons = _calculate_fundamental_component_score(
            profit_margin=0.25,  # 25% = +2
            revenue_growth=None,
            debt_to_equity=0.4,  # Low debt = +1
        )
        assert score == 3
        assert len(reasons) == 2


class TestAnalystComponentScore:
    """Tests for _calculate_analyst_component_score (Task 0074 - Task 2)."""

    def test_strong_buy_consensus_max_score(self) -> None:
        """Test that strong buy consensus gets max score."""
        score, reasons = _calculate_analyst_component_score(
            recommendation_mean=1.8,  # Strong buy = +3
            analyst_buy_pct=0.75,  # >70% = +2
        )
        assert score == 5  # Maximum score
        assert len(reasons) == 2
        assert any("strong buy" in r.lower() for r in reasons)
        assert any("75%" in r for r in reasons)

    def test_buy_consensus_medium_score(self) -> None:
        """Test that buy consensus gets medium score."""
        score, reasons = _calculate_analyst_component_score(
            recommendation_mean=2.3,  # Buy = +2
            analyst_buy_pct=0.60,  # 50-70% = +1
        )
        assert score == 3
        assert len(reasons) == 2

    def test_hold_consensus_low_score(self) -> None:
        """Test that hold consensus gets low score."""
        score, reasons = _calculate_analyst_component_score(
            recommendation_mean=2.8,  # Hold = +1
            analyst_buy_pct=0.40,  # <50% = 0
        )
        assert score == 1
        assert len(reasons) == 1

    def test_sell_consensus_zero_score(self) -> None:
        """Test that sell consensus gets zero score."""
        score, reasons = _calculate_analyst_component_score(
            recommendation_mean=4.0,  # Sell = 0
            analyst_buy_pct=0.20,  # <50% = 0
        )
        assert score == 0
        assert len(reasons) == 0

    def test_none_values_zero_contribution(self) -> None:
        """Test that None values contribute 0 points."""
        score, reasons = _calculate_analyst_component_score(
            recommendation_mean=None,
            analyst_buy_pct=None,
        )
        assert score == 0
        assert len(reasons) == 0


class TestNewsSentimentScore:
    """Tests for _calculate_news_sentiment_score (Task 0074 - Task 4)."""

    def test_strong_positive_sentiment(self) -> None:
        """Test strong positive sentiment (+0.8 → ~4.5 points)."""
        score, reasons = _calculate_news_sentiment_score(0.8)
        assert score == 4  # (0.8 + 1.0) / 2.0 * 5.0 = 4.5 → 4
        assert len(reasons) == 1
        assert "positive" in reasons[0].lower()

    def test_weak_positive_sentiment(self) -> None:
        """Test weak positive sentiment (+0.2 → ~3.0 points)."""
        score, reasons = _calculate_news_sentiment_score(0.2)
        assert score == 3  # (0.2 + 1.0) / 2.0 * 5.0 = 3.0
        assert len(reasons) == 1
        assert "positive" in reasons[0].lower()

    def test_neutral_sentiment(self) -> None:
        """Test neutral sentiment (0.0 → ~2.5 points)."""
        score, reasons = _calculate_news_sentiment_score(0.0)
        assert score == 2  # (0.0 + 1.0) / 2.0 * 5.0 = 2.5 → 2
        assert len(reasons) == 0  # No reason for neutral

    def test_negative_sentiment(self) -> None:
        """Test negative sentiment (-0.5 → ~1.25 points)."""
        score, reasons = _calculate_news_sentiment_score(-0.5)
        assert score == 1  # (-0.5 + 1.0) / 2.0 * 5.0 = 1.25 → 1
        assert len(reasons) == 1
        assert "negative" in reasons[0].lower()

    def test_very_negative_sentiment(self) -> None:
        """Test very negative sentiment (-1.0 → 0 points)."""
        score, reasons = _calculate_news_sentiment_score(-1.0)
        assert score == 0
        assert len(reasons) == 1
        assert "negative" in reasons[0].lower()


class TestSignalStrengthCalculation:
    """Tests for _calculate_signal_strength with expanded range (Task 0074)."""

    def test_max_confirmations_max_strength(self) -> None:
        """Test that max confirmations (21) gives max strength (10)."""
        strength = _calculate_signal_strength(21)
        assert strength == 10

    def test_min_confirmations_zero_strength(self) -> None:
        """Test that min confirmations (-3) gives zero strength."""
        strength = _calculate_signal_strength(-3)
        assert strength == 0

    def test_medium_confirmations_medium_strength(self) -> None:
        """Test that medium confirmations (10) gives strength ~5."""
        strength = _calculate_signal_strength(10)
        # (10 + 3) / 2.4 = 5.4 → 5
        assert strength == 5

    def test_negative_beyond_range_clamped(self) -> None:
        """Test that values below -3 are clamped to 0."""
        strength = _calculate_signal_strength(-10)
        assert strength == 0

    def test_beyond_max_clamped(self) -> None:
        """Test that values above 21 are clamped to 10."""
        strength = _calculate_signal_strength(30)
        assert strength == 10


class TestClassifySignalIntegration:
    """Integration tests for classify_signal with new scoring (Task 0074)."""

    def test_buy_signal_excellent_fundamentals(self) -> None:
        """Test BUY signal with excellent fundamentals gets high strength."""
        result = classify_signal({
            "price": 150.0,
            "ema_20": 145.0,
            "sma_5": 148.0,
            "sma_5_prev": 146.0,
            "rsi_14": 55.0,
            "macd": 2.5,
            "volume": 10000000,
            "volume_avg_20": 8000000,
            "company_health": "EXCELLENT",
            "news_sentiment": 0.5,
            # Excellent fundamentals
            "profit_margin": 0.35,
            "revenue_growth": 0.30,
            "debt_to_equity": 0.3,
            # Strong analyst support
            "recommendation_mean": 1.8,
            "analyst_buy_pct": 0.80,
        })
        assert result.signal_type == SignalType.BUY
        assert result.strength.value >= 8  # High strength
        # Check for fundamental reasons
        assert any("profitable" in r.lower() for r in result.reasons)
        assert any("analyst" in r.lower() for r in result.reasons)

    def test_buy_signal_good_fundamentals(self) -> None:
        """Test BUY signal with good (not excellent) fundamentals gets medium strength."""
        result = classify_signal({
            "price": 150.0,
            "ema_20": 145.0,
            "sma_5": 148.0,
            "sma_5_prev": 146.0,
            "rsi_14": 55.0,
            "macd": 2.5,
            "volume": 10000000,
            "volume_avg_20": 8000000,
            "company_health": "GOOD",
            "news_sentiment": 0.3,
            # Good but not excellent fundamentals
            "profit_margin": 0.12,
            "revenue_growth": 0.10,
            "debt_to_equity": 1.0,
            # Moderate analyst support
            "recommendation_mean": 2.3,
            "analyst_buy_pct": 0.60,
        })
        assert result.signal_type == SignalType.BUY
        # Strength should be lower than excellent
        assert 5 <= result.strength.value <= 8

    def test_hold_signal_weak_fundamentals(self) -> None:
        """Test HOLD signal with weak fundamentals."""
        result = classify_signal({
            "price": 150.0,
            "ema_20": 145.0,
            "sma_5": 148.0,
            "sma_5_prev": 146.0,
            "rsi_14": 55.0,
            "macd": 0.5,
            "volume": 5000000,
            "volume_avg_20": 8000000,  # Below average
            "company_health": "WEAK",
            "news_sentiment": -0.2,
            # Weak fundamentals
            "profit_margin": 0.02,
            "revenue_growth": -0.05,
            "debt_to_equity": 2.5,
            # No analyst support
            "recommendation_mean": 3.5,
            "analyst_buy_pct": 0.30,
        })
        assert result.signal_type == SignalType.HOLD
        assert result.strength.value <= 5

    def test_signal_with_no_fundamental_data(self) -> None:
        """Test signal classification works when fundamental data is missing."""
        result = classify_signal({
            "price": 150.0,
            "ema_20": 145.0,
            "sma_5": 148.0,
            "sma_5_prev": 146.0,
            "rsi_14": 55.0,
            "macd": 2.5,
            "volume": 10000000,
            "volume_avg_20": 8000000,
            "company_health": "GOOD",
            "news_sentiment": 0.3,
            # No fundamental data
            "profit_margin": None,
            "revenue_growth": None,
            "debt_to_equity": None,
            "recommendation_mean": None,
            "analyst_buy_pct": None,
        })
        # Should still work, just with lower score
        assert result.signal_type in (SignalType.BUY, SignalType.HOLD)
        # Score should be lower without fundamental boost
        assert result.strength.value <= 6


class TestAvoidSignal:
    """Tests for AVOID signal detection (unchanged from original)."""

    def test_avoid_signal_multiple_negatives(self) -> None:
        """Test AVOID signal when multiple negative indicators present."""
        result = classify_signal({
            "price": 140.0,  # Below EMA
            "ema_20": 150.0,
            "sma_5": 145.0,
            "sma_5_prev": 148.0,  # Declining
            "rsi_14": 25.0,
            "macd": -5.0,
            "volume": 5000000,
            "volume_avg_20": 8000000,
            "company_health": "WEAK",
            "news_sentiment": -0.5,  # Significantly negative
        })
        assert result.signal_type == SignalType.AVOID
