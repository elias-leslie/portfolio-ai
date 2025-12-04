"""News intelligence building for watchlist service.

This module provides:
- News intelligence summary generation
- Article parsing and key event extraction
- Sentiment analysis aggregation
"""

from __future__ import annotations

import json
from typing import Any

from ...logging_config import get_logger
from ..models import KeyEvent, NewsArticleDict, NewsIntelligence
from ..watchlist_repository import WatchlistRepository
from .formatters import _format_time_ago, _get_event_icon

logger = get_logger(__name__)


def parse_news_article(
    row: tuple[Any, ...],
    key_events: list[KeyEvent],
) -> tuple[NewsArticleDict, float | None]:
    """Parse news article row into article dict and extract sentiment.

    Args:
        row: Database row tuple
        key_events: List to append key events to (modified in place)

    Returns:
        Tuple of (article_dict, sentiment_score)
    """
    (
        symbol,
        headline,
        url,
        summary_text,
        news_source_name,
        author,
        image_url,
        published_at,
        sentiment_score,
        sentiment_label,
        sentiment_confidence,
        _sentiment_model,
        raw_payload,
        _content_hash,
        _fetched_at,
        filing_type,
        is_material_event,
        plain_language_headline,
        _story_id,
        _is_primary_article,
        _coverage_count,
        impact_summary,
        actionable_insight,
    ) = row

    # Build article dict
    article = {
        "symbol": symbol,
        "headline": headline,
        "url": url,
        "summary": summary_text,
        "source": news_source_name,
        "author": author,
        "image_url": image_url,
        "published_at": published_at.isoformat() if published_at else None,
        "sentiment_score": float(sentiment_score) if sentiment_score else 0.0,
        "sentiment_label": sentiment_label or "neutral",
        "sentiment_confidence": (float(sentiment_confidence) if sentiment_confidence else 0.0),
        "filing_type": filing_type,
        "is_material_event": bool(is_material_event),
        "plain_language_headline": plain_language_headline or headline,
        "impact_summary": impact_summary,
        "actionable_insight": actionable_insight,
    }

    # Extract key events (material events only, max 3)
    if is_material_event and len(key_events) < 3:
        # Try to extract event category from raw_payload
        event_category = None
        if raw_payload:
            try:
                payload_dict = (
                    json.loads(raw_payload) if isinstance(raw_payload, str) else raw_payload
                )
                event_category = payload_dict.get("event_category")
            except Exception:
                pass

        key_events.append(
            KeyEvent(
                icon=_get_event_icon(event_category, True),
                text=plain_language_headline or headline,
                time_ago=_format_time_ago(published_at),
                is_material=True,
                event_category=event_category,
                published_at=published_at,
            )
        )

    return article, float(sentiment_score) if sentiment_score is not None else None  # type: ignore[return-value]


def generate_news_headline(
    key_events: list[KeyEvent],
    avg_sentiment: float,
    article_count: int,
) -> str:
    """Generate summary headline from news intelligence.

    Args:
        key_events: List of key events
        avg_sentiment: Average sentiment score
        article_count: Number of articles

    Returns:
        Generated headline string
    """
    if len(key_events) >= 2:
        # Multiple events - summarize
        event_types = [
            evt.text.split(" - ")[0] if " - " in evt.text else evt.text[:30]
            for evt in key_events[:2]
        ]
        return f"{event_types[0]} + {event_types[1]}"
    if len(key_events) == 1:
        return key_events[0].text
    if avg_sentiment > 0.3:
        return f"Positive news flow ({article_count} articles)"
    if avg_sentiment < -0.3:
        return f"Negative news flow ({article_count} articles)"
    return f"Mixed news ({article_count} articles in 24h)"


def build_news_intelligence(repo: WatchlistRepository, symbol: str) -> NewsIntelligence | None:
    """Build news intelligence summary for a symbol.

    Args:
        repo: Watchlist repository instance
        symbol: Ticker symbol

    Returns:
        NewsIntelligence object or None if no recent news
    """
    # Query news cache for recent articles
    rows = repo.get_recent_news(symbol, hours=24, limit=20)
    if not rows:
        return None

    # Parse articles and extract key events
    articles: list[NewsArticleDict] = []
    sentiment_scores: list[float] = []
    key_events: list[KeyEvent] = []

    for row in rows:
        article, sentiment = parse_news_article(row, key_events)
        articles.append(article)
        if sentiment is not None:
            sentiment_scores.append(sentiment)

    # Calculate average sentiment
    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores) if sentiment_scores else 0.0

    # Determine sentiment label
    if avg_sentiment > 0.15:
        sentiment_label = "Positive"
    elif avg_sentiment < -0.15:
        sentiment_label = "Negative"
    else:
        sentiment_label = "Neutral"

    # Generate headline summary
    headline = generate_news_headline(key_events, avg_sentiment, len(articles))

    return NewsIntelligence(
        headline=headline[:100],  # Limit headline length
        sentiment_score=round(avg_sentiment, 2),
        sentiment_label=sentiment_label,
        article_count_24h=len(articles),
        key_events=key_events,
        recent_articles=articles[:5],  # Top 5 most recent
    )


__all__ = [
    "build_news_intelligence",
    "generate_news_headline",
    "parse_news_article",
]
