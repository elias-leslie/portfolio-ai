"""Tests for narrative generation and signal classification."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.watchlist.models import SignalClassification, SignalInputsDict, SignalStrength, SignalType


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
                signal_type=None,  # intentional: testing validation rejects None
                strength=SignalStrength(value=5),
                reasons=[],
            )

        # Test missing strength — deliberately pass None to verify validation
        with pytest.raises(ValidationError):
            SignalClassification(
                signal_type=SignalType.HOLD,
                strength=None,  # intentional: testing validation rejects None
                reasons=[],
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
        inputs: SignalInputsDict = {
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
        inputs: SignalInputsDict = {
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
        inputs: SignalInputsDict = {
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


class TestGenerateCompanyHealthBullets:
    """Tests for generate_company_health_bullets function."""

    def test_generate_company_health_bullets_excellent(self) -> None:
        """Test company health bullets for EXCELLENT company (NVDA-style)."""
        from app.watchlist.narrative import generate_company_health_bullets

        # NVDA-style fundamentals: High growth, high margins, strong balance sheet
        fundamentals = {
            "revenue_growth": 1.22,  # 122% YoY
            "profit_margin": 0.53,  # 53%
            "debt_to_equity": 0.15,  # Low debt
            "cash": 26_000_000_000,  # $26B cash
            "analyst_buy_pct": 0.94,  # 47 buy / 50 total
        }

        bullets = generate_company_health_bullets(fundamentals)

        # Should generate 3-5 bullets
        assert 3 <= len(bullets) <= 5
        # Should use checkmarks (✓ for positive)
        assert any("✓" in bullet for bullet in bullets)
        # Should mention revenue growth
        all_text = " ".join(bullets).lower()
        assert "revenue" in all_text or "growing" in all_text
        # Should mention profit margins
        assert "profit" in all_text or "margin" in all_text
        # Should mention balance sheet or cash
        assert any(term in all_text for term in ["cash", "balance", "debt"])
        # Should be plain language (no jargon)
        for bullet in bullets:
            assert "P/E" not in bullet
            assert "EBITDA" not in bullet

    def test_generate_company_health_bullets_weak(self) -> None:
        """Test company health bullets for WEAK company (negative indicators)."""
        from app.watchlist.narrative import generate_company_health_bullets

        # Weak fundamentals: Shrinking revenue, negative margins, high debt
        fundamentals = {
            "revenue_growth": -0.15,  # -15% decline
            "profit_margin": -0.05,  # -5% (unprofitable)
            "debt_to_equity": 2.5,  # Very high debt
            "cash": 500_000_000,  # Low cash
            "analyst_buy_pct": 0.20,  # Only 20% buy ratings
        }

        bullets = generate_company_health_bullets(fundamentals)

        # Should generate bullets
        assert len(bullets) > 0
        # Should use warning symbols (✗ or ⚠ for negative)
        assert any(symbol in bullet for symbol in ["✗", "⚠"] for bullet in bullets)
        # Should mention negative aspects
        all_text = " ".join(bullets).lower()
        assert any(
            term in all_text for term in ["shrinking", "declining", "negative", "unprofitable"]
        )

    def test_generate_company_health_bullets_good(self) -> None:
        """Test company health bullets for GOOD company (moderate metrics)."""
        from app.watchlist.narrative import generate_company_health_bullets

        # Good fundamentals: Moderate growth, decent margins, reasonable debt
        fundamentals = {
            "revenue_growth": 0.08,  # 8% growth
            "profit_margin": 0.12,  # 12% margin
            "debt_to_equity": 0.8,  # Moderate debt
            "cash": 5_000_000_000,  # $5B cash
            "analyst_buy_pct": 0.60,  # 60% buy ratings
        }

        bullets = generate_company_health_bullets(fundamentals)

        assert len(bullets) >= 3
        # Should have mix of positive indicators
        assert any("✓" in bullet for bullet in bullets)

    def test_generate_company_health_bullets_handles_missing_data(self) -> None:
        """Test that function handles missing fundamental data gracefully."""
        from app.watchlist.narrative import generate_company_health_bullets

        # Minimal data available
        fundamentals = {
            "revenue_growth": 0.10,
        }

        bullets = generate_company_health_bullets(fundamentals)

        # Should still generate at least one bullet
        assert len(bullets) >= 1
        # Should not crash or return empty list

    def test_generate_company_health_bullets_no_jargon(self) -> None:
        """Test that company health bullets contain no financial jargon."""
        from app.watchlist.narrative import generate_company_health_bullets

        fundamentals = {
            "revenue_growth": 0.25,
            "profit_margin": 0.18,
            "debt_to_equity": 0.4,
            "cash": 10_000_000_000,
            "analyst_buy_pct": 0.75,
        }

        bullets = generate_company_health_bullets(fundamentals)

        # Verify no jargon
        jargon_terms = ["P/E", "EBITDA", "EPS", "ROE", "ROI", "ROIC", "FCF"]
        all_text = " ".join(bullets)
        for jargon in jargon_terms:
            assert jargon not in all_text, f"Found jargon term: {jargon}"


class TestGenerateActionPlan:
    """Tests for generate_action_plan function."""

    def test_generate_action_plan_buy_signal(self) -> None:
        """Test action plan generation for BUY signal."""
        from app.watchlist.narrative import generate_action_plan

        # BUY signal with entry/stop/target calculated
        action_plan = generate_action_plan(
            signal_type="BUY",
            entry_price=202.0,
            stop_loss=195.0,
            profit_target=216.0,
        )

        # Should contain all three components
        all_text = action_plan.lower()
        assert "buy" in all_text or "entry" in all_text
        assert "stop" in all_text or "exit" in all_text
        assert "profit" in all_text or "target" in all_text
        # Should include prices
        assert "202" in action_plan
        assert "195" in action_plan
        assert "216" in action_plan
        # Should include percentage gain
        assert "%" in action_plan

    def test_generate_action_plan_hold_signal(self) -> None:
        """Test action plan generation for HOLD signal."""
        from app.watchlist.narrative import generate_action_plan

        # HOLD signal should have conditional entry
        action_plan = generate_action_plan(
            signal_type="HOLD",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=160.0,
        )

        all_text = action_plan.lower()
        # Should mention conditional entry or wait
        assert any(word in all_text for word in ["wait", "watch", "consider", "if"])

    def test_generate_action_plan_avoid_signal(self) -> None:
        """Test action plan generation for AVOID signal."""
        from app.watchlist.narrative import generate_action_plan

        # AVOID signal with None values
        action_plan = generate_action_plan(
            signal_type="AVOID",
            entry_price=None,
            stop_loss=None,
            profit_target=None,
        )

        all_text = action_plan.lower()
        # Should recommend avoiding
        assert any(word in all_text for word in ["avoid", "stay away", "pass", "skip"])

    def test_generate_action_plan_calculates_gain_percentage(self) -> None:
        """Test that action plan includes calculated gain percentage."""
        from app.watchlist.narrative import generate_action_plan

        # Entry $100, Target $110 → 10% gain
        action_plan = generate_action_plan(
            signal_type="BUY",
            entry_price=100.0,
            stop_loss=95.0,
            profit_target=110.0,
        )

        # Should show gain percentage
        assert "10" in action_plan and "%" in action_plan

    def test_generate_action_plan_no_jargon(self) -> None:
        """Test that action plan contains no trading jargon."""
        from app.watchlist.narrative import generate_action_plan

        action_plan = generate_action_plan(
            signal_type="BUY",
            entry_price=202.0,
            stop_loss=195.0,
            profit_target=216.0,
        )

        # Verify no jargon
        jargon_terms = ["ATR", "R:R", "risk/reward", "fibonacci", "pivot"]
        for jargon in jargon_terms:
            assert jargon.lower() not in action_plan.lower(), f"Found jargon term: {jargon}"


class TestGeneratePositionSizingText:
    """Tests for generate_position_sizing_text function."""

    def test_generate_position_sizing_text_valid_trade(self) -> None:
        """Test position sizing text for valid trade setup."""
        from app.watchlist.narrative import generate_position_sizing_text

        # Valid trade: Entry $202, Stop $195, Target $216, Risk $500 → 71 shares
        text = generate_position_sizing_text(
            shares=71,
            entry_price=202.0,
            stop_loss=195.0,
            profit_target=216.0,
        )

        all_text = text.lower()
        # Should include shares
        assert "71" in text
        # Should include investment amount
        assert "14" in text  # $14,342 investment
        # Should include potential gain
        assert "gain" in all_text or "profit" in all_text
        # Should include max loss
        assert "loss" in all_text or "risk" in all_text

    def test_generate_position_sizing_text_calculates_investment(self) -> None:
        """Test that position sizing calculates total investment."""
        from app.watchlist.narrative import generate_position_sizing_text

        # 100 shares @ $50 = $5,000 investment
        text = generate_position_sizing_text(
            shares=100,
            entry_price=50.0,
            stop_loss=48.0,
            profit_target=55.0,
        )

        # Should show $5,000 investment
        assert "5,000" in text or "5000" in text

    def test_generate_position_sizing_text_calculates_potential_gain(self) -> None:
        """Test that position sizing shows potential gain."""
        from app.watchlist.narrative import generate_position_sizing_text

        # 100 shares, Entry $50, Target $55 → Gain $500 (+10%)
        text = generate_position_sizing_text(
            shares=100,
            entry_price=50.0,
            stop_loss=48.0,
            profit_target=55.0,
        )

        # Should show $500 gain and +10%
        assert "500" in text
        assert "10" in text and "%" in text

    def test_generate_position_sizing_text_calculates_max_loss(self) -> None:
        """Test that position sizing shows maximum loss."""
        from app.watchlist.narrative import generate_position_sizing_text

        # 100 shares, Entry $50, Stop $48 → Loss $200 (-4%)
        text = generate_position_sizing_text(
            shares=100,
            entry_price=50.0,
            stop_loss=48.0,
            profit_target=55.0,
        )

        # Should show $200 loss and -4%
        assert "200" in text
        assert "4" in text and "%" in text

    def test_generate_position_sizing_text_handles_zero_shares(self) -> None:
        """Test position sizing when shares = 0 (stock too expensive)."""
        from app.watchlist.narrative import generate_position_sizing_text

        # 0 shares means stock is too expensive for risk budget
        text = generate_position_sizing_text(
            shares=0,
            entry_price=1000.0,
            stop_loss=998.0,
            profit_target=1010.0,
        )

        all_text = text.lower()
        # Should explain why 0 shares
        assert any(word in all_text for word in ["expensive", "budget", "risk"])

    def test_generate_position_sizing_text_no_jargon(self) -> None:
        """Test that position sizing text contains no trading jargon."""
        from app.watchlist.narrative import generate_position_sizing_text

        text = generate_position_sizing_text(
            shares=71,
            entry_price=202.0,
            stop_loss=195.0,
            profit_target=216.0,
        )

        # Verify no jargon
        jargon_terms = ["R:R", "risk/reward", "position size", "lot", "unit"]
        for jargon in jargon_terms:
            assert jargon.lower() not in text.lower(), f"Found jargon term: {jargon}"


class TestGenerateSpecialNotes:
    """Tests for generate_special_notes function."""

    def test_generate_special_notes_earnings_imminent(self) -> None:
        """Test special notes for earnings within 5 days (red warning)."""
        from app.watchlist.narrative import generate_special_notes

        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=8,
            earnings_days_away=2,
            company_health="EXCELLENT",
        )

        # Should include earnings warning
        all_text = notes.lower()
        assert "earnings" in all_text
        assert "2" in notes  # Days away
        # Should have red alert emoji or warning
        assert "🔴" in notes or "⚠" in notes

    def test_generate_special_notes_earnings_soon(self) -> None:
        """Test special notes for earnings within 6-14 days (caution)."""
        from app.watchlist.narrative import generate_special_notes

        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=7,
            earnings_days_away=10,
            company_health="GOOD",
        )

        # Should include earnings caution
        all_text = notes.lower()
        assert "earnings" in all_text
        assert "10" in notes

    def test_generate_special_notes_no_earnings_soon(self) -> None:
        """Test special notes when earnings >30 days away (no warning)."""
        from app.watchlist.narrative import generate_special_notes

        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=9,
            earnings_days_away=45,
            company_health="EXCELLENT",
        )

        # Should NOT include earnings warning
        all_text = notes.lower()
        # No urgent earnings warning
        assert "🔴" not in notes

    def test_generate_special_notes_why_this_works_buy_signal(self) -> None:
        """Test that WHY THIS WORKS section explains BUY logic."""
        from app.watchlist.narrative import generate_special_notes

        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=9,
            earnings_days_away=None,
            company_health="EXCELLENT",
        )

        all_text = notes.lower()
        # Should have WHY section
        assert "why" in all_text
        # Should mention technical + fundamentals
        assert any(word in all_text for word in ["technical", "setup", "fundamentals", "quality"])

    def test_generate_special_notes_why_this_works_hold_signal(self) -> None:
        """Test that WHY THIS WORKS section explains HOLD logic."""
        from app.watchlist.narrative import generate_special_notes

        notes = generate_special_notes(
            signal_type="HOLD",
            signal_strength=5,
            earnings_days_away=None,
            company_health="GOOD",
        )

        all_text = notes.lower()
        # Should explain why HOLD (mixed signals, waiting)
        assert any(word in all_text for word in ["mixed", "wait", "watch", "improve"])

    def test_generate_special_notes_avoid_signal(self) -> None:
        """Test special notes for AVOID signal."""
        from app.watchlist.narrative import generate_special_notes

        notes = generate_special_notes(
            signal_type="AVOID",
            signal_strength=2,
            earnings_days_away=3,
            company_health="WEAK",
        )

        all_text = notes.lower()
        # Should explain why AVOID
        assert any(word in all_text for word in ["risk", "avoid", "concern", "weak"])

    def test_generate_special_notes_with_specific_insights(self) -> None:
        """Test special notes with specific technical and fundamental insights."""
        from app.watchlist.narrative import generate_special_notes

        technicals = {
            "price": 105.0,
            "ema_20": 100.0,
            "rsi_14": 55.0,
        }
        fundamentals = {
            "revenue_growth": 0.25,
            "profit_margin": 0.20,
            "analyst_buy_pct": 0.80,
        }

        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=9,
            earnings_days_away=None,
            company_health="EXCELLENT",
            technicals=technicals,
            fundamentals=fundamentals,
        )

        # Should contain specific insights
        assert "Price above 20-day trend" in notes
        assert "RSI in healthy zone" in notes
        assert "High growth (+25% revenue)" in notes
        assert "Highly profitable (20% margin)" in notes
        assert "Analysts bullish (80% buy ratings)" in notes
