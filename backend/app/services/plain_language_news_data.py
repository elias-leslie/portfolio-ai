"""Data constants and private classification helpers for plain language news.

Contains static lookup tables, category sets, and low-level text classifiers
used by the public helper functions.
"""

from __future__ import annotations

from ._plain_language_news_classifiers import (
    _classify_analyst_exec_guidance_dividend,
    _classify_earnings,
    _classify_insider,
    _classify_misc,
    _classify_sec_filing,
)
from .plain_language_news_types import EventCategory

__all__ = [
    "IMPACT_MAP",
    "MODERATELY_BEARISH",
    "MODERATELY_BULLISH",
    "STRONGLY_BEARISH",
    "STRONGLY_BULLISH",
    "_classify_analyst_exec_guidance_dividend",
    "_classify_earnings",
    "_classify_insider",
    "_classify_misc",
    "_classify_sec_filing",
]

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
