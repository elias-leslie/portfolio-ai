"""News intelligence aggregation for research insights.

Handles:
- News sentiment analysis (7-day and 30-day rolling averages)
- Material event detection (earnings, product launches, acquisitions, regulatory)
- News volume confidence scoring
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from app.storage import PortfolioStorage

# Material event keywords for headline classification
MATERIAL_EVENT_KEYWORDS: dict[str, list[str]] = {
    "earnings": ["earnings", "beat", "miss", "eps", "revenue"],
    "product_launch": ["product", "launch", "release", "announce"],
    "acquisition": ["acquisition", "merger", "acquire", "buyout"],
    "regulatory": ["fda", "approval", "regulatory", "sec"],
}

# News volume thresholds for confidence calculation
NEWS_CONFIDENCE_THRESHOLDS: dict[int, float] = {
    20: 1.0,
    10: 0.8,
    5: 0.6,
}
NEWS_CONFIDENCE_DEFAULT = 0.4


def extract_material_events(news_rows: list[dict[str, Any]]) -> list[str]:
    """Extract material events from headlines using keyword classification.

    Args:
        news_rows: List of news article dicts with 'headline' key

    Returns:
        List of unique event types found (e.g., ['earnings', 'acquisition'])
    """
    material_events = []
    for row in news_rows:
        headline = row.get("headline", "")
        if not headline:
            continue
        headline_lower = headline.lower()
        for event_type, keywords in MATERIAL_EVENT_KEYWORDS.items():
            if any(kw in headline_lower for kw in keywords):
                material_events.append(event_type)
                break  # One event type per headline
    return list(set(material_events))


def calculate_news_confidence(news_volume: int) -> float:
    """Calculate confidence score based on article count.

    Args:
        news_volume: Number of news articles

    Returns:
        Confidence score between 0.0 and 1.0
    """
    for threshold, confidence in sorted(NEWS_CONFIDENCE_THRESHOLDS.items(), reverse=True):
        if news_volume >= threshold:
            return confidence
    return NEWS_CONFIDENCE_DEFAULT


def calculate_sentiment_metrics(news_rows: list[dict[str, Any]], end_date: date) -> dict[str, Any]:
    """Calculate sentiment metrics from news data.

    Args:
        news_rows: List of news article dicts
        end_date: End of lookback period

    Returns:
        Dict with sentiment_score, sentiment_7d_avg, sentiment_30d_avg, sentiment_trend
    """
    all_scores = [row["sentiment_score"] for row in news_rows if row["sentiment_score"] is not None]
    # Convert end_date to datetime for comparison with published_at (which is datetime)
    end_datetime = datetime.combine(end_date, datetime.min.time())
    recent_7d = [
        row["sentiment_score"]
        for row in news_rows
        if row["sentiment_score"] is not None
        and row["published_at"] is not None
        and (
            row["published_at"].replace(tzinfo=None)
            if hasattr(row["published_at"], "replace")
            else row["published_at"]
        )
        >= (end_datetime - timedelta(days=7))
    ]

    sentiment_score = all_scores[0] if all_scores else 0.0  # Most recent
    sentiment_7d_avg = sum(recent_7d) / len(recent_7d) if recent_7d else 0.0
    sentiment_30d_avg = sum(all_scores) / len(all_scores) if all_scores else 0.0

    # Determine sentiment trend
    if sentiment_7d_avg > sentiment_30d_avg + 0.1:
        sentiment_trend = "improving"
    elif sentiment_7d_avg < sentiment_30d_avg - 0.1:
        sentiment_trend = "deteriorating"
    else:
        sentiment_trend = "stable"

    return {
        "sentiment_score": sentiment_score,
        "sentiment_7d_avg": sentiment_7d_avg,
        "sentiment_30d_avg": sentiment_30d_avg,
        "sentiment_trend": sentiment_trend,
    }


def aggregate_news_intelligence(
    storage: PortfolioStorage, symbol: str, start_date: date, end_date: date
) -> dict[str, Any]:
    """Aggregate news sentiment and events.

    Args:
        storage: Portfolio storage instance
        symbol: Stock symbol
        start_date: Start of lookback period
        end_date: End of lookback period (today)

    Returns:
        Dict with news intelligence fields
    """
    # Fetch news data
    df = storage.get_news_data(symbol, str(start_date), str(end_date))
    news_rows = df.to_dicts() if not df.is_empty() else []

    if not news_rows:
        # No news data available
        return {
            "sentiment_trend": "stable",
            "sentiment_score": 0.0,
            "sentiment_7d_avg": 0.0,
            "sentiment_30d_avg": 0.0,
            "material_events": [],
            "news_volume": 0,
            "confidence": 0.0,
        }

    # Calculate metrics
    sentiment_data = calculate_sentiment_metrics(news_rows, end_date)
    material_events = extract_material_events(news_rows)
    news_volume = len(news_rows)
    confidence = calculate_news_confidence(news_volume)

    return {
        "sentiment_trend": sentiment_data["sentiment_trend"],
        "sentiment_score": sentiment_data["sentiment_score"],
        "sentiment_7d_avg": sentiment_data["sentiment_7d_avg"],
        "sentiment_30d_avg": sentiment_data["sentiment_30d_avg"],
        "material_events": material_events,
        "news_volume": news_volume,
        "confidence": confidence,
    }
