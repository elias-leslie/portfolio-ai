"""Company fundamental data fetching and health classification.

This module provides multi-source failover for fetching company fundamentals
(profit margins, revenue growth, debt ratios, analyst ratings) and classifies
companies as EXCELLENT, GOOD, or WEAK based on financial health metrics.

Sources (in priority order):
1. YFinance (free, no API key needed)
2. Finnhub (requires FINNHUB_API_KEY environment variable)
3. Financial Modeling Prep (requires FMP_API_KEY environment variable)

Architecture:
This module serves as the public API facade. Implementation is split across:
- fundamentals_models: Data models (FundamentalData, BaseFundamentalSource)
- fundamentals_sources: Data source implementations and failover logic
- fundamentals_scoring: 4-pillar scoring system calculations
- fundamentals_classifier: Company health classification
- fundamentals_cache: Caching layer with 24-hour TTL
"""

from __future__ import annotations

# Re-export all public APIs for backward compatibility
from app.watchlist.fundamentals_cache import fetch_fundamentals_cached
from app.watchlist.fundamentals_classifier import classify_company_health
from app.watchlist.fundamentals_models import BaseFundamentalSource, FundamentalData
from app.watchlist.fundamentals_scoring import (
    calculate_fundamental_score,
    calculate_growth_score,
    calculate_health_score,
    calculate_sentiment_score,
    calculate_valuation_score,
)
from app.watchlist.fundamentals_sources import (
    FinnhubSource,
    FMPSource,
    YFinanceSource,
    fetch_fundamentals,
)

__all__ = [
    "BaseFundamentalSource",
    "FMPSource",
    "FinnhubSource",
    "FundamentalData",
    "YFinanceSource",
    "calculate_fundamental_score",
    "calculate_growth_score",
    "calculate_health_score",
    "calculate_sentiment_score",
    "calculate_valuation_score",
    "classify_company_health",
    "fetch_fundamentals",
    "fetch_fundamentals_cached",
]
