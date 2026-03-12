"""Research aggregation service for dynamic strategy generation.

This module collects and structures market research from all available sources:
- News sentiment (30-day rolling analysis)
- Fundamental metrics (company health, valuation, growth)
- Technical indicators (trend, momentum, volume)
- Macro context (Fear & Greed, market regime)
- Sector relative strength (vs SPY benchmark)

Output: ResearchInsights dataclass with confidence scores for each dimension.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Literal

from app.logging_config import get_logger
from app.storage import PortfolioStorage

from .models import ResearchInsights
from .research import (
    aggregate_fundamental_analysis,
    aggregate_macro_context,
    aggregate_news_intelligence,
    aggregate_sector_strength,
    aggregate_technical_analysis,
)

logger = get_logger(__name__)


class ResearchAggregationService:
    """Service for aggregating market research from multiple sources."""

    def __init__(self) -> None:
        """Initialize research aggregation service."""
        self.storage = PortfolioStorage()

    async def aggregate_research(self, symbol: str, lookback_days: int = 30) -> ResearchInsights:
        """Aggregate market research for a symbol.

        Args:
            symbol: Stock symbol
            lookback_days: Days of historical data to analyze (default 30)

        Returns:
            ResearchInsights with confidence scores for each dimension

        Raises:
            ValueError: If symbol not found or insufficient data
        """
        as_of_date = date.today()
        cutoff_date = as_of_date - timedelta(days=lookback_days)

        # Collect data from all sources in parallel (conceptually)
        news_data = aggregate_news_intelligence(self.storage, symbol, cutoff_date, as_of_date)
        fundamental_data = aggregate_fundamental_analysis(symbol)
        technical_data = aggregate_technical_analysis(self.storage, symbol, as_of_date)
        macro_data = aggregate_macro_context(self.storage, as_of_date)
        sector_data = aggregate_sector_strength(self.storage, symbol, as_of_date)

        # Calculate overall confidence (weighted average)
        overall_confidence = self._calculate_overall_confidence(
            news_data["confidence"],
            fundamental_data["confidence"],
            technical_data["confidence"],
            1.0,  # macro always available
            sector_data["confidence"],
        )

        # Classify research quality
        research_quality: Literal["high", "medium", "low"]
        if overall_confidence >= 0.8:
            research_quality = "high"
        elif overall_confidence >= 0.5:
            research_quality = "medium"
        else:
            research_quality = "low"

        return ResearchInsights(
            symbol=symbol,
            as_of_date=as_of_date,
            # News intelligence
            news_sentiment_trend=news_data["sentiment_trend"],
            news_sentiment_score=news_data["sentiment_score"],
            news_sentiment_7d_avg=news_data["sentiment_7d_avg"],
            news_sentiment_30d_avg=news_data["sentiment_30d_avg"],
            material_events=news_data["material_events"],
            news_volume=news_data["news_volume"],
            news_confidence=news_data["confidence"],
            # Fundamental analysis
            company_health=fundamental_data["company_health"],
            fundamental_score=fundamental_data["fundamental_score"],
            valuation_tier=fundamental_data["valuation_tier"],
            growth_tier=fundamental_data["growth_tier"],
            profitability_tier=fundamental_data["profitability_tier"],
            debt_tier=fundamental_data["debt_tier"],
            analyst_consensus=fundamental_data["analyst_consensus"],
            fundamental_confidence=fundamental_data["confidence"],
            # Technical analysis
            trend_strength=technical_data["trend_strength"],
            trend_duration_days=technical_data["trend_duration_days"],
            momentum_rating=technical_data["momentum_rating"],
            volume_profile=technical_data["volume_profile"],
            rsi_zone=technical_data["rsi_zone"],
            price_vs_ma=technical_data["price_vs_ma"],
            technical_confidence=technical_data["confidence"],
            # Macro context
            market_regime=macro_data["market_regime"],
            fear_greed_score=macro_data["fear_greed_score"],
            fear_greed_classification=macro_data["fear_greed_classification"],
            sector_rotation_phase=macro_data["sector_rotation_phase"],
            # Sector strength
            sector=sector_data["sector"],
            sector_momentum=sector_data["sector_momentum"],
            sector_vs_spy_30d=sector_data["sector_vs_spy_30d"],
            sector_rotation_signal=sector_data["sector_rotation_signal"],
            # Overall assessment
            overall_confidence=overall_confidence,
            research_quality=research_quality,
            last_updated=datetime.now(UTC),
        )

    def _calculate_overall_confidence(
        self,
        news_conf: float,
        fundamental_conf: float,
        technical_conf: float,
        macro_conf: float,
        sector_conf: float,
    ) -> float:
        """Calculate weighted average confidence across all dimensions.

        Args:
            news_conf: News intelligence confidence (0-1)
            fundamental_conf: Fundamental analysis confidence (0-1)
            technical_conf: Technical analysis confidence (0-1)
            macro_conf: Macro context confidence (0-1, always 1.0)
            sector_conf: Sector strength confidence (0-1)

        Returns:
            Overall confidence score (0-1)
        """
        # Weights (sum to 1.0)
        weights = {
            "news": 0.25,
            "fundamental": 0.30,
            "technical": 0.30,
            "macro": 0.10,
            "sector": 0.05,
        }

        weighted_sum = (
            news_conf * weights["news"]
            + fundamental_conf * weights["fundamental"]
            + technical_conf * weights["technical"]
            + macro_conf * weights["macro"]
            + sector_conf * weights["sector"]
        )

        return round(weighted_sum, 2)


# Singleton instance
_aggregator_instance: ResearchAggregationService | None = None


def get_research_aggregator() -> ResearchAggregationService:
    """Get singleton instance of research aggregation service."""
    global _aggregator_instance  # noqa: PLW0603
    if _aggregator_instance is None:
        _aggregator_instance = ResearchAggregationService()
    return _aggregator_instance
