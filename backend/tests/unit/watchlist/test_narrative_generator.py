"""Unit tests for narrative_generator module (FEAT-029).

Tests the narrative generation functions that convert technical/fundamental data
into plain-language text for retail traders (zero-jargon approach).
"""

from __future__ import annotations

from app.watchlist.models import SignalClassification, SignalStrength, SignalType
from app.watchlist.narrative_generator import (
    generate_action_plan,
    generate_company_health_bullets,
    generate_headline,
    generate_position_sizing_text,
    generate_special_notes,
    generate_technical_bullets,
)


class TestGenerateHeadline:
    """Tests for generate_headline function."""

    def test_strong_buy_signal_high_strength(self) -> None:
        """Test STRONG BUY headline for high-strength signal."""
        classification = SignalClassification(
            signal_type=SignalType.BUY,
            strength=SignalStrength(value=9),
            reasons=["Uptrend confirmed", "Volume spike"],
        )
        headline = generate_headline(classification)
        assert headline.startswith("STRONG BUY")
        assert "Uptrend confirmed" in headline

    def test_buy_signal_medium_strength(self) -> None:
        """Test BUY headline for medium-strength signal."""
        classification = SignalClassification(
            signal_type=SignalType.BUY,
            strength=SignalStrength(value=6),
            reasons=["Price above average"],
        )
        headline = generate_headline(classification)
        assert headline.startswith("BUY")
        assert "Price above average" in headline

    def test_hold_signal(self) -> None:
        """Test HOLD headline."""
        classification = SignalClassification(
            signal_type=SignalType.HOLD,
            strength=SignalStrength(value=4),
            reasons=["Waiting for confirmation"],
        )
        headline = generate_headline(classification)
        assert headline.startswith("HOLD")
        assert "Waiting for confirmation" in headline

    def test_avoid_signal(self) -> None:
        """Test AVOID headline."""
        classification = SignalClassification(
            signal_type=SignalType.AVOID,
            strength=SignalStrength(value=2),
            reasons=["Multiple risk factors"],
        )
        headline = generate_headline(classification)
        assert headline.startswith("AVOID")

    def test_headline_removes_technical_details(self) -> None:
        """Test that headline strips technical details in parentheses."""
        classification = SignalClassification(
            signal_type=SignalType.BUY,
            strength=SignalStrength(value=8),
            reasons=["Breakout setup (RSI 65, MACD positive)"],
        )
        headline = generate_headline(classification)
        assert "Breakout setup" in headline
        assert "RSI" not in headline
        assert "MACD" not in headline


class TestGenerateTechnicalBullets:
    """Tests for generate_technical_bullets function."""

    def test_uptrend_bullets(self) -> None:
        """Test technical bullets for uptrend scenario."""
        inputs = {
            "price": 150.0,
            "ema_20": 145.0,
            "rsi_14": 55.0,
            "macd": 2.5,
            "volume": 10000000,
            "volume_avg_20": 8000000,
        }
        bullets = generate_technical_bullets(inputs)
        assert len(bullets) >= 3
        assert any("uptrend" in b.lower() for b in bullets)
        assert any("momentum" in b.lower() for b in bullets)
        assert any("volume" in b.lower() for b in bullets)

    def test_downtrend_bullets(self) -> None:
        """Test technical bullets for downtrend scenario."""
        inputs = {
            "price": 140.0,
            "ema_20": 150.0,
            "rsi_14": 30.0,
            "macd": -2.5,
            "volume": 5000000,
            "volume_avg_20": 8000000,
        }
        bullets = generate_technical_bullets(inputs)
        assert any("downtrend" in b.lower() or "below" in b.lower() for b in bullets)
        # RSI 30 triggers weakness message
        assert any("weakness" in b.lower() or "sellers" in b.lower() for b in bullets)
        assert any("sellers" in b.lower() or "negative" in b.lower() for b in bullets)

    def test_overbought_condition(self) -> None:
        """Test overbought RSI detection."""
        inputs = {
            "price": 155.0,
            "ema_20": 145.0,
            "rsi_14": 75.0,
            "macd": 1.0,
            "volume": 9000000,
            "volume_avg_20": 8000000,
        }
        bullets = generate_technical_bullets(inputs)
        assert any("extended" in b.lower() or "high" in b.lower() for b in bullets)

    def test_limited_data_fallback(self) -> None:
        """Test fallback when limited data available."""
        inputs = {"price": 150.0, "ema_20": 145.0}
        bullets = generate_technical_bullets(inputs)
        # Should still return at least 3 bullets with fallback message
        assert len(bullets) >= 3

    def test_caps_at_five_bullets(self) -> None:
        """Test that output is capped at 5 bullets."""
        inputs = {
            "price": 150.0,
            "ema_20": 145.0,
            "rsi_14": 55.0,
            "macd": 2.5,
            "volume": 15000000,
            "volume_avg_20": 8000000,
        }
        bullets = generate_technical_bullets(inputs)
        assert len(bullets) <= 5


