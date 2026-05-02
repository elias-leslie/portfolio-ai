"""Strategy generation agent powered by LLM analysis.

This module implements an LLM agent that analyzes ResearchInsights and generates
trading strategy configurations with weighted confirmations and risk parameters.
"""

from __future__ import annotations

import json
from typing import Any

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.agents.clients.base_client import LLMResponse
from app.logging_config import get_logger
from app.services.agent_hub_prompt_service import render_agent_hub_prompt, require_agent_hub_prompt

from .models import (
    ExpectedCharacteristics,
    ResearchInsights,
    StrategyGenerationResult,
    StrategyParameters,
)

logger = get_logger(__name__)

STRATEGY_GENERATOR_PROMPT = "portfolio-strategy-generator-template"
STRATEGY_GENERATOR_SYSTEM_PROMPT = "portfolio-strategy-generator-system"


class StrategyGeneratorAgent:
    """Agent that generates trading strategies from market research."""

    def __init__(self) -> None:
        """Initialize strategy generator agent."""
        self.llm_client = AgentHubAPIClient(agent_slug="trade-manager")

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

        prompt = render_agent_hub_prompt(
            STRATEGY_GENERATOR_PROMPT,
            research_json=research_json,
        )

        logger.info(
            f"Generating strategy for {research.symbol} "
            f"(confidence={research.overall_confidence:.2f}, quality={research.research_quality})"
        )

        # Call LLM
        try:
            response: LLMResponse = self.llm_client.generate(
                prompt=prompt,
                system=require_agent_hub_prompt(STRATEGY_GENERATOR_SYSTEM_PROMPT),
                purpose="strategy_generation",
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
                "strategy_generated",
                symbol=research.symbol,
                strategy_type=result.strategy_type,
                confidence=round(result.confidence, 2),
            )

            return result

        except Exception as e:
            logger.exception("strategy_generation_failed", error=str(e))
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
            logger.error("strategy_json_parse_failed", error=str(e), content_preview=content[:100], exc_info=True)
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

        # Cast to dict[str, Any] for explicit return type
        result: dict[str, Any] = strategy_data
        return result

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
            logger.error("strategy_validation_failed", error=str(e), exc_info=True)
            raise ValueError(f"Invalid strategy configuration: {e}") from e


# Singleton instance
_generator_instance: StrategyGeneratorAgent | None = None


def get_strategy_generator() -> StrategyGeneratorAgent:
    """Get singleton instance of strategy generator agent."""
    global _generator_instance  # noqa: PLW0603
    if _generator_instance is None:
        _generator_instance = StrategyGeneratorAgent()
    return _generator_instance
