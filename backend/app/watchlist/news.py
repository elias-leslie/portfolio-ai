"""News fetching and sentiment analysis for watchlist intelligence.

This module fetches recent news headlines from Google News RSS feeds and
performs sentiment analysis using VADER (Valence Aware Dictionary and sEntiment Reasoner).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

import feedparser  # type: ignore[import-untyped]
from pydantic import BaseModel
from vaderSentiment.vaderSentiment import (  # type: ignore[import-untyped]
    SentimentIntensityAnalyzer,
)

from app.storage.types import DatabaseConnection

if TYPE_CHECKING:
    pass


class NewsHeadline(BaseModel):
    """News headline with sentiment score."""

    title: str
    url: str | None = None
    published_at: str | None = None
    sentiment_score: float  # -1.0 to +1.0


def fetch_news_headlines(symbol: str, max_results: int = 10) -> list[NewsHeadline]:
    """Fetch recent news headlines from Google News RSS.

    Args:
        symbol: Stock ticker symbol
        max_results: Maximum number of headlines to return (default: 10)

    Returns:
        List of NewsHeadline objects with sentiment scores
        Returns empty list on error
    """
    try:
        # Construct Google News RSS URL
        url = f"https://news.google.com/rss/search?q={symbol}+stock&hl=en-US&gl=US&ceid=US:en"

        # Parse RSS feed
        feed = feedparser.parse(url)

        # Initialize VADER sentiment analyzer
        analyzer = SentimentIntensityAnalyzer()

        headlines: list[NewsHeadline] = []

        # Extract headlines up to max_results
        for entry in feed.entries[:max_results]:
            title = entry.get("title", "")
            if not title:
                continue  # Skip entries without titles

            # Compute sentiment score using VADER
            # compound score ranges from -1 (extremely negative) to +1 (extremely positive)
            sentiment_scores = analyzer.polarity_scores(title)
            sentiment_score = sentiment_scores["compound"]

            # Extract optional fields
            url_str = entry.get("link")
            published = entry.get("published")

            headline = NewsHeadline(
                title=title,
                url=url_str,
                published_at=published,
                sentiment_score=sentiment_score,
            )
            headlines.append(headline)

        return headlines

    except Exception:
        # Return empty list on any error (network failure, parsing error, etc.)
        return []


def categorize_sentiment(sentiment_score: float) -> str:
    """Categorize sentiment score as positive, negative, or neutral.

    Args:
        sentiment_score: Sentiment score from -1.0 to +1.0

    Returns:
        "positive", "negative", or "neutral"
    """
    if sentiment_score >= 0.2:
        return "positive"
    if sentiment_score <= -0.2:
        return "negative"
    return "neutral"


def fetch_news_headlines_cached(
    conn: DatabaseConnection, symbol: str, max_results: int = 10, ttl_hours: int = 6
) -> list[NewsHeadline]:
    """Fetch news headlines with caching support (default TTL: 6 hours).

    This function checks the reference_cache table first. If valid cached data
    exists (within TTL), it returns the cached data without calling external APIs.
    If cache is stale or missing, it fetches fresh data and caches it.

    News data changes frequently, so TTL is shorter than fundamentals (6 hours vs 24 hours).

    Args:
        conn: Database connection
        symbol: Stock ticker symbol
        max_results: Maximum number of headlines to return (default: 10)
        ttl_hours: Cache TTL in hours (default: 6 hours)

    Returns:
        List of NewsHeadline objects with sentiment scores
        Returns empty list on error

    Example:
        >>> from app.storage.connection import ConnectionManager
        >>> cm = ConnectionManager()
        >>> with cm.connection() as conn:
        ...     headlines = fetch_news_headlines_cached(conn, "NVDA")
        >>> # First call fetches from API and caches
        >>> # Second call within 6 hours uses cache
    """
    # Check cache first
    # For sub-day TTLs, we use timestamp comparison instead of date comparison
    cache_cutoff = datetime.now() - timedelta(hours=ttl_hours)

    cached_row = conn.execute(
        """
        SELECT payload
        FROM reference_cache
        WHERE symbol = %s
          AND source = %s
          AND created_at >= %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [symbol, "news", cache_cutoff],
    ).fetchone()

    # Cache hit - return cached data
    if cached_row is not None:
        payload = cached_row[0]
        # Payload is a list of dicts, convert to list of NewsHeadline
        if isinstance(payload, list):
            return [NewsHeadline(**item) for item in payload]
        return []

    # Cache miss or stale - fetch fresh data
    fresh_data = fetch_news_headlines(symbol, max_results)

    if not fresh_data:
        return []

    # Cache the fresh data
    # Convert list of NewsHeadline to list of dicts for JSON storage
    payload_data = [headline.model_dump() for headline in fresh_data]

    conn.execute(
        """
        INSERT INTO reference_cache (symbol, as_of_date, payload, source)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (ticker, as_of_date, source)
        DO UPDATE SET payload = EXCLUDED.payload, created_at = NOW()
        """,
        [
            symbol,
            date.today().isoformat(),
            json.dumps(payload_data),
            "news",
        ],
    )
    conn.commit()

    return fresh_data
