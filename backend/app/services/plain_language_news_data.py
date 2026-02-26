"""Data constants and private classification helpers for plain language news.

Contains static lookup tables, category sets, and low-level text classifiers
used by the public helper functions.
"""

from __future__ import annotations

from .plain_language_news_types import EventCategory

# ---------------------------------------------------------------------------
# Impact map: category -> plain-language trader impact
# ---------------------------------------------------------------------------

IMPACT_MAP: dict[EventCategory, str] = {
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

# ---------------------------------------------------------------------------
# Sentiment category sets used by generate_actionable_insight
# ---------------------------------------------------------------------------

STRONGLY_BULLISH: frozenset[EventCategory] = frozenset({
    EventCategory.EARNINGS_BEAT,
    EventCategory.INSIDER_BUY_LARGE,
    EventCategory.ANALYST_UPGRADE,
    EventCategory.FDA_APPROVAL,
    EventCategory.GUIDANCE_RAISED,
})

MODERATELY_BULLISH: frozenset[EventCategory] = frozenset({
    EventCategory.BUYBACK_ANNOUNCED,
    EventCategory.DIVIDEND_INCREASE,
    EventCategory.PARTNERSHIP,
    EventCategory.PRODUCT_LAUNCH,
    EventCategory.REGULATORY_WIN,
})

STRONGLY_BEARISH: frozenset[EventCategory] = frozenset({
    EventCategory.EARNINGS_MISS,
    EventCategory.ANALYST_DOWNGRADE,
    EventCategory.FDA_REJECTION,
    EventCategory.GUIDANCE_LOWERED,
    EventCategory.SEC_INVESTIGATION,
})

MODERATELY_BEARISH: frozenset[EventCategory] = frozenset({
    EventCategory.INSIDER_SELL_LARGE,
    EventCategory.DIVIDEND_CUT,
    EventCategory.LAWSUIT_FILED,
    EventCategory.REGULATORY_LOSS,
})

# ---------------------------------------------------------------------------
# Private text-classification helpers
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


def _classify_analyst_exec_guidance_dividend(text: str) -> EventCategory | None:  # noqa: PLR0911
    """Classify analyst, executive, guidance, and dividend events."""
    if any(w in text for w in ["analyst", "rating", "target"]):
        if any(w in text for w in ["upgrade", "raised", "boost", "increase"]):
            return EventCategory.ANALYST_UPGRADE
        if any(w in text for w in ["downgrade", "lowered", "cut", "reduce"]):
            return EventCategory.ANALYST_DOWNGRADE
        if "initiate" in text or "coverage" in text:
            return EventCategory.ANALYST_INITIATE
    if any(w in text for w in ["merger", "acquisition", "acquire", "takeover"]):
        if "announce" in text or "agree" in text or "proposed" in text:
            return EventCategory.M_AND_A_ANNOUNCED
        if "completed" in text or "closed" in text or "finalized" in text:
            return EventCategory.M_AND_A_COMPLETED
    if "ceo" in text and any(w in text for w in ["new", "appoint", "hire", "resign", "step down"]):
        return EventCategory.EXEC_CHANGE_CEO
    if "cfo" in text and any(w in text for w in ["new", "appoint", "hire", "resign", "step down"]):
        return EventCategory.EXEC_CHANGE_CFO
    if "guidance" in text or "outlook" in text or "forecast" in text:
        if any(w in text for w in ["raise", "increase", "boost", "improve"]):
            return EventCategory.GUIDANCE_RAISED
        if any(w in text for w in ["lower", "reduce", "cut", "worsen"]):
            return EventCategory.GUIDANCE_LOWERED
    if "dividend" in text:
        if any(w in text for w in ["increase", "raise", "boost"]):
            return EventCategory.DIVIDEND_INCREASE
        if any(w in text for w in ["cut", "reduce", "suspend"]):
            return EventCategory.DIVIDEND_CUT
    return None
