"""Strategy generation agent powered by LLM analysis.

This module implements an LLM agent that analyzes ResearchInsights and generates
trading strategy configurations with weighted confirmations and risk parameters.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.agents.llm_client import DualProviderClient, LLMResponse

from .models import (
    ExpectedCharacteristics,
    ResearchInsights,
    StrategyGenerationResult,
    StrategyParameters,
)

logger = logging.getLogger(__name__)

# System prompt template for strategy generation
STRATEGY_GENERATOR_PROMPT = """You are a quantitative trading strategist. Your job is to analyze market research and generate a trading strategy configuration.

**Your Task**:
1. Analyze the research across all dimensions (news, fundamentals, technical, macro, sector)
2. Identify the dominant market theme (e.g., "strong momentum with positive earnings", "sector rotation opportunity")
3. Design a strategy that capitalizes on this theme
4. Generate a JSON configuration with strategy parameters

**Strategy Types to Consider**:
- **Momentum**: Strong uptrend + positive news + sector strength → aggressive entries
- **Value**: Undervalued fundamentals + improving sentiment → patient entries
- **Event**: Material news event + earnings proximity → short-term tactical
- **Reversal**: Oversold technical + improving fundamentals → contrarian entries
- **Defensive**: High volatility + weak sentiment → conservative entries only

**Critical Rules**:
- Confirmation weights MUST sum to exactly 1.0
- All thresholds must be within reasonable ranges (RSI 0-100, sentiment -1 to +1)
- Confidence must reflect research quality (low quality = lower confidence)
- If research is insufficient (overall_confidence < 0.5), recommend "no_strategy" type

**Output Format**:
Respond with ONLY a valid JSON object (no markdown, no explanation outside JSON):

{
  "strategy_type": "momentum|value|event|reversal|defensive|no_strategy",
  "reasoning": "2-3 sentence explanation of why this strategy fits the research",
  "confidence": 0.7,

  "parameters": {
    "weight_price_trend": 0.20,
    "weight_rsi_health": 0.10,
    "weight_momentum": 0.15,
    "weight_volume": 0.10,
    "weight_fundamentals": 0.15,
    "weight_news_sentiment": 0.20,
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
    "news_sentiment_threshold": 0.2
  },

  "expected_characteristics": {
    "avg_holding_period_days": 45,
    "expected_win_rate": 0.55,
    "expected_sharpe": 1.3,
    "risk_level": "medium"
  }
}

**Weight Guidelines**:
- Momentum strategy: Higher weight on momentum (0.25), sector (0.15), price trend (0.20)
- Value strategy: Higher weight on fundamentals (0.30), valuation (via price_trend 0.15)
- Event strategy: Higher weight on news (0.35), volume (0.15)
- Reversal strategy: Higher weight on RSI (0.20), fundamentals (0.25)
- Defensive strategy: Balanced weights (0.14-0.15 each), high min_weighted_score (0.70)

**Risk Level Guidelines**:
- Low: Sharpe > 2.0, win rate > 0.65, conservative thresholds
- Medium-low: Sharpe 1.5-2.0, win rate 0.55-0.65
- Medium: Sharpe 1.0-1.5, win rate 0.50-0.55
- Medium-high: Sharpe 0.7-1.0, win rate 0.45-0.50
- High: Sharpe < 0.7, win rate < 0.45 (event trading, high risk)
"""


class StrategyGeneratorAgent:
    """Agent that generates trading strategies from market research."""

    def __init__(self) -> None:
        """Initialize strategy generator agent."""
        self.llm_client = DualProviderClient(
            primary="gemini",  # Fast and cheap
        )

    async def generate_strategy(self, research: ResearchInsights) -> StrategyGenerationResult:
        """Generate trading strategy from research insights.

        Args:
            research: Aggregated market research

        Returns:
            StrategyGenerationResult with configuration and reasoning

        Raises:
            ValueError: If generation fails or produces invalid output
        """
        # Format research into prompt
        research_json = self._format_research_prompt(research)

        prompt = f"""**Input Research Summary**:
{research_json}

