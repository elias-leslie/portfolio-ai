"""Unit tests for StrategyGeneratorAgent."""

import json
from datetime import date, datetime
from unittest.mock import patch

import pytest

from app.agents.llm_client import LLMResponse
from app.strategies.models import (
    ExpectedCharacteristics,
    ResearchInsights,
    StrategyGenerationResult,
    StrategyParameters,
)
from app.strategies.strategy_generator import StrategyGeneratorAgent


@pytest.fixture
def sample_research_insights():
    """Create sample research insights for testing."""
    return ResearchInsights(
        symbol="AAPL",
        as_of_date=date(2024, 11, 20),
        # News intelligence
        news_sentiment_trend="improving",
        news_sentiment_score=0.6,
        news_sentiment_7d_avg=0.55,
        news_sentiment_30d_avg=0.5,
        material_events=["earnings_beat", "product_launch"],
        news_volume=45,
        news_confidence=0.85,
        # Fundamentals
        company_health="EXCELLENT",
        fundamental_score=85,
        valuation_tier="fair",
        growth_tier="accelerating",
        profitability_tier="excellent",
        debt_tier="low",
        analyst_consensus=1.5,
        fundamental_confidence=0.9,
        # Technical
        trend_strength="strong_up",
        trend_duration_days=45,
        momentum_rating="accelerating",
        volume_profile="increasing",
        rsi_zone="healthy",
        price_vs_ma={"20d": 1.05, "50d": 1.08, "200d": 1.12},
        technical_confidence=1.0,
        # Macro
        market_regime="bull",
        fear_greed_score=72,
        fear_greed_classification="greed",
        sector_rotation_phase="mid_cycle",
        # Sector
        sector="Technology",
        sector_momentum="leading",
        sector_vs_spy_30d=5.2,
        sector_rotation_signal="hold",
        # Composite
        overall_confidence=0.9,
        research_quality="high",
        last_updated=datetime.now(),
    )


@pytest.fixture
def sample_llm_response_momentum():
    """Create sample LLM response for momentum strategy."""
    strategy_json = {
        "strategy_type": "momentum",
        "reasoning": "Strong uptrend with positive earnings and product launch. Technical indicators show accelerating momentum with healthy RSI. Sector leading the market. High confidence momentum strategy recommended.",
        "confidence": 0.85,
        "parameters": {
            "weight_price_trend": 0.20,
            "weight_rsi_health": 0.10,
            "weight_momentum": 0.25,
            "weight_volume": 0.10,
            "weight_fundamentals": 0.15,
            "weight_news_sentiment": 0.15,
            "weight_sector_alignment": 0.05,
            "min_confirmations": 6,
            "min_weighted_score": 0.65,
            "stop_loss_atr_multiplier": 2.0,
            "max_holding_days": 60,
            "position_sizing_method": "fixed_dollars",
            "position_size_value": 10000.00,
            "rsi_oversold_threshold": 30,
            "rsi_overbought_threshold": 70,
            "volume_multiplier_threshold": 0.7,
            "news_sentiment_threshold": 0.2,
        },
        "expected_characteristics": {
            "avg_holding_period_days": 45,
            "expected_win_rate": 0.58,
            "expected_sharpe": 1.4,
            "risk_level": "medium",
        },
    }
    return LLMResponse(
        content=json.dumps(strategy_json),
        provider="gemini",
        model="gemini-2.0-flash-exp",
        usage={"input_tokens": 500, "output_tokens": 300},
        stop_reason="stop",
    )