class TestGenerateCompanyHealthBullets:
    """Tests for generate_company_health_bullets function."""

    def test_excellent_company(self) -> None:
        """Test bullets for excellent fundamentals."""
        fundamentals = {
            "revenue_growth": 0.30,  # 30%
            "profit_margin": 0.25,  # 25%
            "debt_to_equity": 0.3,
            "cash": 10_000_000_000,  # $10B
            "analyst_buy_pct": 0.80,  # 80%
        }
        bullets = generate_company_health_bullets(fundamentals)
        assert len(bullets) >= 3
        assert any("growing fast" in b.lower() or "30%" in b for b in bullets)
        assert any("profitable" in b.lower() or "25%" in b for b in bullets)
        assert any("strong balance sheet" in b.lower() or "$10b" in b.lower() for b in bullets)
        assert any("analysts love it" in b.lower() or "80%" in b for b in bullets)

    def test_weak_company(self) -> None:
        """Test bullets for weak fundamentals."""
        fundamentals = {
            "revenue_growth": -0.10,  # -10%
            "profit_margin": -0.05,  # -5%
            "debt_to_equity": 2.5,
            "analyst_buy_pct": 0.25,  # 25%
        }
        bullets = generate_company_health_bullets(fundamentals)
        assert any("shrinking" in b.lower() or "down" in b.lower() for b in bullets)
        assert any("unprofitable" in b.lower() or "losing" in b.lower() for b in bullets)
        assert any("high debt" in b.lower() for b in bullets)
        assert any("cautious" in b.lower() or "25%" in b for b in bullets)

    def test_moderate_company(self) -> None:
        """Test bullets for moderate fundamentals."""
        fundamentals = {
            "revenue_growth": 0.08,  # 8%
            "profit_margin": 0.12,  # 12%
            "debt_to_equity": 1.0,
        }
        bullets = generate_company_health_bullets(fundamentals)
        assert any("growth" in b.lower() or "8%" in b for b in bullets)
        assert any("profitable" in b.lower() or "12%" in b for b in bullets)

    def test_missing_data_fallback(self) -> None:
        """Test fallback when no fundamental data available."""
        fundamentals: dict[str, float] = {}
        bullets = generate_company_health_bullets(fundamentals)
        assert len(bullets) == 1
        assert "limited fundamental data" in bullets[0].lower()


class TestGenerateActionPlan:
    """Tests for generate_action_plan function."""

    def test_buy_signal_action_plan(self) -> None:
        """Test action plan for BUY signal."""
        plan = generate_action_plan(
            signal_type="BUY",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=165.0,
        )
        assert "ACTION PLAN" in plan
        assert "$150.00" in plan
        assert "$145.00" in plan
        assert "$165.00" in plan
        assert "%" in plan  # Contains percentage calculations

    def test_hold_signal_action_plan(self) -> None:
        """Test action plan for HOLD signal."""
        plan = generate_action_plan(
            signal_type="HOLD",
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=165.0,
        )
        assert "WATCH AND WAIT" in plan
        assert "wait for stronger confirmation" in plan.lower()

    def test_avoid_signal_action_plan(self) -> None:
        """Test action plan for AVOID signal."""
        plan = generate_action_plan(
            signal_type="AVOID",
            entry_price=None,
            stop_loss=None,
            profit_target=None,
        )
        assert "avoid this trade" in plan.lower()
        assert "risk factors" in plan.lower()

    def test_missing_price_data(self) -> None:
        """Test action plan when price data is missing."""
        plan = generate_action_plan(
            signal_type="BUY",
            entry_price=None,
            stop_loss=145.0,
            profit_target=165.0,
        )
        assert "unable to calculate" in plan.lower()


