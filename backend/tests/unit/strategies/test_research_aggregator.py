"""Unit tests for ResearchAggregationService."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from app.strategies.models import ResearchInsights
from app.strategies.research_aggregator import ResearchAggregationService


@pytest.fixture
def mock_storage():
    """Create mock PortfolioStorage."""
    storage = Mock()
    return storage


@pytest.fixture
def mock_connection():
    """Create mock database connection."""
    conn = Mock()
    cursor = Mock()
    conn.cursor.return_value = cursor
    return conn


@pytest.fixture
def service(mock_storage, mock_connection):
    """Create ResearchAggregationService with mocks."""
    mock_conn_manager = Mock()
    mock_conn_manager.connection.return_value.__enter__ = Mock(return_value=mock_connection)
    mock_conn_manager.connection.return_value.__exit__ = Mock(return_value=None)

    with (
        patch("app.strategies.research_aggregator.PortfolioStorage", return_value=mock_storage),
        patch(
            "app.strategies.research_aggregator.get_connection_manager",
            return_value=mock_conn_manager,
        ),
    ):
        return ResearchAggregationService()


class TestResearchAggregationService:
    """Test suite for ResearchAggregationService."""

    def test_initialization(self, service):
        """Test service initialization."""
        assert service.storage is not None
        assert service.conn is not None

    @pytest.mark.asyncio
    async def test_aggregate_research_success(self, service, mock_connection):
        """Test successful research aggregation."""
        symbol = "AAPL"

        # Mock news data query
        news_cursor = Mock()
        news_cursor.fetchall.return_value = [
            (0.6, 15),  # (sentiment_score, article_count) for last 7 days
            (0.5, 45),  # (sentiment_score, article_count) for last 30 days
        ]

        # Mock fundamental data
        fundamental_cursor = Mock()
        fundamental_cursor.fetchone.return_value = (
            85,  # fundamental_score
            "EXCELLENT",  # company_health
            "Technology",  # sector
        )

        # Mock technical data (day_bars query for 252 days)
        technical_cursor = Mock()
        technical_cursor.fetchall.return_value = [
            (
                date.today() - timedelta(days=i),
                Decimal(150 + i * 0.5),
                Decimal(148),
                Decimal(151),
                Decimal(149),
                1000000,
            )
            for i in range(252)
        ]

        # Mock Fear & Greed data
        macro_cursor = Mock()
        macro_cursor.fetchone.return_value = (72, "greed")

        # Mock sector strength data
        sector_cursor = Mock()
        sector_cursor.fetchone.return_value = (Decimal("5.2"), "leading")

        # Set up cursor returns for different queries
        mock_connection.cursor.return_value = news_cursor

        # Mock the internal methods
        with (
            patch.object(
                service,
                "_aggregate_news_intelligence",
                return_value={
                    "sentiment_trend": "improving",
                    "sentiment_score": 0.6,
                    "sentiment_7d_avg": 0.55,
                    "sentiment_30d_avg": 0.5,
                    "material_events": ["earnings_beat"],
                    "news_volume": 45,
                    "confidence": 0.85,
                },
            ),
            patch.object(
                service,
                "_aggregate_fundamental_analysis",
                return_value={
                    "company_health": "EXCELLENT",
                    "fundamental_score": 85,
                    "valuation_tier": "fair",
                    "growth_tier": "accelerating",
                    "profitability_tier": "excellent",
                    "debt_tier": "low",
                    "analyst_consensus": 1.5,
                    "confidence": 0.9,
                },
            ),
            patch.object(
                service,
                "_aggregate_technical_analysis",
                return_value={
                    "trend_strength": "strong_up",
                    "trend_duration_days": 45,
                    "momentum_rating": "accelerating",
                    "volume_profile": "increasing",
                    "rsi_zone": "healthy",
                    "price_vs_ma": {"20d": 1.05, "50d": 1.08, "200d": 1.12},
                    "confidence": 1.0,
                },
            ),
            patch.object(
                service,
                "_aggregate_macro_context",
                return_value={
                    "market_regime": "bull",
                    "fear_greed_score": 72,
                    "fear_greed_classification": "greed",
                    "sector_rotation_phase": "mid_cycle",
                },
            ),
            patch.object(
                service,
                "_aggregate_sector_strength",
                return_value={
                    "sector": "Technology",
                    "sector_momentum": "leading",
                    "sector_vs_spy_30d": 5.2,
                    "sector_rotation_signal": "hold",
                    "confidence": 1.0,
                },
            ),
        ):
            result = await service.aggregate_research(symbol, lookback_days=30)

        # Verify result structure
        assert isinstance(result, ResearchInsights)
        assert result.symbol == symbol
        assert result.as_of_date == date.today()

        # Verify news data
        assert result.news_sentiment_trend == "improving"
        assert result.news_sentiment_score == 0.6
        assert result.news_volume == 45
        assert result.news_confidence == 0.85

        # Verify fundamental data
        assert result.company_health == "EXCELLENT"
        assert result.fundamental_score == 85
        assert result.fundamental_confidence == 0.9

        # Verify technical data
        assert result.trend_strength == "strong_up"
        assert result.rsi_zone == "healthy"
        assert result.technical_confidence == 1.0

        # Verify macro data
        assert result.market_regime == "bull"
        assert result.fear_greed_score == 72

        # Verify sector data
        assert result.sector == "Technology"
        assert result.sector_momentum == "leading"

        # Verify overall assessment
        assert result.overall_confidence > 0.8
        assert result.research_quality == "high"

    @pytest.mark.asyncio
    async def test_aggregate_research_medium_quality(self, service):
        """Test research aggregation with medium quality data."""
        symbol = "XYZ"

        # Mock with lower confidence scores
        with (
            patch.object(
                service,
                "_aggregate_news_intelligence",
                return_value={
                    "sentiment_trend": "stable",
                    "sentiment_score": 0.3,
                    "sentiment_7d_avg": 0.3,
                    "sentiment_30d_avg": 0.3,
                    "material_events": [],
                    "news_volume": 10,  # Low volume
                    "confidence": 0.5,  # Low confidence
                },
            ),
            patch.object(
                service,
                "_aggregate_fundamental_analysis",
                return_value={
                    "company_health": "GOOD",
                    "fundamental_score": 65,
                    "valuation_tier": "fair",
                    "growth_tier": "stable",
                    "profitability_tier": "good",
                    "debt_tier": "moderate",
                    "analyst_consensus": 3.0,
                    "confidence": 0.6,  # Medium confidence
                },
            ),
            patch.object(
                service,
                "_aggregate_technical_analysis",
                return_value={
                    "trend_strength": "neutral",
                    "trend_duration_days": 10,
                    "momentum_rating": "steady",
                    "volume_profile": "stable",
                    "rsi_zone": "healthy",
                    "price_vs_ma": {"20d": 1.00, "50d": 0.98, "200d": 1.02},
                    "confidence": 1.0,
                },
            ),
            patch.object(
                service,
                "_aggregate_macro_context",
                return_value={
                    "market_regime": "range",
                    "fear_greed_score": 50,
                    "fear_greed_classification": "neutral",
                    "sector_rotation_phase": "mid_cycle",
                },
            ),
            patch.object(
                service,
                "_aggregate_sector_strength",
                return_value={
                    "sector": "Consumer Discretionary",
                    "sector_momentum": "in_line",
                    "sector_vs_spy_30d": 0.5,
                    "sector_rotation_signal": "hold",
                    "confidence": 1.0,
                },
            ),
        ):
            result = await service.aggregate_research(symbol, lookback_days=30)

        # Verify medium quality classification
        assert result.overall_confidence >= 0.5
        assert result.overall_confidence < 0.8
        assert result.research_quality == "medium"

    @pytest.mark.asyncio
    async def test_aggregate_research_low_quality(self, service):
        """Test research aggregation with low quality data."""
        symbol = "PENNY"

        # Mock with very low confidence scores
        with (
            patch.object(
                service,
                "_aggregate_news_intelligence",
                return_value={
                    "sentiment_trend": "stable",
                    "sentiment_score": 0.0,
                    "sentiment_7d_avg": 0.0,
                    "sentiment_30d_avg": 0.0,
                    "material_events": [],
                    "news_volume": 2,  # Very low volume
                    "confidence": 0.2,  # Very low confidence
                },
            ),
            patch.object(
                service,
                "_aggregate_fundamental_analysis",
                return_value={
                    "company_health": "WEAK",
                    "fundamental_score": 30,
                    "valuation_tier": "overvalued",
                    "growth_tier": "slowing",
                    "profitability_tier": "weak",
                    "debt_tier": "high",
                    "analyst_consensus": 4.5,
                    "confidence": 0.3,  # Low confidence
                },
            ),
            patch.object(
                service,
                "_aggregate_technical_analysis",
                return_value={
                    "trend_strength": "weak_down",
                    "trend_duration_days": 5,
                    "momentum_rating": "decelerating",
                    "volume_profile": "decreasing",
                    "rsi_zone": "oversold",
                    "price_vs_ma": {"20d": 0.85, "50d": 0.80, "200d": 0.75},
                    "confidence": 0.7,  # Some data available
                },
            ),
            patch.object(
                service,
                "_aggregate_macro_context",
                return_value={
                    "market_regime": "volatile",
                    "fear_greed_score": 25,
                    "fear_greed_classification": "extreme_fear",
                    "sector_rotation_phase": "recession",
                },
            ),
            patch.object(
                service,
                "_aggregate_sector_strength",
                return_value={
                    "sector": "Unknown",
                    "sector_momentum": "lagging",
                    "sector_vs_spy_30d": -8.5,
                    "sector_rotation_signal": "rotate_out",
                    "confidence": 0.5,
                },
            ),
        ):
            result = await service.aggregate_research(symbol, lookback_days=30)

        # Verify low quality classification
        assert result.overall_confidence < 0.5
        assert result.research_quality == "low"

    def test_calculate_overall_confidence(self, service):
        """Test overall confidence calculation."""
        # Equal weights scenario
        confidence = service._calculate_overall_confidence(0.8, 0.9, 1.0, 1.0, 1.0)
        assert 0.9 <= confidence <= 1.0

        # Mixed confidences
        confidence = service._calculate_overall_confidence(0.5, 0.6, 1.0, 1.0, 0.8)
        assert 0.7 <= confidence <= 0.8

        # Low news confidence should pull down overall
        confidence = service._calculate_overall_confidence(0.2, 0.9, 1.0, 1.0, 1.0)
        assert confidence < 0.9

    @pytest.mark.asyncio
    async def test_lookback_days_parameter(self, service):
        """Test that lookback_days parameter is used correctly."""
        symbol = "TEST"
        lookback_days = 60

        with (
            patch.object(service, "_aggregate_news_intelligence") as mock_news,
            patch.object(
                service,
                "_aggregate_fundamental_analysis",
                return_value={
                    "company_health": "GOOD",
                    "fundamental_score": 70,
                    "valuation_tier": "fair",
                    "growth_tier": "stable",
                    "profitability_tier": "good",
                    "debt_tier": "moderate",
                    "analyst_consensus": 2.5,
                    "confidence": 0.8,
                },
            ),
            patch.object(
                service,
                "_aggregate_technical_analysis",
                return_value={
                    "trend_strength": "neutral",
                    "trend_duration_days": 20,
                    "momentum_rating": "steady",
                    "volume_profile": "stable",
                    "rsi_zone": "healthy",
                    "price_vs_ma": {"20d": 1.0, "50d": 1.0, "200d": 1.0},
                    "confidence": 1.0,
                },
            ),
            patch.object(
                service,
                "_aggregate_macro_context",
                return_value={
                    "market_regime": "range",
                    "fear_greed_score": 50,
                    "fear_greed_classification": "neutral",
                    "sector_rotation_phase": "mid_cycle",
                },
            ),
            patch.object(
                service,
                "_aggregate_sector_strength",
                return_value={
                    "sector": "Technology",
                    "sector_momentum": "in_line",
                    "sector_vs_spy_30d": 0.0,
                    "sector_rotation_signal": "hold",
                    "confidence": 1.0,
                },
            ),
        ):
            # Set up mock returns
            mock_news.return_value = {
                "sentiment_trend": "stable",
                "sentiment_score": 0.5,
                "sentiment_7d_avg": 0.5,
                "sentiment_30d_avg": 0.5,
                "material_events": [],
                "news_volume": 20,
                "confidence": 0.7,
            }

            await service.aggregate_research(symbol, lookback_days=lookback_days)

            # Verify cutoff date was calculated correctly
            mock_news.assert_called_once()
            call_args = mock_news.call_args[0]
            cutoff_date = call_args[1]
            expected_cutoff = date.today() - timedelta(days=lookback_days)
            assert cutoff_date == expected_cutoff

    @pytest.mark.asyncio
    async def test_research_insights_timestamp(self, service):
        """Test that last_updated timestamp is set."""
        symbol = "AAPL"

        with (
            patch.object(
                service,
                "_aggregate_news_intelligence",
                return_value={
                    "sentiment_trend": "stable",
                    "sentiment_score": 0.5,
                    "sentiment_7d_avg": 0.5,
                    "sentiment_30d_avg": 0.5,
                    "material_events": [],
                    "news_volume": 20,
                    "confidence": 0.7,
                },
            ),
            patch.object(
                service,
                "_aggregate_fundamental_analysis",
                return_value={
                    "company_health": "GOOD",
                    "fundamental_score": 70,
                    "valuation_tier": "fair",
                    "growth_tier": "stable",
                    "profitability_tier": "good",
                    "debt_tier": "moderate",
                    "analyst_consensus": 2.5,
                    "confidence": 0.8,
                },
            ),
            patch.object(
                service,
                "_aggregate_technical_analysis",
                return_value={
                    "trend_strength": "neutral",
                    "trend_duration_days": 20,
                    "momentum_rating": "steady",
                    "volume_profile": "stable",
                    "rsi_zone": "healthy",
                    "price_vs_ma": {"20d": 1.0, "50d": 1.0, "200d": 1.0},
                    "confidence": 1.0,
                },
            ),
            patch.object(
                service,
                "_aggregate_macro_context",
                return_value={
                    "market_regime": "range",
                    "fear_greed_score": 50,
                    "fear_greed_classification": "neutral",
                    "sector_rotation_phase": "mid_cycle",
                },
            ),
            patch.object(
                service,
                "_aggregate_sector_strength",
                return_value={
                    "sector": "Technology",
                    "sector_momentum": "in_line",
                    "sector_vs_spy_30d": 0.0,
                    "sector_rotation_signal": "hold",
                    "confidence": 1.0,
                },
            ),
        ):
            result = await service.aggregate_research(symbol)

        assert result.last_updated is not None
        # Timestamp should be very recent (within last minute)
        from datetime import datetime

        time_diff = (datetime.now() - result.last_updated).total_seconds()
        assert time_diff < 60