@pytest.fixture
def sample_llm_response_no_strategy():
    """Create sample LLM response for no strategy recommendation."""
    strategy_json = {
        "strategy_type": "no_strategy",
        "reasoning": "Research quality is insufficient (overall confidence < 0.5). Limited news coverage and missing fundamental data. Recommend waiting for higher quality research before generating strategy.",
        "confidence": 0.3,
        "parameters": {
            "weight_price_trend": 0.14,
            "weight_rsi_health": 0.14,
            "weight_momentum": 0.14,
            "weight_volume": 0.14,
            "weight_fundamentals": 0.16,
            "weight_news_sentiment": 0.14,
            "weight_sector_alignment": 0.14,
            "min_confirmations": 7,
            "min_weighted_score": 0.75,
            "stop_loss_atr_multiplier": 2.0,
            "max_holding_days": 60,
            "position_sizing_method": "fixed_dollars",
            "position_size_value": 10000.00,
            "rsi_oversold_threshold": 30,
            "rsi_overbought_threshold": 70,
            "volume_multiplier_threshold": 0.7,
            "news_sentiment_threshold": 0.2,
        },
        "expected_characteristics": {
            "avg_holding_period_days": 30,
            "expected_win_rate": 0.45,
            "expected_sharpe": 0.5,
            "risk_level": "high",
        },
    }
    return LLMResponse(
        content=json.dumps(strategy_json),
        provider="gemini",
        model="gemini-2.0-flash-exp",
        usage={"input_tokens": 300, "output_tokens": 200},
        stop_reason="stop",
    )