Based on this research, generate a trading strategy configuration as valid JSON.
"""

        logger.info(
            f"Generating strategy for {research.symbol} "
            f"(confidence={research.overall_confidence:.2f}, quality={research.research_quality})"
        )

        # Call LLM
        try:
            response: LLMResponse = self.llm_client.generate(
                prompt=prompt,
                system=STRATEGY_GENERATOR_PROMPT,
                max_tokens=2000,
                temperature=0.3,  # Low temperature for consistent output
            )

            logger.info(
                f"LLM response received from {response.provider} ({response.model}), "
                f"tokens: {response.usage}"
            )

            # Parse JSON response
            strategy_data = self._parse_strategy_json(response.content)

            # Validate and construct result
            result = self._construct_strategy_result(strategy_data)

            logger.info(
                f"Strategy generated successfully: {research.symbol} -> {result.strategy_type} "
                f"(confidence={result.confidence:.2f})"
            )

            return result

        except Exception as e:
            logger.exception(f"Strategy generation failed: {e}")
            raise ValueError(f"Strategy generation failed: {e}") from e

    def _format_research_prompt(self, research: ResearchInsights) -> str:
        """Format research insights into prompt text.

        Args:
            research: Research insights dataclass

        Returns:
            Formatted JSON string
        """
        # Convert dataclass to dict
        research_dict = {
            "symbol": research.symbol,
            "as_of_date": research.as_of_date.isoformat(),
            "news": {
                "sentiment_trend": research.news_sentiment_trend,
                "sentiment_score": research.news_sentiment_score,
                "sentiment_7d_avg": research.news_sentiment_7d_avg,
                "sentiment_30d_avg": research.news_sentiment_30d_avg,
                "material_events": research.material_events,
                "news_volume": research.news_volume,
                "confidence": research.news_confidence,
            },
            "fundamentals": {
                "company_health": research.company_health,
                "fundamental_score": research.fundamental_score,
                "valuation_tier": research.valuation_tier,
                "growth_tier": research.growth_tier,
                "profitability_tier": research.profitability_tier,
                "debt_tier": research.debt_tier,
                "analyst_consensus": research.analyst_consensus,
                "confidence": research.fundamental_confidence,
            },
            "technical": {
                "trend_strength": research.trend_strength,
                "trend_duration_days": research.trend_duration_days,
                "momentum_rating": research.momentum_rating,
                "volume_profile": research.volume_profile,
                "rsi_zone": research.rsi_zone,
                "price_vs_ma": research.price_vs_ma,
                "confidence": research.technical_confidence,
            },
            "macro": {
                "market_regime": research.market_regime,
                "fear_greed_score": research.fear_greed_score,
                "fear_greed_classification": research.fear_greed_classification,
                "sector_rotation_phase": research.sector_rotation_phase,
            },
            "sector": {
                "sector": research.sector,
                "sector_momentum": research.sector_momentum,
                "sector_vs_spy_30d": research.sector_vs_spy_30d,
                "sector_rotation_signal": research.sector_rotation_signal,
            },
            "overall": {
                "confidence": research.overall_confidence,
                "quality": research.research_quality,
            },
        }

        return json.dumps(research_dict, indent=2)

    def _parse_strategy_json(self, content: str) -> dict[str, Any]:
        """Parse LLM response content into strategy dict.

        Args:
            content: Raw LLM response text

        Returns:
            Parsed strategy dictionary

        Raises:
            ValueError: If JSON parsing fails or format invalid
        """
        # Clean content (remove markdown code blocks if present)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # Parse JSON
        try:
            strategy_data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse strategy JSON: {e} (content: {content[:100]}...)")
            raise ValueError(f"Invalid JSON response: {e}") from e

        # Validate required fields
        required_fields = [
            "strategy_type",
            "reasoning",
            "confidence",
            "parameters",
            "expected_characteristics",
        ]
        for field in required_fields:
            if field not in strategy_data:
                raise ValueError(f"Missing required field: {field}")

        return strategy_data

    def _construct_strategy_result(self, strategy_data: dict[str, Any]) -> StrategyGenerationResult:
        """Construct validated StrategyGenerationResult from parsed data.

        Args:
            strategy_data: Parsed strategy dictionary

        Returns:
            StrategyGenerationResult with validated Pydantic models

        Raises:
            ValueError: If validation fails
        """
        try:
            # Construct StrategyParameters (Pydantic validates weights sum to 1.0)
            parameters = StrategyParameters(**strategy_data["parameters"])

            # Construct ExpectedCharacteristics
            expected_characteristics = ExpectedCharacteristics(
                **strategy_data["expected_characteristics"]
            )

            # Construct full result
            result = StrategyGenerationResult(
                strategy_type=strategy_data["strategy_type"],
                reasoning=strategy_data["reasoning"],
                confidence=strategy_data["confidence"],
                parameters=parameters,
                expected_characteristics=expected_characteristics,
            )

            return result

        except Exception as e:
            logger.error(f"Strategy validation failed: {e}")
            raise ValueError(f"Invalid strategy configuration: {e}") from e


# Singleton instance
_generator_instance: StrategyGeneratorAgent | None = None


def get_strategy_generator() -> StrategyGeneratorAgent:
    """Get singleton instance of strategy generator agent."""
    global _generator_instance
    if _generator_instance is None:
        _generator_instance = StrategyGeneratorAgent()
    return _generator_instance
