"""Helper functions for plain language news translation.

Contains classification, insight generation, and impact summary logic
extracted from plain_language_news.py to keep each module focused.
"""

from __future__ import annotations

from ..logging_config import get_logger
from .plain_language_news_data import (
    IMPACT_MAP,
    MODERATELY_BEARISH,
    MODERATELY_BULLISH,
    STRONGLY_BEARISH,
    STRONGLY_BULLISH,
    _classify_analyst_exec_guidance_dividend,
    _classify_earnings,
    _classify_insider,
    _classify_misc,
    _classify_sec_filing,
)
from .plain_language_news_types import EventCategory

logger = get_logger(__name__)


def classify_event_category(
    headline: str,
    summary: str | None = None,
    filing_type: str | None = None,
) -> EventCategory:
    """Classify news event into a category based on headline and summary.

    Args:
        headline: News headline
        summary: Optional news summary
        filing_type: Optional SEC filing type (8-K, 10-Q, etc.)

    Returns:
        EventCategory enum value
    """
    text = (headline + " " + (summary or "")).lower()
    for fn in (
        lambda t: _classify_sec_filing(t, filing_type) if filing_type else None,
        _classify_earnings,
        _classify_insider,
        _classify_analyst_exec_guidance_dividend,
        _classify_misc,
    ):
        result = fn(text)
        if result is not None:
            return result
    return EventCategory.UNKNOWN


def _insight_by_category(category: EventCategory) -> str | None:
    """Return a fixed-text insight for specific non-bulk categories."""
    if category == EventCategory.INSIDER_BUY_SMALL:
        return "Mildly bullish - insiders buying is usually good"
    if category == EventCategory.INSIDER_SELL_SMALL:
        return "Often routine - don't overreact unless repeated"
    if category in (EventCategory.EXEC_CHANGE_CEO, EventCategory.EXEC_CHANGE_CFO):
        return "Leadership change - wait to see new direction"
    if category == EventCategory.M_AND_A_ANNOUNCED:
        return "Deal announced - wait for details and shareholder vote"
    return None


def generate_actionable_insight(  # noqa: PLR0911
    category: EventCategory,
    sentiment_score: float | None,
    symbol: str,
    in_watchlist: bool = False,
) -> str:
    """Generate actionable insight answering 'What should I do?'

    Args:
        category: Event category
        sentiment_score: Sentiment score (-1 to 1, or None)
        symbol: Stock symbol
        in_watchlist: Whether symbol is in user's watchlist

    Returns:
        Plain-language actionable recommendation
    """
    if category in STRONGLY_BULLISH:
        return (
            "Good news - consider adding to your position if you own it"
            if in_watchlist
            else "Strong bullish signal - worth researching for potential entry"
        )
    if category in MODERATELY_BULLISH:
        return "Positive development - hold and monitor" if in_watchlist else "Bullish news - add to research list"
    if category in STRONGLY_BEARISH:
        return (
            "Bad news - review your position and risk tolerance"
            if in_watchlist
            else "Bearish signal - avoid or wait for clarity"
        )
    if category in MODERATELY_BEARISH:
        return "Concerning news - monitor closely" if in_watchlist else "Caution warranted - wait for more information"
    specific = _insight_by_category(category)
    if specific is not None:
        return specific
    if sentiment_score is not None:
        if sentiment_score > 0.3:
            return "Positive sentiment - worth investigating"
        if sentiment_score < -0.3:
            return "Negative sentiment - proceed with caution"
    return "News reported - read the details before acting"


def generate_impact_summary(category: EventCategory, sentiment_score: float | None = None) -> str:
    """Generate impact summary explaining 'What does this mean for traders?'

    Args:
        category: Event category
        sentiment_score: Optional sentiment score for context

    Returns:
        Plain-language impact explanation
    """
    impact = IMPACT_MAP.get(category)
    if impact:
        return impact
    if sentiment_score is not None:
        if sentiment_score > 0.5:
            return "Very positive news - may create short-term momentum"
        if sentiment_score > 0.2:
            return "Mildly positive - modest upside possible"
        if sentiment_score < -0.5:
            return "Very negative news - may trigger selling pressure"
        if sentiment_score < -0.2:
            return "Mildly negative - modest downside risk"
    return "News reported - assess impact based on your strategy"
