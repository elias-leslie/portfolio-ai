"""Catalyst Impact Scoring Module.

Calculates time-decayed impact scores for news events based on
their category and duration. Used to enhance watchlist scoring
with event-driven signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from ..logging_config import get_logger
from ..rules.loader import get_rules
from ..rules.models import CatalystImpact
from .plain_language_news import EventCategory, classify_event_category

logger = get_logger(__name__)


@dataclass
class CatalystScore:
    """Calculated catalyst impact score with metadata."""

    score: float  # Time-decayed impact (-5 to +5)
    raw_impact: float  # Original impact before decay
    event_category: str
    days_since_event: int
    duration_days: int
    is_expired: bool
    expires_at: datetime | None


def get_catalyst_config(event_category: str) -> CatalystImpact:
    """Get catalyst impact configuration for an event category.

    Args:
        event_category: Event category string (e.g., 'earnings_beat', 'fda_approval')

    Returns:
        CatalystImpact with impact score and duration
    """
    rules = get_rules()
    # Normalize category name (EventCategory enum uses underscores)
    normalized = event_category.lower().replace("-", "_")
    return rules.catalyst_impacts.get(normalized, CatalystImpact(impact=0.0, duration_days=1))


def calculate_catalyst_impact(
    event_category: str | EventCategory,
    event_date: datetime,
    current_date: datetime | None = None,
) -> CatalystScore:
    """Calculate time-decayed catalyst impact score.

    Impact decays linearly over the duration period:
    - Day 0: 100% of impact
    - Day N (N = duration): 0% impact (expired)

    Args:
        event_category: Event type (string or EventCategory enum)
        event_date: When the event occurred
        current_date: Reference date for decay calculation (default: now)

    Returns:
        CatalystScore with calculated impact and metadata
    """
    if current_date is None:
        current_date = datetime.now(UTC)

    # Normalize to timezone-aware
    if event_date.tzinfo is None:
        event_date = event_date.replace(tzinfo=UTC)
    if current_date.tzinfo is None:
        current_date = current_date.replace(tzinfo=UTC)

    # Get category string
    if isinstance(event_category, EventCategory):
        category_str = event_category.value
    else:
        category_str = str(event_category)

    # Get config from rules
    config = get_catalyst_config(category_str)

    # Calculate days since event
    delta = current_date - event_date
    days_since = max(0, delta.days)

    # Check expiration
    is_expired = days_since >= config.duration_days

    # Calculate expires_at
    expires_at = event_date + timedelta(days=config.duration_days)

    if is_expired:
        return CatalystScore(
            score=0.0,
            raw_impact=config.impact,
            event_category=category_str,
            days_since_event=days_since,
            duration_days=config.duration_days,
            is_expired=True,
            expires_at=expires_at,
        )

    # Linear decay: impact * (1 - days_since / duration_days)
    decay_factor = 1.0 - (days_since / config.duration_days)
    decayed_score = config.impact * decay_factor

    return CatalystScore(
        score=round(decayed_score, 2),
        raw_impact=config.impact,
        event_category=category_str,
        days_since_event=days_since,
        duration_days=config.duration_days,
        is_expired=False,
        expires_at=expires_at,
    )


def calculate_news_catalyst_score(
    headline: str,
    summary: str | None,
    published_at: datetime,
    filing_type: str | None = None,
    current_date: datetime | None = None,
) -> CatalystScore:
    """Calculate catalyst score from news article.

    Classifies the news event and calculates time-decayed impact.

    Args:
        headline: News headline text
        summary: Optional article summary
        published_at: When the article was published
        filing_type: Optional SEC filing type (8-K, Form 4, etc.)
        current_date: Reference date for decay (default: now)

    Returns:
        CatalystScore with calculated impact
    """
    # Classify the event
    category = classify_event_category(headline, summary, filing_type)

    # Calculate impact
    return calculate_catalyst_impact(category, published_at, current_date)


def aggregate_catalyst_scores(
    scores: list[CatalystScore],
    max_positive: float = 5.0,
    max_negative: float = -5.0,
) -> float:
    """Aggregate multiple catalyst scores into a single score.

    Uses the strongest signal in each direction, capped at max values.

    Args:
        scores: List of CatalystScore objects
        max_positive: Maximum positive aggregate score
        max_negative: Minimum (most negative) aggregate score

    Returns:
        Aggregated catalyst score
    """
    if not scores:
        return 0.0

    # Separate positive and negative scores
    positive_scores = [s.score for s in scores if s.score > 0]
    negative_scores = [s.score for s in scores if s.score < 0]

    # Take max positive and most negative
    best_positive = max(positive_scores) if positive_scores else 0.0
    worst_negative = min(negative_scores) if negative_scores else 0.0

    # Combine (could be net positive, net negative, or cancelling)
    aggregate = best_positive + worst_negative

    # Clamp to bounds
    return max(max_negative, min(max_positive, aggregate))


def get_active_catalysts_for_ticker(
    ticker: str,
    news_articles: list[dict[str, str | datetime | float | None]],
    current_date: datetime | None = None,
) -> list[CatalystScore]:
    """Get all active (non-expired) catalysts for a ticker.

    Args:
        ticker: Stock symbol
        news_articles: List of news article dicts with:
            - headline: str
            - summary: str | None
            - published_at: datetime
            - filing_type: str | None (optional)
        current_date: Reference date (default: now)

    Returns:
        List of active CatalystScore objects, sorted by impact magnitude
    """
    active_catalysts: list[CatalystScore] = []

    for article in news_articles:
        headline = str(article.get("headline", ""))
        summary = article.get("summary")
        published_at = article.get("published_at")
        filing_type = article.get("filing_type")

        if not headline or not published_at:
            continue

        # Ensure published_at is a datetime
        event_datetime: datetime
        if isinstance(published_at, str):
            try:
                event_datetime = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except ValueError:
                continue
        elif isinstance(published_at, datetime):
            event_datetime = published_at
        else:
            continue  # Skip if not a valid type

        score = calculate_news_catalyst_score(
            headline=headline,
            summary=str(summary) if summary else None,
            published_at=event_datetime,
            filing_type=str(filing_type) if filing_type else None,
            current_date=current_date,
        )

        if not score.is_expired and abs(score.score) > 0.1:
            active_catalysts.append(score)

    # Sort by absolute impact (strongest signals first)
    active_catalysts.sort(key=lambda s: abs(s.score), reverse=True)

    return active_catalysts
