"""Private text-classification helpers for plain language news.

Low-level classifiers mapping news text to EventCategory values,
consumed exclusively by plain_language_news_data.py re-exports.
"""

from __future__ import annotations

from .plain_language_news_types import EventCategory

_EARNINGS = ("earnings", "quarter", "q1", "q2", "q3", "q4", "revenue")
_BEAT = ("beat", "exceed", "strong", "surge", "top")
_MISS = ("miss", "weak", "below", "disappoint", "fall")
_MA_ANNOUNCE = ("announced", "agree", "proposed")
_MA_COMPLETE = ("completed", "closed", "finalized")
_EXEC_CHANGE = ("new", "appoint", "hire", "resign", "step down")
_BIG_AMOUNT = ("million", "$1m", "$2m", "$5m", "$10m")
_INSIDER_ROLES = ("insider", "executive", "ceo", "cfo", "director")


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def _classify_sec_filing(text: str, filing_type: str) -> EventCategory | None:  # noqa: PLR0911
    """Classify event from SEC filing type context."""
    if filing_type in ("8-K", "8-K/A"):
        if _has(text, ("earnings", "quarter", "revenue", "profit")):
            if _has(text, ("beat", "exceed", "strong", "surge")):
                return EventCategory.EARNINGS_BEAT
            return EventCategory.EARNINGS_MISS if _has(text, ("miss", "weak", "below", "disappoint")) else EventCategory.EARNINGS_MIXED
        if _has(text, ("merger", "acquisition", "acquire", "buy")):
            if "announced" in text or "agree" in text:
                return EventCategory.M_AND_A_ANNOUNCED
            if "completed" in text or "closed" in text:
                return EventCategory.M_AND_A_COMPLETED
        return None
    if filing_type != "Form 4":
        return None
    if "buy" in text or "purchase" in text:
        return EventCategory.INSIDER_BUY_LARGE
    if "sell" in text or "sale" in text:
        return EventCategory.INSIDER_SELL_LARGE
    return None


def _classify_earnings(text: str) -> EventCategory | None:
    """Classify earnings-related events."""
    if not _has(text, _EARNINGS):
        return None
    if _has(text, _BEAT):
        return EventCategory.EARNINGS_BEAT
    if _has(text, _MISS):
        return EventCategory.EARNINGS_MISS
    return None


def _classify_insider(text: str) -> EventCategory | None:
    """Classify insider trading events."""
    if not _has(text, _INSIDER_ROLES):
        return None
    is_large = _has(text, _BIG_AMOUNT)
    if _has(text, ("buy", "bought", "purchase")):
        return EventCategory.INSIDER_BUY_LARGE if is_large else EventCategory.INSIDER_BUY_SMALL
    if _has(text, ("sell", "sold", "sale")):
        return EventCategory.INSIDER_SELL_LARGE if is_large else EventCategory.INSIDER_SELL_SMALL
    return None


def _classify_misc(text: str) -> EventCategory | None:  # noqa: PLR0911
    """Classify miscellaneous event categories."""
    if "buyback" in text or "share repurchase" in text:
        return EventCategory.BUYBACK_ANNOUNCED
    if "split" in text and "stock" in text:
        return EventCategory.SPLIT_ANNOUNCED
    _fda = "fda" in text or "approval" in text
    if _fda and _has(text, ("approve", "approved", "green light")):
        return EventCategory.FDA_APPROVAL
    if _fda and _has(text, ("reject", "denied", "failed")):
        return EventCategory.FDA_REJECTION
    _legal = _has(text, ("lawsuit", "sue", "sued", "litigation"))
    if _legal and ("filed" in text or "file" in text):
        return EventCategory.LAWSUIT_FILED
    if _legal and ("settled" in text or "settlement" in text):
        return EventCategory.LAWSUIT_SETTLED
    if "sec" in text and _has(text, ("investigation", "probe", "inquiry")):
        return EventCategory.SEC_INVESTIGATION
    return None


def _classify_analyst_exec_guidance_dividend(text: str) -> EventCategory | None:  # noqa: PLR0911
    """Classify analyst, executive, guidance, and dividend events."""
    if _has(text, ("analyst", "rating", "target")):
        if _has(text, ("upgrade", "raised", "boost", "increase")):
            return EventCategory.ANALYST_UPGRADE
        if _has(text, ("downgrade", "lowered", "cut", "reduce")):
            return EventCategory.ANALYST_DOWNGRADE
        if "initiate" in text or "coverage" in text:
            return EventCategory.ANALYST_INITIATE
    if _has(text, ("merger", "acquisition", "acquire", "takeover")):
        if _has(text, _MA_ANNOUNCE):
            return EventCategory.M_AND_A_ANNOUNCED
        if _has(text, _MA_COMPLETE):
            return EventCategory.M_AND_A_COMPLETED
    if "ceo" in text and _has(text, _EXEC_CHANGE):
        return EventCategory.EXEC_CHANGE_CEO
    if "cfo" in text and _has(text, _EXEC_CHANGE):
        return EventCategory.EXEC_CHANGE_CFO
    if _has(text, ("guidance", "outlook", "forecast")):
        if _has(text, ("raise", "increase", "boost", "improve")):
            return EventCategory.GUIDANCE_RAISED
        if _has(text, ("lower", "reduce", "cut", "worsen")):
            return EventCategory.GUIDANCE_LOWERED
    if "dividend" in text:
        if _has(text, ("increase", "raise", "boost")):
            return EventCategory.DIVIDEND_INCREASE
        if _has(text, ("cut", "reduce", "suspend")):
            return EventCategory.DIVIDEND_CUT
    return None
