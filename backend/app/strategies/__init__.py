"""Dynamic strategy generation system.

This package implements research-driven strategy generation that extends
the existing signal_classifier system with LLM-powered insights.

See ARCHITECTURE.md for complete design documentation.
"""

from app.strategies.models import ResearchInsights, StrategyGenerationResult

__all__ = [
    "ResearchInsights",
    "StrategyGenerationResult",
]
