"""Research aggregation subpackage.

Organized modules:
- news_intelligence: News sentiment and material events
- fundamental_analysis: Company health and valuation metrics
- technical_analysis: Trend, momentum, and volume analysis
- macro_context: Fear & Greed, market regime
- sector_strength: Sector relative strength vs SPY
"""

from .fundamental_analysis import aggregate_fundamental_analysis
from .macro_context import aggregate_macro_context
from .news_intelligence import aggregate_news_intelligence
from .sector_strength import aggregate_sector_strength
from .technical_analysis import aggregate_technical_analysis

__all__ = [
    "aggregate_fundamental_analysis",
    "aggregate_macro_context",
    "aggregate_news_intelligence",
    "aggregate_sector_strength",
    "aggregate_technical_analysis",
]
