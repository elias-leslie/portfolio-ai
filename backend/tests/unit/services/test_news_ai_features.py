from __future__ import annotations

from datetime import UTC, datetime

from app.services.news_ai_features import _build_clusterer_articles
from app.services.news_models import NewsArticle, SentimentScore


def test_build_clusterer_articles_prefers_publication_source_over_vendor() -> None:
    article = NewsArticle(
        symbol="MARKET",
        headline="Powell says the Fed can wait longer before cutting rates",
        summary="Rates remain in focus as inflation stays elevated.",
        source="Reuters",
        fetched_at=datetime(2026, 4, 11, 14, 0, tzinfo=UTC),
        published_at=datetime(2026, 4, 11, 13, 55, tzinfo=UTC),
        sentiment=SentimentScore(
            score=0.1,
            label="neutral",
            confidence=0.7,
            model="finbert",
            probabilities={"positive": 0.2, "neutral": 0.6, "negative": 0.2},
        ),
        content_hash="hash-1",
        vendor="finnhub",
    )

    cluster_articles = _build_clusterer_articles([article])

    assert len(cluster_articles) == 1
    assert cluster_articles[0].vendor == "Reuters"
