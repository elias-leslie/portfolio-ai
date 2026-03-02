"""Consensus computation for Multi-LLM Strategy Reviewer.

Handles sentiment analysis and disagreement detection between providers.
"""

from __future__ import annotations

from .multi_reviewer_models import DisagreementSeverity, ProviderReview

# Keywords indicating bullish sentiment
BULLISH_KEYWORDS: list[str] = [
    "upside",
    "positive",
    "strength",
    "momentum",
    "support",
    "opportunity",
    "favorable",
    "bullish",
]

# Keywords indicating bearish sentiment
BEARISH_KEYWORDS: list[str] = [
    "downside",
    "negative",
    "weakness",
    "resistance",
    "risk",
    "concern",
    "unfavorable",
    "bearish",
    "caution",
    "warning",
]

# Keywords indicating concerns in a review
CONCERN_KEYWORDS: list[str] = [
    "risk",
    "concern",
    "caution",
    "unusual",
    "unexpected",
    "note that",
    "however",
    "but",
    "warning",
]


def analyze_sentiment(review_text: str) -> float:
    """Analyze sentiment of review text.

    Args:
        review_text: LLM review text

    Returns:
        Sentiment score from -1.0 (bearish) to +1.0 (bullish)
    """
    text_lower = review_text.lower()
    bullish_count = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
    bearish_count = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)
    total = bullish_count + bearish_count
    if total == 0:
        return 0.0  # Neutral
    return (bullish_count - bearish_count) / total


def detect_rules_disagreement(review_text: str, rationale: str) -> bool:
    """Check if LLM review flags concerns not in rules rationale.

    Args:
        review_text: LLM review
        rationale: Rules engine rationale

    Returns:
        True if LLM flags NEW concerns
    """
    review_lower = review_text.lower()
    rationale_lower = rationale.lower()
    has_concerns = any(kw in review_lower for kw in CONCERN_KEYWORDS)
    rules_didnt_flag = not any(kw in rationale_lower for kw in CONCERN_KEYWORDS)
    return has_concerns and rules_didnt_flag


def compute_consensus(
    gemini: ProviderReview, claude: ProviderReview
) -> tuple[float, DisagreementSeverity, bool]:
    """Compute consensus between two provider reviews.

    Args:
        gemini: Gemini review result
        claude: Claude review result

    Returns:
        (agreement_score, disagreement_severity, provider_disagreement)
    """
    if gemini.error or claude.error:
        if gemini.error and not claude.error:
            return 1.0, DisagreementSeverity.NONE, False
        if claude.error and not gemini.error:
            return 1.0, DisagreementSeverity.NONE, False
        # Both failed
        return 0.0, DisagreementSeverity.NONE, False

    gemini_sentiment = analyze_sentiment(gemini.review_text)
    claude_sentiment = analyze_sentiment(claude.review_text)
    sentiment_diff = abs(gemini_sentiment - claude_sentiment)
    agreement_score = 1.0 - (sentiment_diff / 2.0)

    if sentiment_diff < 0.3:
        severity = DisagreementSeverity.NONE
        provider_disagreement = False
    elif sentiment_diff < 0.7:
        severity = DisagreementSeverity.MINOR
        provider_disagreement = True
    else:
        severity = DisagreementSeverity.MAJOR
        provider_disagreement = True

    return agreement_score, severity, provider_disagreement


def generate_consensus_summary(
    gemini: ProviderReview,
    claude: ProviderReview,
    severity: DisagreementSeverity,
    provider_disagreement: bool,
) -> str:
    """Generate human-readable consensus summary.

    Args:
        gemini: Gemini review
        claude: Claude review
        severity: Disagreement severity
        provider_disagreement: Whether providers disagree

    Returns:
        Summary string for display
    """
    if gemini.error and claude.error:
        return "Both reviewers unavailable"
    if gemini.error:
        return f"Only Claude review available: {claude.review_text[:100]}..."
    if claude.error:
        return f"Only Gemini review available: {gemini.review_text[:100]}..."
    if not provider_disagreement:
        return "Both reviewers agree on the assessment"
    if severity == DisagreementSeverity.MINOR:
        return "Reviewers have minor differences in emphasis but align on direction"
    return "ALERT: Reviewers significantly disagree - manual review recommended"
