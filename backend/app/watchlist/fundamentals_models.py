"""Company fundamental data models.

This module defines the data structures for company fundamentals including
profit margins, revenue growth, debt ratios, analyst ratings, and scoring metrics.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel


class FundamentalData(BaseModel):
    """Company fundamental data model."""

    symbol: str
    profit_margin: float | None = None  # Profit margin as decimal (0.53 = 53%)
    revenue_growth: float | None = None  # Revenue growth as decimal (1.22 = 122%)
    debt_to_equity: float | None = None  # Debt-to-equity ratio (0.45 = 45%)
    recommendation_key: str | None = None  # "buy", "hold", "sell"
    recommendation_mean: float | None = None  # 1.0-5.0 (1=strong buy, 5=sell)
    target_mean_price: float | None = None  # Analyst average target price

    # 4-pillar scores (calculated)
    fundamental_score: float | None = None  # Overall 0-100
    valuation_score: float | None = None  # 0-100
    growth_score: float | None = None  # 0-100
    health_score: float | None = None  # 0-100
    sentiment_score: float | None = None  # 0-100 (blended analyst + news)

    # News sentiment (GAP-015)
    news_sentiment_score: float | None = None  # 0-100 from news_cache aggregation


class BaseFundamentalSource(ABC):
    """Abstract base class for fundamental data sources."""

    @abstractmethod
    def fetch_fundamentals(self, symbol: str) -> FundamentalData | None:
        """Fetch fundamental data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            FundamentalData if successful, None if failed
        """
        pass
