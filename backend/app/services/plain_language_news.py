"""Plain language news translation and actionable insights.

Converts financial news jargon into plain language that everyday people can understand.
Generates actionable insights that answer "What should I do?" and impact summaries
that explain "What does this mean for traders?"

Zero jargon rule: No financial terms like "EPS", "guidance", "EBITDA" without explanation.

Public API is re-exported from submodules:
  - plain_language_news_types: EventCategory enum
  - plain_language_news_helpers: classify_event_category, generate_actionable_insight,
    generate_impact_summary
"""

from __future__ import annotations

from .plain_language_news_helpers import (
    classify_event_category,
    generate_actionable_insight,
    generate_impact_summary,
)
from .plain_language_news_types import EventCategory

__all__ = [
    "EventCategory",
    "classify_event_category",
    "generate_actionable_insight",
    "generate_impact_summary",
]
