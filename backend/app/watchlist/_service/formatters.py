"""Data formatting and transformation utilities for watchlist service.

This module provides:
- Time formatting (relative time strings)
- Event icon mapping
- News payload normalization
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..refresh_builders import _extract_article_publisher, _extract_article_vendor


def _format_time_ago(dt: datetime | None) -> str:
    """Format datetime as 'X hours/days ago'."""
    if dt is None:
        return "unknown"

    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    delta = now - dt
    hours = delta.total_seconds() / 3600

    if hours < 1:
        minutes = int(delta.total_seconds() / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if hours < 24:
        hours_int = int(hours)
        return f"{hours_int} hour{'s' if hours_int != 1 else ''} ago"
    days = int(hours / 24)
    return f"{days} day{'s' if days != 1 else ''} ago"


def _get_event_icon(event_category: str | None, is_material: bool) -> str:
    """Get icon for event category."""
    if not event_category:
        return "📰"

    # Map event categories to icons
    icon_map = {
        "earnings": "📋",
        "insider_buy": "📈",
        "insider_sell": "📉",
        "analyst_upgrade": "📈",
        "analyst_downgrade": "📉",
        "m_and_a": "🤝",
        "exec_change": "👔",
        "fda_approval": "✅",
        "fda_rejection": "❌",
        "lawsuit": "⚖️",
        "guidance_raised": "📈",
        "guidance_lowered": "📉",
        "dividend": "💰",
        "sec_investigation": "⚠️",
    }

    # Match category prefix
    for prefix, icon in icon_map.items():
        if event_category.startswith(prefix):
            return icon

    return "⚠️" if is_material else "📰"


def _normalize_recent_news_payload(news_payload: dict[str, Any]) -> dict[str, Any]:
    """Ensure vendor + publisher metadata is surfaced for stored news payloads."""
    if not isinstance(news_payload, dict):
        return news_payload

    articles = news_payload.get("articles")
    if not isinstance(articles, list):
        return news_payload

    normalized_articles: list[dict[str, Any]] = []
    changed = False

    for article in articles:
        if not isinstance(article, dict):
            normalized_articles.append(article)
            continue

        normalized_article = dict(article)

        vendor = _extract_article_vendor(normalized_article)
        if vendor and vendor != normalized_article.get("vendor"):
            normalized_article["vendor"] = vendor
            changed = True

        publisher = _extract_article_publisher(normalized_article)
        if publisher and publisher != normalized_article.get("source"):
            normalized_article["source"] = publisher
            changed = True

        if normalized_article.setdefault(
            "publisher", normalized_article.get("source")
        ) != article.get("publisher"):
            changed = True

        normalized_articles.append(normalized_article)

    if not changed:
        return news_payload

    payload = dict(news_payload)
    payload["articles"] = normalized_articles
    return payload


__all__ = [
    "_format_time_ago",
    "_get_event_icon",
    "_normalize_recent_news_payload",
]