class TestGeneratePositionSizing:
    """Tests for generate_position_sizing_text function."""

    def test_normal_position_sizing(self) -> None:
        """Test position sizing calculation for normal scenario."""
        text = generate_position_sizing_text(
            shares=100,
            entry_price=150.0,
            stop_loss=145.0,
            profit_target=165.0,
        )
        assert "100 shares" in text
        assert "$15,000" in text  # 100 * 150
        assert "potential gain" in text.lower()
        assert "maximum loss" in text.lower()

    def test_zero_shares_warning(self) -> None:
        """Test warning when shares = 0 (too expensive)."""
        text = generate_position_sizing_text(
            shares=0,
            entry_price=5000.0,
            stop_loss=4800.0,
            profit_target=5500.0,
        )
        assert "too expensive" in text.lower()
        assert "risk budget" in text.lower()

    def test_large_position(self) -> None:
        """Test formatting for large position size."""
        text = generate_position_sizing_text(
            shares=1000,
            entry_price=50.0,
            stop_loss=48.0,
            profit_target=55.0,
        )
        assert "1,000 shares" in text  # Comma formatting
        assert "$50,000" in text


class TestGenerateSpecialNotes:
    """Tests for generate_special_notes function."""

    def test_imminent_earnings_warning(self) -> None:
        """Test red alert for imminent earnings (0-5 days)."""
        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=8,
            earnings_days_away=3,
            company_health="EXCELLENT",
        )
        assert "EARNINGS IN 3 DAYS" in notes
        assert "high volatility" in notes.lower()

    def test_upcoming_earnings_caution(self) -> None:
        """Test caution for upcoming earnings (6-14 days)."""
        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=7,
            earnings_days_away=10,
            company_health="GOOD",
        )
        assert "10 days away" in notes
        assert "increased volatility" in notes.lower()

    def test_why_this_works_buy_signal(self) -> None:
        """Test WHY THIS WORKS section for BUY signal."""
        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=8,
            earnings_days_away=None,
            company_health="EXCELLENT",
            technicals={"price": 150.0, "ema_20": 145.0, "rsi_14": 55.0},
            fundamentals={"revenue_growth": 0.25, "profit_margin": 0.20, "analyst_buy_pct": 0.75},
        )
        assert "WHY THIS WORKS" in notes
        assert "bullish" in notes.lower() or "price above" in notes.lower()

    def test_why_hold(self) -> None:
        """Test WHY HOLD section."""
        notes = generate_special_notes(
            signal_type="HOLD",
            signal_strength=5,
            earnings_days_away=None,
            company_health="GOOD",
        )
        assert "WHY HOLD" in notes
        assert "mixed technical signals" in notes.lower()

    def test_why_avoid(self) -> None:
        """Test WHY AVOID section."""
        notes = generate_special_notes(
            signal_type="AVOID",
            signal_strength=2,
            earnings_days_away=None,
            company_health="WEAK",
        )
        assert "WHY AVOID" in notes
        assert "risk factors" in notes.lower()

    def test_gap_warning_low_confidence(self) -> None:
        """Test data gap warning for LOW confidence."""
        gap_result = {
            "confidence_level": "LOW",
            "readiness_score": 45.0,
            "missing_capabilities": [
                "Options Flow Analysis (GAP-031)",
                "Insider Transactions (GAP-006)",
                "Institutional Ownership (GAP-007)",
            ],
        }
        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=7,
            earnings_days_away=None,
            company_health="GOOD",
            gap_result=gap_result,
        )
        assert "DATA GAPS DETECTED" in notes
        assert "45%" in notes
        assert "Options Flow Analysis" in notes

    def test_gap_warning_medium_confidence(self) -> None:
        """Test data gap notice for MEDIUM confidence."""
        gap_result = {
            "confidence_level": "MEDIUM",
            "readiness_score": 65.0,
            "missing_capabilities": ["Insider Transactions (GAP-006)"],
        }
        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=7,
            earnings_days_away=None,
            company_health="GOOD",
            gap_result=gap_result,
        )
        assert "MODERATE DATA COVERAGE" in notes
        assert "65%" in notes
        assert "Insider Transactions" in notes

    def test_no_special_notes_when_all_clear(self) -> None:
        """Test empty notes when no special conditions present."""
        gap_result = {
            "confidence_level": "HIGH",
            "readiness_score": 85.0,
            "missing_capabilities": [],
        }
        notes = generate_special_notes(
            signal_type="BUY",
            signal_strength=8,
            earnings_days_away=None,
            company_health="EXCELLENT",
            gap_result=gap_result,
        )
        # Should only have WHY THIS WORKS section (no warnings)
        assert "WHY THIS WORKS" in notes
        assert "DATA GAPS" not in notes
        assert "EARNINGS" not in notes
