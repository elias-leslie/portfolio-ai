"""Private text-classification helpers for plain language news.

Low-level classifiers that map news text to EventCategory values.
These functions are intentionally private (underscore prefix) and
consumed exclusively by plain_language_news_data.py re-exports.
"""

from __future__ import annotations

from .plain_language_news_types import EventCategory


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
