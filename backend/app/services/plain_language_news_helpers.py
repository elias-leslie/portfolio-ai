"""Helper functions for plain language news translation.

Contains classification, insight generation, and impact summary logic
extracted from plain_language_news.py to keep each module focused.
"""

from __future__ import annotations

from ..logging_config import get_logger
from .plain_language_news_types import EventCategory

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def _classify_sec_filing(text: str, filing_type: str) -> EventCategory | None:  # noqa: PLR0911
    """Classify event from SEC filing type context."""
    if filing_type in ("8-K", "8-K/A"):
        if any(w in text for w in ["earnings", "quarter", "revenue", "profit"]):
            if any(w in text for w in ["beat", "exceed", "strong", "surge"]):
                return EventCategory.EARNINGS_BEAT
            if any(w in text for w in ["miss", "weak", "below", "disappoint"]):
                return EventCategory.EARNINGS_MISS
            return EventCategory.EARNINGS_MIXED
        if any(w in text for w in ["merger", "acquisition", "acquire", "buy"]):
            if "announced" in text or "agree" in text:
                return EventCategory.M_AND_A_ANNOUNCED
            if "completed" in text or "closed" in text:
                return EventCategory.M_AND_A_COMPLETED
    if filing_type == "Form 4":
        if "buy" in text or "purchase" in text:
            return EventCategory.INSIDER_BUY_LARGE
        if "sell" in text or "sale" in text:
            return EventCategory.INSIDER_SELL_LARGE
    return None


def _classify_earnings(text: str) -> EventCategory | None:
    """Classify earnings-related events."""
    if not any(w in text for w in ["earnings", "quarter", "q1", "q2", "q3", "q4", "revenue"]):
        return None
    if any(w in text for w in ["beat", "exceed", "strong", "surge", "top"]):
        return EventCategory.EARNINGS_BEAT
    if any(w in text for w in ["miss", "weak", "below", "disappoint", "fall"]):
        return EventCategory.EARNINGS_MISS
    return None


def _classify_insider(text: str) -> EventCategory | None:
    """Classify insider trading events."""
    if not any(w in text for w in ["insider", "executive", "ceo", "cfo", "director"]):
        return None
    if any(w in text for w in ["buy", "bought", "purchase"]):
        if any(w in text for w in ["million", "$1m", "$2m", "$5m", "$10m"]):
            return EventCategory.INSIDER_BUY_LARGE
        return EventCategory.INSIDER_BUY_SMALL
    if any(w in text for w in ["sell", "sold", "sale"]):
        if any(w in text for w in ["million", "$1m", "$2m", "$5m", "$10m"]):
            return EventCategory.INSIDER_SELL_LARGE
        return EventCategory.INSIDER_SELL_SMALL
    return None


def _classify_misc(text: str) -> EventCategory | None:  # noqa: PLR0911
    """Classify miscellaneous event categories."""
    if "buyback" in text or "share repurchase" in text:
        return EventCategory.BUYBACK_ANNOUNCED
    if "split" in text and "stock" in text:
        return EventCategory.SPLIT_ANNOUNCED
    if "fda" in text or "approval" in text:
        if any(w in text for w in ["approve", "approved", "green light"]):
            return EventCategory.FDA_APPROVAL
        if any(w in text for w in ["reject", "denied", "failed"]):
            return EventCategory.FDA_REJECTION
    if any(w in text for w in ["lawsuit", "sue", "sued", "litigation"]):
        if "filed" in text or "file" in text:
            return EventCategory.LAWSUIT_FILED
        if "settled" in text or "settlement" in text:
            return EventCategory.LAWSUIT_SETTLED
    if "sec" in text and any(w in text for w in ["investigation", "probe", "inquiry"]):
        return EventCategory.SEC_INVESTIGATION
    return None


