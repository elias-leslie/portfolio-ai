"""Type definitions for plain language news translation.

Defines the EventCategory enum used for news event classification.
"""

from __future__ import annotations

from enum import StrEnum


class EventCategory(StrEnum):
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
