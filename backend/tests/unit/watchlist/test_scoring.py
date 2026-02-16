"""Unit tests for watchlist scoring module (FEAT-030).

Tests the 5-pillar scoring system:
- Price component (price change percentage)
- Technical component (RSI, trend, MACD)
- Fundamental component (4 sub-scores: valuation, growth, health, sentiment)
- Catalyst component (news events scoring)
- Options flow component (call/put sentiment)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.portfolio.models import PriceData
from app.services.options_flow_service import OptionsFlowData
from app.watchlist.fundamentals import FundamentalData
from app.watchlist.models import (
    ScoreWeights,
    TechnicalSnapshot,
    WatchlistScoreInputs,
)
from app.watchlist.scoring import calculate_watchlist_scores
from app.watchlist.scoring_service.components import (
    PriceComponentInputs,
    compute_catalyst_component,
    compute_fundamental_component,
    compute_options_flow_component,
    compute_price_component,
    compute_technical_component,
)
from app.watchlist.scoring_service.helpers import (
    score_from_change_percent,
    score_from_rsi,
    score_from_trend,
)


class TestScoreFromChangePercent:
    """Tests for score_from_change_percent helper."""

    def test_positive_change(self) -> None:
        """Test positive price change mapping."""
        # +10% change should map to 75 (midpoint between 50 and 100)
        score = score_from_change_percent(10.0)
        assert score == 75.0

    def test_negative_change(self) -> None:
        """Test negative price change mapping."""
        # -10% change should map to 25 (midpoint between 0 and 50)
        score = score_from_change_percent(-10.0)
        assert score == 25.0

    def test_zero_change(self) -> None:
        """Test zero change maps to 50 (neutral)."""
        score = score_from_change_percent(0.0)
        assert score == 50.0

    def test_clamping_upper_bound(self) -> None:
        """Test that values >20% are clamped to 100."""
        score = score_from_change_percent(30.0)
        assert score == 100.0

    def test_clamping_lower_bound(self) -> None:
        """Test that values <-20% are clamped to 0."""
        score = score_from_change_percent(-30.0)
        assert score == 0.0


class TestScoreFromRSI:
    """Tests for score_from_rsi helper."""

    def test_rsi_50_max_score(self) -> None:
        """Test RSI of 50 (balanced) gives max score."""
        score = score_from_rsi(50.0)
        assert score == 100.0

    def test_rsi_70_overbought(self) -> None:
        """Test overbought RSI (70) gives lower score."""
        score = score_from_rsi(70.0)
        assert score == 60.0  # Distance 20 from 50

    def test_rsi_30_oversold(self) -> None:
        """Test oversold RSI (30) gives lower score."""
        score = score_from_rsi(30.0)
        assert score == 60.0  # Distance 20 from 50

    def test_rsi_extremes(self) -> None:
        """Test extreme RSI values."""
        assert score_from_rsi(0.0) == 0.0
        assert score_from_rsi(100.0) == 0.0


class TestScoreFromTrend:
    """Tests for score_from_trend helper."""

    def test_price_above_averages(self) -> None:
        """Test trend score when price > SMA50 > SMA200."""
        score = score_from_trend(price=110.0, sma_50=105.0, sma_200=100.0)
        assert score is not None
        assert score > 50.0  # Positive trend

    def test_price_below_averages(self) -> None:
        """Test trend score when price < SMA50 < SMA200."""
        score = score_from_trend(price=90.0, sma_50=95.0, sma_200=100.0)
        assert score is not None
        assert score < 50.0  # Negative trend

    def test_missing_data_returns_none(self) -> None:
        """Test that missing data returns None."""
        assert score_from_trend(price=None, sma_50=100.0, sma_200=100.0) is None
        assert score_from_trend(price=100.0, sma_50=None, sma_200=100.0) is None
        assert score_from_trend(price=100.0, sma_50=100.0, sma_200=None) is None


class TestComputePriceComponent:
    """Tests for compute_price_component function."""

    def test_fresh_price_data(self) -> None:
        """Test price component with fresh data."""
        now = datetime.now(UTC)
        inputs = PriceComponentInputs(
            price_data=PriceData(
                symbol="AAPL",
                price=150.0,
                source="test",
                cached_at=now,
                beta=1.2,
                volatility=0.25,
            ),
            change_pct=5.0,  # +5%
            now=now,
        )
        component = compute_price_component(inputs, weight=0.3)
        assert component.score > 50.0  # Positive change
        assert component.weight == 0.3
        assert component.stale is False
        assert component.metadata["raw_change_pct"] == 5.0

    def test_stale_price_data(self) -> None:
        """Test price component with stale data (>15 min old)."""
        now = datetime.now(UTC)
        stale_time = now - timedelta(minutes=20)
        inputs = PriceComponentInputs(
            price_data=PriceData(
                symbol="AAPL",
                price=150.0,
                source="test",
                cached_at=stale_time,
                beta=1.2,
                volatility=0.25,
            ),
            change_pct=5.0,
            now=now,
        )
        component = compute_price_component(inputs, weight=0.3)
        assert component.stale is True

    def test_missing_change_pct(self) -> None:
        """Test price component when change_pct is None."""
        now = datetime.now(UTC)
        inputs = PriceComponentInputs(
            price_data=PriceData(
                symbol="AAPL",
                price=150.0,
                source="test",
                cached_at=now,
                beta=1.2,
                volatility=0.25,
            ),
            change_pct=None,
            now=now,
        )
        component = compute_price_component(inputs, weight=0.3)
        assert component.score == 0.0
        assert component.stale is True
        assert component.metadata["reason"] == "missing_change_pct"


class TestComputeTechnicalComponent:
    """Tests for compute_technical_component function."""

    def test_complete_technical_data(self) -> None:
        """Test technical component with all indicators present."""
        now = datetime.now(UTC)
        technical = TechnicalSnapshot(
            price=150.0,
            rsi_14=55.0,
            sma_50=145.0,
            sma_200=140.0,
            macd=2.0,
            macd_signal=1.5,
            calculated_at=now,
        )
        component = compute_technical_component(technical, weight=0.3, now=now)
        assert component.score > 0.0
        assert component.weight == 0.3
        assert component.stale is False
        assert "rsi_14" in component.metadata
        assert "trend_score" in component.metadata
        assert "macd" in component.metadata

    def test_missing_technical_indicators(self) -> None:
        """Test technical component when all indicators are missing."""
        now = datetime.now(UTC)
        technical = TechnicalSnapshot(
            price=150.0,
            rsi_14=None,
            sma_50=None,
            sma_200=None,
            macd=None,
            macd_signal=None,
            calculated_at=now,
        )
        component = compute_technical_component(technical, weight=0.3, now=now)
        assert component.score == 0.0
        assert component.stale is True
        assert component.metadata["reason"] == "missing_indicators"

    def test_stale_technical_data(self) -> None:
        """Test technical component with stale data (>60 min old)."""
        now = datetime.now(UTC)
        stale_time = now - timedelta(minutes=90)
        technical = TechnicalSnapshot(
            price=150.0,
            rsi_14=55.0,
            sma_50=145.0,
            sma_200=140.0,
            calculated_at=stale_time,
        )
        component = compute_technical_component(technical, weight=0.3, now=now)
        assert component.stale is True


class TestComputeFundamentalComponent:
    """Tests for compute_fundamental_component function."""

    def test_complete_fundamental_data(self) -> None:
        """Test fundamental component with complete 4-pillar scores."""
        now = datetime.now(UTC)
        fundamentals = FundamentalData(
            symbol="AAPL",
            profit_margin=0.25,
            revenue_growth=0.20,
            debt_to_equity=0.5,
            recommendation_mean=2.0,
            fundamental_score=85.0,
            valuation_score=80.0,
            growth_score=90.0,
            health_score=85.0,
            sentiment_score=80.0,
        )
        component = compute_fundamental_component(fundamentals, weight=0.2, now=now)
        assert component.score == 85.0
        assert component.weight == 0.2
        assert component.stale is False
        assert component.sub_scores is not None
        assert "valuation" in component.sub_scores
        assert "growth" in component.sub_scores
        assert "health" in component.sub_scores
        assert "sentiment" in component.sub_scores

    def test_missing_fundamental_data(self) -> None:
        """Test fundamental component when data is None."""
        now = datetime.now(UTC)
        component = compute_fundamental_component(None, weight=0.2, now=now)
        assert component.score == 0.0
        assert component.stale is True
        assert component.metadata["reason"] == "missing_fundamental_data"


class TestComputeCatalystComponent:
    """Tests for compute_catalyst_component function."""

    def test_positive_catalysts(self) -> None:
        """Test catalyst scoring with positive news events."""
        now = datetime.now(UTC)
        news_articles: list[dict[str, str | datetime | float | None]] = [
            {
                "headline": "Strong earnings beat",
                "summary": "Company exceeds expectations",
                "published_at": now - timedelta(hours=2),
                "filing_type": None,
            },
            {
                "headline": "New product launch",
                "summary": "Innovation drives growth",
                "published_at": now - timedelta(hours=5),
                "filing_type": None,
            },
        ]
        component = compute_catalyst_component(
            symbol="AAPL",
            news_articles=news_articles,
            weight=0.15,
            now=now,
        )
        # Catalyst scoring depends on catalyst_scoring service
        # This test validates structure, not exact score
        assert component.weight == 0.15
        assert component.score >= 0.0
        assert component.score <= 100.0
        assert "catalyst_count" in component.metadata

    def test_no_news_articles(self) -> None:
        """Test neutral score when no news articles present."""
        now = datetime.now(UTC)
        component = compute_catalyst_component(
            symbol="AAPL",
            news_articles=[],
            weight=0.15,
            now=now,
        )
        assert component.score == 50.0  # Neutral
        assert component.metadata["reason"] == "no_news_articles"


class TestComputeOptionsFlowComponent:
    """Tests for compute_options_flow_component function."""

    def test_bullish_options_flow(self) -> None:
        """Test options flow with high call percentage (bullish)."""
        options_data = OptionsFlowData(
            call_pct=0.65,  # 65% calls
            near_term_pct=0.40,
            concentration_pct=0.50,
            sector_weights={},
            as_of_date=datetime.now(UTC).date(),
            is_stale=False,
        )
        component = compute_options_flow_component(
            options_data=options_data,
            symbol_in_active_sector=False,
            weight=0.1,
        )
        assert component.score > 50.0  # Bullish
        assert component.weight == 0.1
        assert component.stale is False
        assert component.metadata["call_pct"] == 0.65

    def test_bearish_options_flow(self) -> None:
        """Test options flow with low call percentage (bearish)."""
        options_data = OptionsFlowData(
            call_pct=0.35,  # 35% calls (65% puts)
            near_term_pct=0.40,
            concentration_pct=0.50,
            sector_weights={},
            as_of_date=datetime.now(UTC).date(),
            is_stale=False,
        )
        component = compute_options_flow_component(
            options_data=options_data,
            symbol_in_active_sector=False,
            weight=0.1,
        )
        assert component.score < 50.0  # Bearish

    def test_sector_activity_bonus(self) -> None:
        """Test that active sector adds bonus to score."""
        options_data = OptionsFlowData(
            call_pct=0.55,  # Neutral-bullish
            near_term_pct=0.40,
            concentration_pct=0.50,
            sector_weights={},
            as_of_date=datetime.now(UTC).date(),
            is_stale=False,
        )
        component_no_bonus = compute_options_flow_component(
            options_data=options_data,
            symbol_in_active_sector=False,
            weight=0.1,
        )
        component_with_bonus = compute_options_flow_component(
            options_data=options_data,
            symbol_in_active_sector=True,
            weight=0.1,
        )
        assert component_with_bonus.score > component_no_bonus.score

    def test_missing_options_data(self) -> None:
        """Test neutral score when options data is None."""
        component = compute_options_flow_component(
            options_data=None,
            symbol_in_active_sector=False,
            weight=0.1,
        )
        assert component.score == 50.0  # Neutral
        assert component.stale is True


class TestCalculateWatchlistScores:
    """Integration tests for calculate_watchlist_scores (5-pillar system)."""

    def test_2_pillar_scoring(self) -> None:
        """Test basic 2-pillar scoring (price + technical only)."""
        now = datetime.now(UTC)
        inputs = WatchlistScoreInputs(
            price=PriceData(
                symbol="AAPL",
                price=150.0,
                source="test",
                cached_at=now,
                beta=1.2,
                volatility=0.25,
            ),
            price_change_pct=5.0,
            technical=TechnicalSnapshot(
                price=150.0,
                rsi_14=55.0,
                sma_50=145.0,
                sma_200=140.0,
                calculated_at=now,
            ),
            weights=ScoreWeights(price=0.5, technical=0.5),
            now=now,
            stale_ttl_minutes=15,
        )
        breakdown = calculate_watchlist_scores(inputs)
        assert breakdown.overall > 0.0
        assert breakdown.price is not None
        assert breakdown.technical is not None
        assert breakdown.fundamental is None
        assert breakdown.catalyst is None
        # options_flow always returns a component (with default neutral score when no data)

    def test_5_pillar_scoring(self) -> None:
        """Test full 5-pillar scoring with all components."""
        now = datetime.now(UTC)
        inputs = WatchlistScoreInputs(
            price=PriceData(
                symbol="AAPL",
                price=150.0,
                source="test",
                cached_at=now,
                beta=1.2,
                volatility=0.25,
            ),
            price_change_pct=5.0,
            technical=TechnicalSnapshot(
                price=150.0,
                rsi_14=55.0,
                sma_50=145.0,
                sma_200=140.0,
                calculated_at=now,
            ),
            fundamental=FundamentalData(
                symbol="AAPL",
                profit_margin=0.25,
                revenue_growth=0.20,
                debt_to_equity=0.5,
                fundamental_score=80.0,
                valuation_score=75.0,
                growth_score=85.0,
                health_score=80.0,
                sentiment_score=75.0,
            ),
            news_articles=[
                {
                    "headline": "Positive news",
                    "summary": "Good results",
                    "published_at": now - timedelta(hours=2),
                    "filing_type": None,
                }
            ],
            options_data=OptionsFlowData(
                call_pct=0.60,
                near_term_pct=0.40,
                concentration_pct=0.50,
                sector_weights={},
                as_of_date=now.date(),
                is_stale=False,
            ),
            weights=ScoreWeights(
                price=0.25,
                technical=0.25,
                fundamental=0.25,
                catalyst=0.15,
                options_flow=0.1,
            ),
            now=now,
            stale_ttl_minutes=15,
        )
        breakdown = calculate_watchlist_scores(inputs)
        assert breakdown.overall > 0.0
        assert breakdown.price is not None
        assert breakdown.technical is not None
        assert breakdown.fundamental is not None
        assert breakdown.catalyst is not None
        assert breakdown.options_flow is not None

        # Verify sub-scores present
        assert breakdown.price.sub_scores is not None
        assert breakdown.technical.sub_scores is not None
        assert breakdown.fundamental.sub_scores is not None
        assert "valuation" in breakdown.fundamental.sub_scores

    def test_rvol_in_price_metadata(self) -> None:
        """Test that RVOL is included in price metadata (FEAT-130)."""
        now = datetime.now(UTC)
        inputs = WatchlistScoreInputs(
            price=PriceData(
                symbol="AAPL",
                price=150.0,
                source="test",
                cached_at=now,
                beta=1.2,
                volatility=0.25,
            ),
            price_change_pct=5.0,
            volume_relative=2.5,  # RVOL = 2.5x
            technical=TechnicalSnapshot(
                price=150.0,
                calculated_at=now,
            ),
            weights=ScoreWeights(price=0.5, technical=0.5),
            now=now,
            stale_ttl_minutes=15,
        )
        breakdown = calculate_watchlist_scores(inputs)
        assert "rvol" in breakdown.price.metadata
        assert breakdown.price.metadata["rvol"] == 2.5
