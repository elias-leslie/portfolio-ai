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


class TestNarrativeTemplates:
    """Tests for narrative template system."""

    def test_narrative_templates_exist(self) -> None:
        """Test that NARRATIVE_TEMPLATES dictionary exists."""
        from app.watchlist.narrative import NARRATIVE_TEMPLATES

        assert isinstance(NARRATIVE_TEMPLATES, dict)
        assert len(NARRATIVE_TEMPLATES) > 0

    def test_narrative_template_uptrend(self) -> None:
        """Test uptrend template translates to plain language."""
        from app.watchlist.narrative import NARRATIVE_TEMPLATES

        template = NARRATIVE_TEMPLATES.get("uptrend")
        assert template is not None
        assert "uptrend" in template.lower() or "rising" in template.lower()
        # Verify no jargon
        assert "EMA" not in template
        assert "SMA" not in template

    def test_narrative_template_no_jargon(self) -> None:
        """Test that templates contain no trader jargon."""
        from app.watchlist.narrative import NARRATIVE_TEMPLATES

        jargon_terms = ["RSI", "MACD", "EMA", "SMA", "ATR", "VWAP"]
        for key, template in NARRATIVE_TEMPLATES.items():
            for jargon in jargon_terms:
                assert jargon not in template, f"Template '{key}' contains jargon: {jargon}"

    def test_narrative_template_coverage(self) -> None:
        """Test that key templates exist."""
        from app.watchlist.narrative import NARRATIVE_TEMPLATES

        required_keys = [
            "uptrend",
            "pullback",
            "momentum_positive",
            "volume_high",
            "overbought",
            "oversold",
        ]
        for key in required_keys:
            assert key in NARRATIVE_TEMPLATES, f"Missing template: {key}"


class TestGenerateHeadline:
    """Tests for generate_headline function."""

    def test_generate_headline_buy_signal(self) -> None:
        """Test headline generation for BUY signal."""
        from app.watchlist.narrative import SignalStrength, SignalType, generate_headline

        classification = SignalClassification(
            signal_type=SignalType.BUY,
            strength=SignalStrength(value=9),
            reasons=[
                "Price > 20-day EMA (uptrend)",
                "RSI at 55 (healthy)",
                "MACD positive (momentum)",
            ],
        )

        headline = generate_headline(classification)

        # Should follow format: "{SIGNAL_TYPE} - {reason}"
        assert "BUY" in headline
        assert " - " in headline
        # Should extract a primary reason
        assert len(headline) > 10  # Not empty

    def test_generate_headline_avoid_signal(self) -> None:
        """Test headline generation for AVOID signal."""
        from app.watchlist.narrative import generate_headline

        classification = SignalClassification(
            signal_type=SignalType.AVOID,
            strength=SignalStrength(value=2),
            reasons=["Price below 20-day EMA (downtrend)", "News sentiment negative"],
        )

        headline = generate_headline(classification)

        assert "AVOID" in headline
        assert " - " in headline

    def test_generate_headline_hold_signal(self) -> None:
        """Test headline generation for HOLD signal."""
        from app.watchlist.narrative import generate_headline

        classification = SignalClassification(
            signal_type=SignalType.HOLD,
            strength=SignalStrength(value=5),
            reasons=["Mixed signals"],
        )

        headline = generate_headline(classification)

        assert "HOLD" in headline
        assert " - " in headline


class TestGenerateTechnicalBullets:
    """Tests for generate_technical_bullets function."""

    def test_generate_technical_bullets_uptrend(self) -> None:
        """Test technical bullet generation for uptrend setup."""
        from app.watchlist.narrative import generate_technical_bullets

        inputs = {
            "price": 202.0,
            "ema_20": 195.0,
            "rsi_14": 55.0,
            "macd": 2.5,
            "volume": 100_000_000,
            "volume_avg_20": 80_000_000,
        }

        bullets = generate_technical_bullets(inputs)

        # Should generate 3-5 bullets
        assert 3 <= len(bullets) <= 5
        # Should be plain language (no jargon)
        for bullet in bullets:
            assert "EMA" not in bullet
            assert "RSI" not in bullet
            assert "MACD" not in bullet
        # Should mention uptrend/momentum/volume
        all_text = " ".join(bullets).lower()
        assert any(term in all_text for term in ["uptrend", "rising", "momentum", "volume"])

    def test_generate_technical_bullets_downtrend(self) -> None:
        """Test technical bullet generation for downtrend setup."""
        from app.watchlist.narrative import generate_technical_bullets

        inputs = {
            "price": 180.0,
            "ema_20": 195.0,
            "rsi_14": 40.0,
            "macd": -1.5,
            "volume": 50_000_000,
            "volume_avg_20": 80_000_000,
        }

        bullets = generate_technical_bullets(inputs)

        assert len(bullets) > 0
        # Should mention downtrend or weakness
        all_text = " ".join(bullets).lower()
        assert any(term in all_text for term in ["downtrend", "falling", "weak", "below"])