class TestStrategyGeneratorAgent:
    """Test suite for StrategyGeneratorAgent."""

    def test_initialization(self):
        """Test agent initialization."""
        agent = StrategyGeneratorAgent()
        assert agent.llm_client is not None
        assert agent.llm_client.primary == "gemini"

    @pytest.mark.asyncio
    async def test_generate_strategy_success_momentum(
        self, sample_research_insights, sample_llm_response_momentum
    ):
        """Test successful momentum strategy generation."""
        agent = StrategyGeneratorAgent()

        # Mock LLM client
        with patch.object(agent.llm_client, "generate", return_value=sample_llm_response_momentum):
            result = await agent.generate_strategy(sample_research_insights)

        # Verify result structure
        assert isinstance(result, StrategyGenerationResult)
        assert result.strategy_type == "momentum"
        assert result.confidence == 0.85
        assert "Strong uptrend" in result.reasoning
        assert isinstance(result.parameters, StrategyParameters)
        assert isinstance(result.expected_characteristics, ExpectedCharacteristics)

        # Verify parameter weights sum to 1.0
        weights = [
            result.parameters.weight_price_trend,
            result.parameters.weight_rsi_health,
            result.parameters.weight_momentum,
            result.parameters.weight_volume,
            result.parameters.weight_fundamentals,
            result.parameters.weight_news_sentiment,
            result.parameters.weight_sector_alignment,
        ]
        assert abs(sum(weights) - 1.0) < 0.01  # Allow small floating point error

    @pytest.mark.asyncio
    async def test_generate_strategy_no_strategy(
        self, sample_research_insights, sample_llm_response_no_strategy
    ):
        """Test no_strategy recommendation for low quality research."""
        agent = StrategyGeneratorAgent()

        # Modify research to have low confidence
        low_confidence_research = ResearchInsights(
            **{
                **sample_research_insights.__dict__,
                "overall_confidence": 0.3,
                "research_quality": "low",
            }
        )

        # Mock LLM client
        with patch.object(
            agent.llm_client, "generate", return_value=sample_llm_response_no_strategy
        ):
            result = await agent.generate_strategy(low_confidence_research)

        assert result.strategy_type == "no_strategy"
        assert result.confidence < 0.5
        assert "insufficient" in result.reasoning.lower() or "quality" in result.reasoning.lower()

    @pytest.mark.asyncio
    async def test_format_research_prompt(self, sample_research_insights):
        """Test research formatting for LLM prompt."""
        agent = StrategyGeneratorAgent()
        prompt = agent._format_research_prompt(sample_research_insights)

        # Verify JSON structure
        research_dict = json.loads(prompt)
        assert research_dict["symbol"] == "AAPL"
        assert research_dict["as_of_date"] == "2024-11-20"
        assert "news" in research_dict
        assert "fundamentals" in research_dict
        assert "technical" in research_dict
        assert "macro" in research_dict
        assert "sector" in research_dict
        assert "overall" in research_dict

        # Verify nested structure
        assert research_dict["news"]["sentiment_score"] == 0.6
        assert research_dict["fundamentals"]["company_health"] == "EXCELLENT"
        assert research_dict["technical"]["trend_strength"] == "strong_up"

    def test_parse_strategy_json_valid(self):
        """Test parsing valid strategy JSON."""
        agent = StrategyGeneratorAgent()
        valid_json = json.dumps(
            {
                "strategy_type": "value",
                "reasoning": "Strong fundamentals with undervalued price. Good entry opportunity.",
                "confidence": 0.75,
                "parameters": {
                    "weight_price_trend": 0.15,
                    "weight_rsi_health": 0.10,
                    "weight_momentum": 0.10,
                    "weight_volume": 0.10,
                    "weight_fundamentals": 0.30,
                    "weight_news_sentiment": 0.15,
                    "weight_sector_alignment": 0.10,
                    "min_confirmations": 6,
                    "min_weighted_score": 0.65,
                    "stop_loss_atr_multiplier": 2.0,
                    "max_holding_days": 90,
                    "position_sizing_method": "fixed_dollars",
                    "position_size_value": 10000.00,
                    "rsi_oversold_threshold": 30,
                    "rsi_overbought_threshold": 70,
                    "volume_multiplier_threshold": 0.7,
                    "news_sentiment_threshold": 0.2,
                },
                "expected_characteristics": {
                    "avg_holding_period_days": 75,
                    "expected_win_rate": 0.60,
                    "expected_sharpe": 1.2,
                    "risk_level": "medium-low",
                },
            }
        )

        result = agent._parse_strategy_json(valid_json)
        assert result["strategy_type"] == "value"
        assert result["confidence"] == 0.75

    def test_parse_strategy_json_with_markdown(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        agent = StrategyGeneratorAgent()
        markdown_json = """```json
{
  "strategy_type": "momentum",
  "reasoning": "Test reasoning with at least fifty characters in total for validation.",
  "confidence": 0.8,
  "parameters": {
    "weight_price_trend": 0.20,
    "weight_rsi_health": 0.10,
    "weight_momentum": 0.25,
    "weight_volume": 0.10,
    "weight_fundamentals": 0.15,
    "weight_news_sentiment": 0.15,
    "weight_sector_alignment": 0.05,
    "min_confirmations": 6,
    "min_weighted_score": 0.65,
    "stop_loss_atr_multiplier": 2.0,
    "max_holding_days": 60,
    "position_sizing_method": "fixed_dollars",
    "position_size_value": 10000.00,
    "rsi_oversold_threshold": 30,
    "rsi_overbought_threshold": 70,
    "volume_multiplier_threshold": 0.7,
    "news_sentiment_threshold": 0.2
  },
  "expected_characteristics": {
    "avg_holding_period_days": 45,
    "expected_win_rate": 0.55,
    "expected_sharpe": 1.3,
    "risk_level": "medium"
  }
}
```"""

        result = agent._parse_strategy_json(markdown_json)
        assert result["strategy_type"] == "momentum"

    def test_parse_strategy_json_missing_field(self):
        """Test parsing JSON with missing required field."""
        agent = StrategyGeneratorAgent()
        invalid_json = json.dumps(
            {
                "strategy_type": "momentum",
                "confidence": 0.8,
                # Missing 'reasoning' field
                "parameters": {},
                "expected_characteristics": {},
            }
        )

        with pytest.raises(ValueError, match="Missing required field"):
            agent._parse_strategy_json(invalid_json)

    def test_parse_strategy_json_invalid_json(self):
        """Test parsing invalid JSON."""
        agent = StrategyGeneratorAgent()
        invalid_json = "not valid json {"

        with pytest.raises(ValueError, match="Invalid JSON response"):
            agent._parse_strategy_json(invalid_json)

    def test_construct_strategy_result_valid(self):
        """Test constructing StrategyGenerationResult from valid data."""
        agent = StrategyGeneratorAgent()
        strategy_data = {
            "strategy_type": "event",
            "reasoning": "Material news event detected with strong short-term momentum opportunity.",
            "confidence": 0.7,
            "parameters": {
                "weight_price_trend": 0.15,
                "weight_rsi_health": 0.10,
                "weight_momentum": 0.15,
                "weight_volume": 0.15,
                "weight_fundamentals": 0.10,
                "weight_news_sentiment": 0.30,
                "weight_sector_alignment": 0.05,
                "min_confirmations": 5,
                "min_weighted_score": 0.60,
                "stop_loss_atr_multiplier": 1.5,
                "max_holding_days": 20,
                "position_sizing_method": "fixed_dollars",
                "position_size_value": 8000.00,
                "rsi_oversold_threshold": 30,
                "rsi_overbought_threshold": 70,
                "volume_multiplier_threshold": 1.0,
                "news_sentiment_threshold": 0.3,
            },
            "expected_characteristics": {
                "avg_holding_period_days": 15,
                "expected_win_rate": 0.52,
                "expected_sharpe": 1.1,
                "risk_level": "medium-high",
            },
        }

        result = agent._construct_strategy_result(strategy_data)
        assert isinstance(result, StrategyGenerationResult)
        assert result.strategy_type == "event"
        assert result.parameters.weight_news_sentiment == 0.30

    def test_construct_strategy_result_invalid_weights(self):
        """Test validation failure when weights don't sum to 1.0."""
        agent = StrategyGeneratorAgent()
        strategy_data = {
            "strategy_type": "momentum",
            "reasoning": "Test strategy with invalid weights that do not sum to exactly one.",
            "confidence": 0.7,
            "parameters": {
                "weight_price_trend": 0.20,
                "weight_rsi_health": 0.10,
                "weight_momentum": 0.25,
                "weight_volume": 0.10,
                "weight_fundamentals": 0.15,
                "weight_news_sentiment": 0.15,
                "weight_sector_alignment": 0.10,  # Sum = 1.05 (invalid)
                "min_confirmations": 6,
                "min_weighted_score": 0.65,
                "stop_loss_atr_multiplier": 2.0,
                "max_holding_days": 60,
                "position_sizing_method": "fixed_dollars",
                "position_size_value": 10000.00,
                "rsi_oversold_threshold": 30,
                "rsi_overbought_threshold": 70,
                "volume_multiplier_threshold": 0.7,
                "news_sentiment_threshold": 0.2,
            },
            "expected_characteristics": {
                "avg_holding_period_days": 45,
                "expected_win_rate": 0.55,
                "expected_sharpe": 1.3,
                "risk_level": "medium",
            },
        }

        with pytest.raises(ValueError, match="Invalid strategy configuration"):
            agent._construct_strategy_result(strategy_data)

    @pytest.mark.asyncio
    async def test_llm_failure_raises_error(self, sample_research_insights):
        """Test that LLM failures are properly propagated."""
        agent = StrategyGeneratorAgent()

        # Mock LLM client to raise exception
        with (
            patch.object(agent.llm_client, "generate", side_effect=Exception("LLM API timeout")),
            pytest.raises(ValueError, match="Strategy generation failed"),
        ):
            await agent.generate_strategy(sample_research_insights)

    def test_strategy_types_coverage(self):
        """Test that all strategy types are valid."""
        agent = StrategyGeneratorAgent()
        valid_types = ["momentum", "value", "event", "reversal", "defensive", "no_strategy"]

        for strategy_type in valid_types:
            strategy_data = {
                "strategy_type": strategy_type,
                "reasoning": "Test reasoning with sufficient length for validation requirements here.",
                "confidence": 0.7,
                "parameters": {
                    "weight_price_trend": 0.15,
                    "weight_rsi_health": 0.15,
                    "weight_momentum": 0.15,
                    "weight_volume": 0.15,
                    "weight_fundamentals": 0.15,
                    "weight_news_sentiment": 0.15,
                    "weight_sector_alignment": 0.10,
                    "min_confirmations": 6,
                    "min_weighted_score": 0.65,
                    "stop_loss_atr_multiplier": 2.0,
                    "max_holding_days": 60,
                    "position_sizing_method": "fixed_dollars",
                    "position_size_value": 10000.00,
                    "rsi_oversold_threshold": 30,
                    "rsi_overbought_threshold": 70,
                    "volume_multiplier_threshold": 0.7,
                    "news_sentiment_threshold": 0.2,
                },
                "expected_characteristics": {
                    "avg_holding_period_days": 45,
                    "expected_win_rate": 0.55,
                    "expected_sharpe": 1.0,
                    "risk_level": "medium",
                },
            }

            result = agent._construct_strategy_result(strategy_data)
            assert result.strategy_type == strategy_type
