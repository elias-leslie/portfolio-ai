"""Tests for options flow scoring integration (GAP-031).

Tests cover:
- Options flow score calculation
- Sector activity detection
- Integration with signal classifier
"""

from __future__ import annotations

from app.watchlist.signal_classifier import (
    _calculate_options_flow_score,
    classify_signal,
)


class TestCalculateOptionsFlowScore:
    """Tests for options flow score calculation."""

    def test_no_options_data_returns_zero(self) -> None:
        """Missing options data contributes 0 points."""
        score, reasons = _calculate_options_flow_score(
            options_call_pct=None,
            options_near_term_pct=None,
            ticker_in_active_sector=None,
        )
        assert score == 0
        assert reasons == []

    def test_strong_bullish_options_flow(self) -> None:
        """58%+ calls gives maximum 3 points."""
        score, reasons = _calculate_options_flow_score(
            options_call_pct=0.60,
            options_near_term_pct=0.50,
            ticker_in_active_sector=False,
        )
        assert score == 3
        assert len(reasons) == 1
        assert "bullish" in reasons[0].lower()
        assert "60%" in reasons[0]

    def test_moderate_bullish_options_flow(self) -> None:
        """55-58% calls gives 2 points."""
        score, reasons = _calculate_options_flow_score(
            options_call_pct=0.56,
            options_near_term_pct=0.50,
            ticker_in_active_sector=False,
        )
        assert score == 2
        assert "moderately bullish" in reasons[0].lower()

    def test_slight_bullish_options_flow(self) -> None:
        """52-55% calls gives 1 point."""
        score, reasons = _calculate_options_flow_score(
            options_call_pct=0.53,
            options_near_term_pct=0.50,
            ticker_in_active_sector=False,
        )
        assert score == 1
        assert "slightly bullish" in reasons[0].lower()

    def test_neutral_options_flow(self) -> None:
        """45-52% calls is neutral (0 points)."""
        score, reasons = _calculate_options_flow_score(
            options_call_pct=0.50,
            options_near_term_pct=0.50,
            ticker_in_active_sector=False,
        )
        assert score == 0
        assert len(reasons) == 0

    def test_bearish_options_flow(self) -> None:
        """<45% calls is bearish (0 points but noted)."""
        score, reasons = _calculate_options_flow_score(
            options_call_pct=0.40,
            options_near_term_pct=0.50,
            ticker_in_active_sector=False,
        )
        assert score == 0  # No positive points
        assert len(reasons) == 1
        assert "bearish" in reasons[0].lower()

    def test_sector_activity_bonus(self) -> None:
        """Ticker in active sector adds 1 point."""
        score, reasons = _calculate_options_flow_score(
            options_call_pct=0.58,
            options_near_term_pct=0.50,
            ticker_in_active_sector=True,
        )
        assert score == 4  # 3 (bullish) + 1 (sector)
        assert any("sector" in r.lower() for r in reasons)

    def test_max_score_with_all_factors(self) -> None:
        """Maximum score is 4 (3 call + 1 sector)."""
        score, reasons = _calculate_options_flow_score(
            options_call_pct=0.65,
            options_near_term_pct=0.80,
            ticker_in_active_sector=True,
        )
        assert score == 4
        assert len(reasons) == 2


class TestOptionsFlowIntegration:
    """Tests for options flow integration in classify_signal."""

    def test_options_flow_boosts_signal_strength(self) -> None:
        """Bullish options flow should increase confirmations."""
        # Base inputs without options
        base_inputs = {
            "price": 150.0,
            "ema_20": 145.0,  # Above EMA = bullish
            "sma_5": 148.0,
            "sma_5_prev": 145.0,  # Rising = bullish
            "rsi_14": 55.0,
            "macd": 1.0,
            "volume": 10000000,
            "volume_avg_20": 8000000,
            "company_health": "GOOD",
            "news_sentiment": 0.1,
        }

        # Without options
        result_without = classify_signal(base_inputs)

        # With bullish options
        inputs_with_options = {
            **base_inputs,
            "options_call_pct": 0.60,
            "options_near_term_pct": 0.50,
            "ticker_in_active_sector": True,
        }
        result_with = classify_signal(inputs_with_options)

        # Options should boost strength
        assert result_with.strength.value >= result_without.strength.value

    def test_options_flow_adds_reason(self) -> None:
        """Bullish options flow should add reason to classification."""
        inputs = {
            "price": 150.0,
            "ema_20": 145.0,
            "sma_5": 148.0,
            "sma_5_prev": 145.0,
            "rsi_14": 55.0,
            "macd": 1.0,
            "volume": 10000000,
            "volume_avg_20": 8000000,
            "company_health": "GOOD",
            "news_sentiment": 0.1,
            "options_call_pct": 0.58,
            "options_near_term_pct": 0.50,
            "ticker_in_active_sector": False,
        }

        result = classify_signal(inputs)

        # Should have options-related reason
        options_reasons = [r for r in result.reasons if "options" in r.lower()]
        assert len(options_reasons) > 0

    def test_bearish_options_does_not_add_points(self) -> None:
        """Bearish options flow should not add positive points."""
        inputs = {
            "price": 150.0,
            "ema_20": 145.0,
            "sma_5": 148.0,
            "sma_5_prev": 145.0,
            "rsi_14": 55.0,
            "macd": 1.0,
            "volume": 10000000,
            "volume_avg_20": 8000000,
            "company_health": "GOOD",
            "news_sentiment": 0.1,
            "options_call_pct": 0.40,  # Bearish
            "options_near_term_pct": 0.50,
            "ticker_in_active_sector": False,
        }

        result = classify_signal(inputs)

        # Bearish options noted but doesn't add points
        options_reasons = [r for r in result.reasons if "options" in r.lower()]
        assert len(options_reasons) == 1
        assert "bearish" in options_reasons[0].lower()