def classify_event_category(  # noqa: PLR0911
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

    if filing_type:
        result = _classify_sec_filing(text, filing_type)
        if result is not None:
            return result

    result = _classify_earnings(text)
    if result is not None:
        return result

    result = _classify_insider(text)
    if result is not None:
        return result

    # Analyst patterns
    if any(w in text for w in ["analyst", "rating", "target"]):
        if any(w in text for w in ["upgrade", "raised", "boost", "increase"]):
            return EventCategory.ANALYST_UPGRADE
        if any(w in text for w in ["downgrade", "lowered", "cut", "reduce"]):
            return EventCategory.ANALYST_DOWNGRADE
        if "initiate" in text or "coverage" in text:
            return EventCategory.ANALYST_INITIATE

    # M&A patterns
    if any(w in text for w in ["merger", "acquisition", "acquire", "takeover"]):
        if "announce" in text or "agree" in text or "proposed" in text:
            return EventCategory.M_AND_A_ANNOUNCED
        if "completed" in text or "closed" in text or "finalized" in text:
            return EventCategory.M_AND_A_COMPLETED

    # Executive change patterns
    if "ceo" in text and any(w in text for w in ["new", "appoint", "hire", "resign", "step down"]):
        return EventCategory.EXEC_CHANGE_CEO
    if "cfo" in text and any(w in text for w in ["new", "appoint", "hire", "resign", "step down"]):
        return EventCategory.EXEC_CHANGE_CFO

    # Guidance patterns
    if "guidance" in text or "outlook" in text or "forecast" in text:
        if any(w in text for w in ["raise", "increase", "boost", "improve"]):
            return EventCategory.GUIDANCE_RAISED
        if any(w in text for w in ["lower", "reduce", "cut", "worsen"]):
            return EventCategory.GUIDANCE_LOWERED

    # Dividend patterns
    if "dividend" in text:
        if any(w in text for w in ["increase", "raise", "boost"]):
            return EventCategory.DIVIDEND_INCREASE
        if any(w in text for w in ["cut", "reduce", "suspend"]):
            return EventCategory.DIVIDEND_CUT

    result = _classify_misc(text)
    if result is not None:
        return result

    return EventCategory.UNKNOWN


# ---------------------------------------------------------------------------
# Impact map for generate_impact_summary
# ---------------------------------------------------------------------------

_IMPACT_MAP: dict[EventCategory, str] = {
    EventCategory.EARNINGS_BEAT: "Strong results may drive stock higher short-term",
    EventCategory.EARNINGS_MISS: "Weak results may pressure stock lower",
    EventCategory.EARNINGS_MIXED: "Mixed signals - stock may be range-bound",
    EventCategory.INSIDER_BUY_LARGE: (
        "Executives with inside info are betting on growth - bullish for long-term holders"
    ),
    EventCategory.INSIDER_BUY_SMALL: "Mild bullish signal - executives showing confidence",
    EventCategory.INSIDER_SELL_LARGE: (
        "Could signal concerns or just portfolio rebalancing - monitor for pattern"
    ),
    EventCategory.INSIDER_SELL_SMALL: (
        "Usually routine selling - not a major red flag unless repeated"
    ),
    EventCategory.ANALYST_UPGRADE: (
        "Institutional buying may follow - short-term momentum likely"
    ),
    EventCategory.ANALYST_DOWNGRADE: (
        "Institutional selling may follow - near-term headwinds"
    ),
    EventCategory.ANALYST_INITIATE: (
        "More Wall Street attention - could increase liquidity and volatility"
    ),
    EventCategory.M_AND_A_ANNOUNCED: (
        "Deal premium typically lifts target stock - wait for regulatory approval"
    ),
    EventCategory.M_AND_A_COMPLETED: (
        "Deal done - target stock may stabilize at buyout price"
    ),
    EventCategory.EXEC_CHANGE_CEO: (
        "New leadership may mean strategy shift - expect volatility"
    ),
    EventCategory.EXEC_CHANGE_CFO: (
        "Financial strategy may change - watch next quarter's results"
    ),
    EventCategory.PRODUCT_LAUNCH: (
        "Revenue potential depends on adoption - watch sales data"
    ),
    EventCategory.PARTNERSHIP: (
        "Could expand market opportunity - assess partner quality"
    ),
    EventCategory.FDA_APPROVAL: "Game-changer for biotech - explosive upside possible",
    EventCategory.FDA_REJECTION: (
        "Major setback - recovery depends on pipeline strength"
    ),
    EventCategory.GUIDANCE_RAISED: (
        "Management sees strength ahead - bullish for next quarter"
    ),
    EventCategory.GUIDANCE_LOWERED: (
        "Management sees weakness - bearish for next quarter"
    ),
    EventCategory.DIVIDEND_INCREASE: (
        "Shows confidence and rewards shareholders - stable income signal"
    ),
    EventCategory.DIVIDEND_CUT: "Company needs cash - red flag for dividend investors",
    EventCategory.BUYBACK_ANNOUNCED: (
        "Company thinks stock is undervalued - supports price"
    ),
    EventCategory.SPLIT_ANNOUNCED: "Cosmetic change only - no fundamental impact",
    EventCategory.LAWSUIT_FILED: (
        "Legal costs and distraction - monitor settlement news"
    ),
    EventCategory.LAWSUIT_SETTLED: "Removes overhang - assess financial impact",
    EventCategory.SEC_INVESTIGATION: "Serious regulatory risk - avoid until resolved",
    EventCategory.REGULATORY_WIN: "Removes barrier to growth - bullish catalyst",
    EventCategory.REGULATORY_LOSS: (
        "Limits growth potential - reassess business model"
    ),
    EventCategory.MARKET_SHARE_GAIN: (
        "Competitive advantage growing - bullish long-term"
    ),
    EventCategory.MARKET_SHARE_LOSS: (
        "Losing ground to rivals - bearish unless reversed"
    ),
}


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
    strongly_bullish = {
        EventCategory.EARNINGS_BEAT,
        EventCategory.INSIDER_BUY_LARGE,
        EventCategory.ANALYST_UPGRADE,
        EventCategory.FDA_APPROVAL,
        EventCategory.GUIDANCE_RAISED,
    }
    moderately_bullish = {
        EventCategory.BUYBACK_ANNOUNCED,
        EventCategory.DIVIDEND_INCREASE,
        EventCategory.PARTNERSHIP,
        EventCategory.PRODUCT_LAUNCH,
        EventCategory.REGULATORY_WIN,
    }
    strongly_bearish = {
        EventCategory.EARNINGS_MISS,
        EventCategory.ANALYST_DOWNGRADE,
        EventCategory.FDA_REJECTION,
        EventCategory.GUIDANCE_LOWERED,
        EventCategory.SEC_INVESTIGATION,
    }
    moderately_bearish = {
        EventCategory.INSIDER_SELL_LARGE,
        EventCategory.DIVIDEND_CUT,
        EventCategory.LAWSUIT_FILED,
        EventCategory.REGULATORY_LOSS,
    }

    if category in strongly_bullish:
        if in_watchlist:
            return "Good news - consider adding to your position if you own it"
        return "Strong bullish signal - worth researching for potential entry"

    if category in moderately_bullish:
        if in_watchlist:
            return "Positive development - hold and monitor"
        return "Bullish news - add to research list"

    if category in strongly_bearish:
        if in_watchlist:
            return "Bad news - review your position and risk tolerance"
        return "Bearish signal - avoid or wait for clarity"

    if category in moderately_bearish:
        if in_watchlist:
            return "Concerning news - monitor closely"
        return "Caution warranted - wait for more information"

    if category == EventCategory.INSIDER_BUY_SMALL:
        return "Mildly bullish - insiders buying is usually good"
    if category == EventCategory.INSIDER_SELL_SMALL:
        return "Often routine - don't overreact unless repeated"
    if category in (EventCategory.EXEC_CHANGE_CEO, EventCategory.EXEC_CHANGE_CFO):
        return "Leadership change - wait to see new direction"
    if category == EventCategory.M_AND_A_ANNOUNCED:
        return "Deal announced - wait for details and shareholder vote"

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
    impact = _IMPACT_MAP.get(category)
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