class TestClassifyTradingStyle:
    """Tests for classify_trading_style function."""

    def test_classify_index_style(self) -> None:
        """Test Index style classification for ETF symbols."""
        from app.watchlist.narrative import classify_trading_style

        # SPY should be classified as Index
        result = classify_trading_style(
            symbol="SPY",
            signal_strength=5,
            signal_type="HOLD",
            rsi_14=50.0,
            earnings_days_away=None,
        )

        assert result["style"] == "Index"
        assert result["confidence"] >= 9  # Very confident for hardcoded list
        assert "indefinitely" in result["holding_period"].lower()
        assert result["risk_level"] == "Low"

    def test_classify_event_style(self) -> None:
        """Test Event style classification for earnings proximity."""
        from app.watchlist.narrative import classify_trading_style

        # Stock with earnings in 3 days should be Event style
        result = classify_trading_style(
            symbol="NVDA",
            signal_strength=6,
            signal_type="BUY",
            rsi_14=50.0,
            earnings_days_away=3,
        )

        assert result["style"] == "Event"
        assert result["confidence"] >= 7
        assert (
            "days" in result["holding_period"].lower()
            or "weeks" in result["holding_period"].lower()
        )
        assert result["risk_level"] == "High"

    def test_classify_swing_style_oversold(self) -> None:
        """Test Swing style classification for RSI in oversold reversal zone."""
        from app.watchlist.narrative import classify_trading_style

        # RSI in 30-40 range (oversold reversal zone)
        result = classify_trading_style(
            symbol="AAPL",
            signal_strength=5,
            signal_type="HOLD",
            rsi_14=35.0,
            earnings_days_away=None,
        )

        assert result["style"] == "Swing"
        assert result["confidence"] >= 6
        assert "week" in result["holding_period"].lower()
        assert result["risk_level"] == "Medium"

    def test_classify_swing_style_overbought(self) -> None:
        """Test Swing style classification for RSI in overbought reversal zone."""
        from app.watchlist.narrative import classify_trading_style

        # RSI in 60-70 range (overbought reversal zone)
        result = classify_trading_style(
            symbol="GOOGL",
            signal_strength=4,
            signal_type="HOLD",
            rsi_14=65.0,
            earnings_days_away=None,
        )

        assert result["style"] == "Swing"
        assert result["confidence"] >= 6
        assert "week" in result["holding_period"].lower()
        assert result["risk_level"] == "Medium"

    def test_classify_trend_style(self) -> None:
        """Test Trend style classification for strong BUY signals."""
        from app.watchlist.narrative import classify_trading_style

        # Strong BUY signal (strength >= 8)
        result = classify_trading_style(
            symbol="TSLA",
            signal_strength=9,
            signal_type="BUY",
            rsi_14=55.0,
            earnings_days_away=None,
        )

        assert result["style"] == "Trend"
        assert result["confidence"] >= 8
        assert "month" in result["holding_period"].lower()
        assert result["risk_level"] == "Medium"

    def test_classify_value_style_default(self) -> None:
        """Test Value style classification as default fallback."""
        from app.watchlist.narrative import classify_trading_style

        # Doesn't match any other criteria → Value
        result = classify_trading_style(
            symbol="MSFT",
            signal_strength=5,
            signal_type="HOLD",
            rsi_14=50.0,
            earnings_days_away=None,
        )

        assert result["style"] == "Value"
        assert result["confidence"] >= 5
        assert "month" in result["holding_period"].lower()
        assert result["risk_level"] in ("Medium", "Medium-Low")

    def test_classify_trading_style_priority_index_first(self) -> None:
        """Test that Index classification takes priority over Event."""
        from app.watchlist.narrative import classify_trading_style

        # VOO with earnings in 3 days → should still be Index
        result = classify_trading_style(
            symbol="VOO",
            signal_strength=6,
            signal_type="BUY",
            rsi_14=50.0,
            earnings_days_away=3,
        )

        assert result["style"] == "Index"

    def test_classify_trading_style_priority_event_over_swing(self) -> None:
        """Test that Event classification takes priority over Swing."""
        from app.watchlist.narrative import classify_trading_style

        # Earnings in 2 days + RSI=35 → should be Event
        result = classify_trading_style(
            symbol="META",
            signal_strength=5,
            signal_type="HOLD",
            rsi_14=35.0,
            earnings_days_away=2,
        )

        assert result["style"] == "Event"
