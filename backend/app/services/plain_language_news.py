"""Plain language news translation and actionable insights.

Converts financial news jargon into plain language that everyday people can understand.
Generates actionable insights that answer "What should I do?" and impact summaries
that explain "What does this mean for traders?"

Zero jargon rule: No financial terms like "EPS", "guidance", "EBITDA" without explanation.
"""

from __future__ import annotations

from enum import Enum

from ..logging_config import get_logger

logger = get_logger(__name__)


class EventCategory(str, Enum):
    """News event categories for pattern matching."""

    EARNINGS_BEAT = "earnings_beat"
    EARNINGS_MISS = "earnings_miss"
    EARNINGS_MIXED = "earnings_mixed"
    INSIDER_BUY_LARGE = "insider_buy_large"
    INSIDER_BUY_SMALL = "insider_buy_small"
    INSIDER_SELL_LARGE = "insider_sell_large"
    INSIDER_SELL_SMALL = "insider_sell_small"
    ANALYST_UPGRADE = "analyst_upgrade"
    ANALYST_DOWNGRADE = "analyst_downgrade"
    ANALYST_INITIATE = "analyst_initiate"
    M_AND_A_ANNOUNCED = "m_and_a_announced"
    M_AND_A_COMPLETED = "m_and_a_completed"
    EXEC_CHANGE_CEO = "exec_change_ceo"
    EXEC_CHANGE_CFO = "exec_change_cfo"
    PRODUCT_LAUNCH = "product_launch"
    PARTNERSHIP = "partnership"
    FDA_APPROVAL = "fda_approval"
    FDA_REJECTION = "fda_rejection"
    LAWSUIT_FILED = "lawsuit_filed"
    LAWSUIT_SETTLED = "lawsuit_settled"
    GUIDANCE_RAISED = "guidance_raised"
    GUIDANCE_LOWERED = "guidance_lowered"
    DIVIDEND_INCREASE = "dividend_increase"
    DIVIDEND_CUT = "dividend_cut"
    BUYBACK_ANNOUNCED = "buyback_announced"
    SPLIT_ANNOUNCED = "split_announced"
    SEC_INVESTIGATION = "sec_investigation"
    REGULATORY_WIN = "regulatory_win"
    REGULATORY_LOSS = "regulatory_loss"
    MARKET_SHARE_GAIN = "market_share_gain"
    MARKET_SHARE_LOSS = "market_share_loss"
    UNKNOWN = "unknown"


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

    # SEC filing patterns
    if filing_type:
        if filing_type in ("8-K", "8-K/A"):
            # 8-K is for material events - check what kind
            if any(word in text for word in ["earnings", "quarter", "revenue", "profit"]):
                if any(word in text for word in ["beat", "exceed", "strong", "surge"]):
                    return EventCategory.EARNINGS_BEAT
                if any(word in text for word in ["miss", "weak", "below", "disappoint"]):
                    return EventCategory.EARNINGS_MISS
                return EventCategory.EARNINGS_MIXED
            if any(word in text for word in ["merger", "acquisition", "acquire", "buy"]):
                if "announced" in text or "agree" in text:
                    return EventCategory.M_AND_A_ANNOUNCED
                if "completed" in text or "closed" in text:
                    return EventCategory.M_AND_A_COMPLETED
        elif filing_type == "Form 4":
            # Insider trading
            if "buy" in text or "purchase" in text:
                return EventCategory.INSIDER_BUY_LARGE
            if "sell" in text or "sale" in text:
                return EventCategory.INSIDER_SELL_LARGE

    # Earnings patterns
    if any(word in text for word in ["earnings", "quarter", "q1", "q2", "q3", "q4", "revenue"]):
        if any(word in text for word in ["beat", "exceed", "strong", "surge", "top"]):
            return EventCategory.EARNINGS_BEAT
        if any(word in text for word in ["miss", "weak", "below", "disappoint", "fall"]):
            return EventCategory.EARNINGS_MISS

    # Insider trading patterns
    if any(word in text for word in ["insider", "executive", "ceo", "cfo", "director"]):
        if any(word in text for word in ["buy", "bought", "purchase"]):
            if any(word in text for word in ["million", "$1m", "$2m", "$5m", "$10m"]):
                return EventCategory.INSIDER_BUY_LARGE
            return EventCategory.INSIDER_BUY_SMALL
        if any(word in text for word in ["sell", "sold", "sale"]):
            if any(word in text for word in ["million", "$1m", "$2m", "$5m", "$10m"]):
                return EventCategory.INSIDER_SELL_LARGE
            return EventCategory.INSIDER_SELL_SMALL

    # Analyst patterns
    if any(word in text for word in ["analyst", "rating", "target"]):
        if any(word in text for word in ["upgrade", "raised", "boost", "increase"]):
            return EventCategory.ANALYST_UPGRADE
        if any(word in text for word in ["downgrade", "lowered", "cut", "reduce"]):
            return EventCategory.ANALYST_DOWNGRADE
        if "initiate" in text or "coverage" in text:
            return EventCategory.ANALYST_INITIATE

    # M&A patterns
    if any(word in text for word in ["merger", "acquisition", "acquire", "takeover"]):
        if "announce" in text or "agree" in text or "proposed" in text:
            return EventCategory.M_AND_A_ANNOUNCED
        if "completed" in text or "closed" in text or "finalized" in text:
            return EventCategory.M_AND_A_COMPLETED

    # Executive change patterns
    if "ceo" in text and any(
        word in text for word in ["new", "appoint", "hire", "resign", "step down"]
    ):
        return EventCategory.EXEC_CHANGE_CEO
    if "cfo" in text and any(
        word in text for word in ["new", "appoint", "hire", "resign", "step down"]
    ):
        return EventCategory.EXEC_CHANGE_CFO

    # Guidance patterns
    if "guidance" in text or "outlook" in text or "forecast" in text:
        if any(word in text for word in ["raise", "increase", "boost", "improve"]):
            return EventCategory.GUIDANCE_RAISED
        if any(word in text for word in ["lower", "reduce", "cut", "worsen"]):
            return EventCategory.GUIDANCE_LOWERED

    # Dividend patterns
    if "dividend" in text:
        if any(word in text for word in ["increase", "raise", "boost"]):
            return EventCategory.DIVIDEND_INCREASE
        if any(word in text for word in ["cut", "reduce", "suspend"]):
            return EventCategory.DIVIDEND_CUT

    # Other patterns
    if "buyback" in text or "share repurchase" in text:
        return EventCategory.BUYBACK_ANNOUNCED
    if "split" in text and "stock" in text:
        return EventCategory.SPLIT_ANNOUNCED
    if "fda" in text or "approval" in text:
        if any(word in text for word in ["approve", "approved", "green light"]):
            return EventCategory.FDA_APPROVAL
        if any(word in text for word in ["reject", "denied", "failed"]):
            return EventCategory.FDA_REJECTION
    if any(word in text for word in ["lawsuit", "sue", "sued", "litigation"]):
        if "filed" in text or "file" in text:
            return EventCategory.LAWSUIT_FILED
        if "settled" in text or "settlement" in text:
            return EventCategory.LAWSUIT_SETTLED
    if "sec" in text and any(word in text for word in ["investigation", "probe", "inquiry"]):
        return EventCategory.SEC_INVESTIGATION

    return EventCategory.UNKNOWN


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
    # Strongly bullish events
    if category in (
        EventCategory.EARNINGS_BEAT,
        EventCategory.INSIDER_BUY_LARGE,
        EventCategory.ANALYST_UPGRADE,
        EventCategory.FDA_APPROVAL,
        EventCategory.GUIDANCE_RAISED,
    ):
        if in_watchlist:
            return "Good news - consider adding to your position if you own it"
        return "Strong bullish signal - worth researching for potential entry"

    # Moderately bullish events
    if category in (
        EventCategory.BUYBACK_ANNOUNCED,
        EventCategory.DIVIDEND_INCREASE,
        EventCategory.PARTNERSHIP,
        EventCategory.PRODUCT_LAUNCH,
        EventCategory.REGULATORY_WIN,
    ):
        if in_watchlist:
            return "Positive development - hold and monitor"
        return "Bullish news - add to research list"

    # Strongly bearish events
    if category in (
        EventCategory.EARNINGS_MISS,
        EventCategory.ANALYST_DOWNGRADE,
        EventCategory.FDA_REJECTION,
        EventCategory.GUIDANCE_LOWERED,
        EventCategory.SEC_INVESTIGATION,
    ):
        if in_watchlist:
            return "Bad news - review your position and risk tolerance"
        return "Bearish signal - avoid or wait for clarity"

    # Moderately bearish events
    if category in (
        EventCategory.INSIDER_SELL_LARGE,
        EventCategory.DIVIDEND_CUT,
        EventCategory.LAWSUIT_FILED,
        EventCategory.REGULATORY_LOSS,
    ):
        if in_watchlist:
            return "Concerning news - monitor closely"
        return "Caution warranted - wait for more information"

    # Neutral/mixed events
    if category == EventCategory.INSIDER_BUY_SMALL:
        return "Mildly bullish - insiders buying is usually good"
    if category == EventCategory.INSIDER_SELL_SMALL:
        return "Often routine - don't overreact unless repeated"
    if category in (EventCategory.EXEC_CHANGE_CEO, EventCategory.EXEC_CHANGE_CFO):
        return "Leadership change - wait to see new direction"
    if category == EventCategory.M_AND_A_ANNOUNCED:
        return "Deal announced - wait for details and shareholder vote"

    # Use sentiment as fallback
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
    impact_map: dict[EventCategory, str] = {
        # Earnings
        EventCategory.EARNINGS_BEAT: "Strong results may drive stock higher short-term",
        EventCategory.EARNINGS_MISS: "Weak results may pressure stock lower",
        EventCategory.EARNINGS_MIXED: "Mixed signals - stock may be range-bound",
        # Insider trading
        EventCategory.INSIDER_BUY_LARGE: "Executives with inside info are betting on growth - bullish for long-term holders",
        EventCategory.INSIDER_BUY_SMALL: "Mild bullish signal - executives showing confidence",
        EventCategory.INSIDER_SELL_LARGE: "Could signal concerns or just portfolio rebalancing - monitor for pattern",
        EventCategory.INSIDER_SELL_SMALL: "Usually routine selling - not a major red flag unless repeated",
        # Analyst
        EventCategory.ANALYST_UPGRADE: "Institutional buying may follow - short-term momentum likely",
        EventCategory.ANALYST_DOWNGRADE: "Institutional selling may follow - near-term headwinds",
        EventCategory.ANALYST_INITIATE: "More Wall Street attention - could increase liquidity and volatility",
        # M&A
        EventCategory.M_AND_A_ANNOUNCED: "Deal premium typically lifts target stock - wait for regulatory approval",
        EventCategory.M_AND_A_COMPLETED: "Deal done - target stock may stabilize at buyout price",
        # Executive changes
        EventCategory.EXEC_CHANGE_CEO: "New leadership may mean strategy shift - expect volatility",
        EventCategory.EXEC_CHANGE_CFO: "Financial strategy may change - watch next quarter's results",
        # Product/partnership
        EventCategory.PRODUCT_LAUNCH: "Revenue potential depends on adoption - watch sales data",
        EventCategory.PARTNERSHIP: "Could expand market opportunity - assess partner quality",
        # FDA
        EventCategory.FDA_APPROVAL: "Game-changer for biotech - explosive upside possible",
        EventCategory.FDA_REJECTION: "Major setback - recovery depends on pipeline strength",
        # Guidance
        EventCategory.GUIDANCE_RAISED: "Management sees strength ahead - bullish for next quarter",
        EventCategory.GUIDANCE_LOWERED: "Management sees weakness - bearish for next quarter",
        # Dividend/buyback
        EventCategory.DIVIDEND_INCREASE: "Shows confidence and rewards shareholders - stable income signal",
        EventCategory.DIVIDEND_CUT: "Company needs cash - red flag for dividend investors",
        EventCategory.BUYBACK_ANNOUNCED: "Company thinks stock is undervalued - supports price",
        EventCategory.SPLIT_ANNOUNCED: "Cosmetic change only - no fundamental impact",
        # Legal/regulatory
        EventCategory.LAWSUIT_FILED: "Legal costs and distraction - monitor settlement news",
        EventCategory.LAWSUIT_SETTLED: "Removes overhang - assess financial impact",
        EventCategory.SEC_INVESTIGATION: "Serious regulatory risk - avoid until resolved",
        EventCategory.REGULATORY_WIN: "Removes barrier to growth - bullish catalyst",
        EventCategory.REGULATORY_LOSS: "Limits growth potential - reassess business model",
        # Market position
        EventCategory.MARKET_SHARE_GAIN: "Competitive advantage growing - bullish long-term",
        EventCategory.MARKET_SHARE_LOSS: "Losing ground to rivals - bearish unless reversed",
    }

    impact = impact_map.get(category)
    if impact:
        return impact

    # Fallback to sentiment
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
