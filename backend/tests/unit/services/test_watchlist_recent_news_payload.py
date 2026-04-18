"""Unit tests for recent watchlist news payload enrichment."""

from __future__ import annotations

from datetime import UTC, datetime

from app.services.news_models import NewsArticle, NewsBundle, NewsSummary, SentimentScore
from app.watchlist.refresh_builders import build_recent_news_payload


def test_build_recent_news_payload_includes_decision_support_fields() -> None:
    article = NewsArticle(
        symbol="TSLA",
        headline="Tesla rolls out robotaxis in Dallas and Houston",
        summary="Tesla said it is rolling out robotaxis in Dallas and Houston.",
        source="Reuters",
        url="https://example.com/tesla-robotaxi",
        fetched_at=datetime(2026, 4, 18, 20, 0, tzinfo=UTC),
        published_at=datetime(2026, 4, 18, 19, 0, tzinfo=UTC),
        sentiment=SentimentScore(
            score=0.2,
            label="positive",
            confidence=0.91,
            model="finbert",
            probabilities={"positive": 0.91},
        ),
        content_hash="tsla-robotaxi",
        raw={"vendor_payload": {"related": "TSLA"}},
        vendor="finnhub",
    )
    bundle = NewsBundle(
        symbol="TSLA",
        summary=NewsSummary(
            symbol="TSLA",
            score=0.2,
            score_change=None,
            positive_count=1,
            negative_count=0,
            neutral_count=0,
            article_count=1,
            latest_published_at=article.published_at,
            model_breakdown={"finbert": 1},
        ),
        articles=[article],
    )

    payload = build_recent_news_payload(bundle)

    saved = payload["articles"][0]
    assert saved["decision_value_score"] is not None
    assert saved["decision_value_reason"]
    assert saved["canonical_headline"] == "Tesla rolls out robotaxis in Dallas and Houston"
