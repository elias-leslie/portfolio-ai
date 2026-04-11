"""Structured decision-value assessment for news articles."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from .news_constants import MARKET_SYMBOL
from .plain_language_news import EventCategory, classify_event_category

SOURCE_SUFFIX_PATTERN = re.compile(
    r"\s[-|:]\s(?:yahoo finance|marketwatch|the motley fool|motley fool|"
    r"seeking alpha|reuters|bloomberg|investor'?s business daily|benzinga|"
    r"24/7 wall st\.)\s*$",
    re.IGNORECASE,
)

PRIMARY_SOURCES = frozenset(
    {
        "Associated Press",
        "Barron's",
        "Bloomberg",
        "CNBC",
        "Financial Times",
        "Investor's Business Daily",
        "MarketWatch",
        "Reuters",
        "The Wall Street Journal",
        "Wall Street Journal",
        "Yahoo Finance",
    }
)
COMMENTARY_SOURCES = frozenset(
    {
        "24/7 Wall St.",
        "Seeking Alpha",
        "The Motley Fool",
    }
)

GENERIC_ACTIONABLE_INSIGHTS = frozenset(
    {
        "news reported - read the details before acting",
        "positive sentiment - worth investigating",
        "negative sentiment - proceed with caution",
    }
)
GENERIC_IMPACT_SUMMARIES = frozenset(
    {
        "news reported - assess impact based on your strategy",
        "very positive news - may create short-term momentum",
        "mildly positive - modest upside possible",
        "very negative news - may trigger selling pressure",
        "mildly negative - modest downside risk",
    }
)
NON_FINANCIAL_PATTERNS = (
    r"\bdo i say yes\b",
    r"\bwhat should i do\b",
    r"\bmy (son|daughter|husband|wife|partner)\b",
    r"\bfamily money\b",
    r"\bpersonal-finance\b",
    r"\bin-state tuition\b",
    r"\bundocumented students\b",
    r"\bretirement income\b",
    r"\btravel(?:ing)?\b",
)
COMMENTARY_PATTERNS = (
    r"\bstill holds true\b",
    r"\bwhat could happen next\b",
    r"\bhere'?s why it matters\b",
    r"\bwhat if\b",
    r"\ball along\b",
    r"\bmissing the point\b",
    r"\bmistake you can make\b",
)
MARKET_CONTEXT_TOPICS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "Rates",
        (
            r"\bfed\b",
            r"\bpowell\b",
            r"\brates?\b",
            r"\btreasur(?:y|ies)\b",
            r"\byields?\b",
            r"\bcentral bank\b",
            r"\becb\b",
            r"\bbank of japan\b",
            r"\bboj\b",
        ),
    ),
    (
        "Inflation",
        (
            r"\binflation\b",
            r"\bcpi\b",
            r"\bppi\b",
            r"\bpce\b",
        ),
    ),
    (
        "Growth",
        (
            r"\bjobs?\b",
            r"\bpayrolls?\b",
            r"\bunemployment\b",
            r"\bgdp\b",
            r"\brecession\b",
            r"\beconom(?:y|ic)\b",
            r"\bconsumer spending\b",
            r"\bretail sales\b",
            r"\bhousing\b",
        ),
    ),
    (
        "Risk",
        (
            r"\bvix\b",
            r"\bshort-covering\b",
            r"\brisk[- ]on\b",
            r"\brisk[- ]off\b",
            r"\bshaky footing\b",
            r"\bmarket breadth\b",
            r"\bstock market\b",
            r"\bwall street\b",
            r"\bs&p(?:\s+500)?\b",
            r"\bnasdaq\b",
            r"\bdow\b",
            r"\brussell\b",
        ),
    ),
    (
        "Sector Leadership",
        (
            r"\bsoftware stocks?\b",
            r"\bsemiconductors?\b",
            r"\bbanks?\b",
            r"\benergy stocks?\b",
            r"\bsector\b",
            r"\bbuy areas\b",
            r"\bchart of the day\b",
        ),
    ),
    (
        "Geopolitics",
        (
            r"\biran\b",
            r"\boil\b",
            r"\bcrude\b",
            r"\bopec\b",
            r"\btariffs?\b",
            r"\btrade war\b",
            r"\bgeopolit(?:ic|ical)\b",
            r"\bhormuz\b",
        ),
    ),
)
HIGH_IMPACT_EVENTS = frozenset(
    {
        EventCategory.EARNINGS_BEAT.value,
        EventCategory.EARNINGS_MISS.value,
        EventCategory.GUIDANCE_RAISED.value,
        EventCategory.GUIDANCE_LOWERED.value,
        EventCategory.ANALYST_UPGRADE.value,
        EventCategory.ANALYST_DOWNGRADE.value,
        EventCategory.M_AND_A_ANNOUNCED.value,
        EventCategory.M_AND_A_COMPLETED.value,
        EventCategory.SEC_INVESTIGATION.value,
        EventCategory.FDA_APPROVAL.value,
        EventCategory.FDA_REJECTION.value,
    }
)
MEDIUM_IMPACT_EVENTS = frozenset(
    {
        EventCategory.EARNINGS_MIXED.value,
        EventCategory.ANALYST_INITIATE.value,
        EventCategory.BUYBACK_ANNOUNCED.value,
        EventCategory.DIVIDEND_INCREASE.value,
        EventCategory.DIVIDEND_CUT.value,
        EventCategory.EXEC_CHANGE_CEO.value,
        EventCategory.EXEC_CHANGE_CFO.value,
        EventCategory.PARTNERSHIP.value,
        EventCategory.PRODUCT_LAUNCH.value,
        EventCategory.REGULATORY_WIN.value,
        EventCategory.REGULATORY_LOSS.value,
        EventCategory.LAWSUIT_FILED.value,
        EventCategory.LAWSUIT_SETTLED.value,
    }
)


@dataclass(frozen=True)
class NewsDecisionAssessment:
    """Structured assessment for ranking one article."""

    canonical_headline: str
    event_category: str | None
    market_context_topic: str | None
    source_signal_tier: str
    decision_value_score: float
    decision_value_label: str
    decision_value_reason: str


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = (
        re.sub(r"<[^>]*>", " ", html.unescape(value))
        .replace("&nbsp;", " ")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\xa0", " ")
        .replace("\u200b", " ")
        .replace("\ufeff", " ")
        .replace("\u2026", "...")
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("\t", " ")
        .strip()
    )
    return re.sub(r"\s+", " ", cleaned).strip()


def canonical_headline(headline: str) -> str:
    """Return a clean, source-agnostic display headline."""
    return SOURCE_SUFFIX_PATTERN.sub("", _clean_text(headline)).strip()


def _normalized_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", _clean_text(value).lower()).strip()


def source_signal_tier(source: str | None) -> str:
    """Classify source quality for decision support."""
    clean_source = _clean_text(source)
    if clean_source in PRIMARY_SOURCES:
        return "primary"
    if clean_source in COMMENTARY_SOURCES:
        return "commentary"
    if not clean_source:
        return "unknown"
    return "secondary"


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def market_context_topic(headline: str, summary: str | None = None) -> str | None:
    """Return the best-fit market context topic when one exists."""
    text = " ".join(part for part in (_clean_text(headline), _clean_text(summary)) if part).lower()
    if not text:
        return None
    for label, patterns in MARKET_CONTEXT_TOPICS:
        if _matches_any(text, patterns):
            return label
    return None


def _generic_copy_penalty(actionable_insight: str | None, impact_summary: str | None) -> bool:
    actionable = _normalized_text(actionable_insight)
    impact = _normalized_text(impact_summary)
    return (
        (not actionable or actionable in GENERIC_ACTIONABLE_INSIGHTS)
        and (not impact or impact in GENERIC_IMPACT_SUMMARIES)
    )


def assess_news_article(article: object) -> NewsDecisionAssessment:
    """Assess one article for decision usefulness."""
    headline = _clean_text(getattr(article, "headline", ""))
    summary = _clean_text(getattr(article, "summary", None))
    source = _clean_text(getattr(article, "source", None))
    symbol = getattr(article, "symbol", "") or ""
    actionable_insight = _clean_text(getattr(article, "actionable_insight", None))
    impact_summary = _clean_text(getattr(article, "impact_summary", None))
    quality_prediction = getattr(article, "quality_prediction", None)
    quality_confidence = float(getattr(article, "quality_confidence", 0.0) or 0.0)
    is_material_event = bool(getattr(article, "is_material_event", False))
    story_id = getattr(article, "story_id", None)
    is_primary_article = bool(getattr(article, "is_primary_article", False))
    coverage_count = int(getattr(article, "coverage_count", 1) or 1)
    filing_type = getattr(article, "filing_type", None)

    clean_headline = canonical_headline(headline)
    text = " ".join(part for part in (clean_headline, summary) if part).lower()
    event_category = classify_event_category(clean_headline, summary, filing_type).value
    topic = market_context_topic(clean_headline, summary) if symbol == MARKET_SYMBOL else None
    source_tier = source_signal_tier(source)

    score = 0.35

    if quality_prediction is True:
        score += 0.14 + min(quality_confidence, 1.0) * 0.12
    elif quality_prediction is False:
        score -= 0.1 + min(quality_confidence, 1.0) * 0.12

    if source_tier == "primary":
        score += 0.12
    elif source_tier == "secondary":
        score += 0.03
    elif source_tier == "commentary":
        score -= 0.16
    else:
        score -= 0.05

    if event_category in HIGH_IMPACT_EVENTS:
        score += 0.24
    elif event_category in MEDIUM_IMPACT_EVENTS:
        score += 0.12
    elif event_category == EventCategory.UNKNOWN.value:
        score -= 0.06

    if is_material_event:
        score += 0.14

    if topic:
        score += 0.12
    elif symbol == MARKET_SYMBOL:
        score -= 0.18

    if summary and len(summary) >= 90:
        score += 0.05
    else:
        score -= 0.04

    if story_id and coverage_count > 1:
        score += 0.04 if is_primary_article else -0.16

    if _generic_copy_penalty(actionable_insight, impact_summary):
        score -= 0.08

    if _matches_any(text, NON_FINANCIAL_PATTERNS):
        score -= 0.55
    if _matches_any(text, COMMENTARY_PATTERNS):
        score -= 0.18
    if source_tier == "commentary" and symbol == MARKET_SYMBOL:
        score -= 0.08

    score = max(0.0, min(score, 1.0))

    if _matches_any(text, NON_FINANCIAL_PATTERNS):
        reason = "Not a portfolio decision signal."
    elif story_id and coverage_count > 1 and not is_primary_article:
        reason = "Syndicated follow-up to an existing story."
    elif symbol == MARKET_SYMBOL and topic:
        reason = f"{topic} setup that can affect multiple holdings at once."
    elif event_category in HIGH_IMPACT_EVENTS:
        reason = "High-impact company event with direct fundamental implications."
    elif event_category in MEDIUM_IMPACT_EVENTS:
        reason = "Meaningful company event worth reviewing in context."
    elif source_tier == "commentary":
        reason = "Commentary-heavy source with weaker decision value."
    elif quality_prediction is False:
        reason = "Low-confidence article with limited decision value."
    else:
        reason = "Potentially relevant, but not strong enough to drive action alone."

    if score >= 0.75:
        label = "high"
    elif score >= 0.55:
        label = "medium"
    else:
        label = "low"

    return NewsDecisionAssessment(
        canonical_headline=clean_headline,
        event_category=None if event_category == EventCategory.UNKNOWN.value else event_category,
        market_context_topic=topic,
        source_signal_tier=source_tier,
        decision_value_score=round(score, 4),
        decision_value_label=label,
        decision_value_reason=reason,
    )
