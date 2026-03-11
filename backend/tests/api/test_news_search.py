"""Tests for the news search endpoint contract."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.news import router
from app.services.news_models import NewsArticle, NewsBundle, NewsSummary, SentimentScore


def _build_bundle(symbol: str, with_article: bool = True) -> NewsBundle:
    articles = []
    if with_article:
        articles = [
            NewsArticle(
                symbol=symbol,
                headline=f"{symbol} headline",
                url=f"https://example.com/{symbol.lower()}",
                source="Example News",
                published_at=datetime(2026, 3, 7, 13, 0, tzinfo=UTC),
                fetched_at=datetime(2026, 3, 7, 13, 5, tzinfo=UTC),
                sentiment=SentimentScore(
                    score=0.4,
                    label="positive",
                    confidence=0.8,
                    model="test",
                    probabilities={"positive": 0.8, "neutral": 0.15, "negative": 0.05},
                ),
                content_hash=f"{symbol}-hash",
            )
        ]

    return NewsBundle(
        symbol=symbol,
        summary=NewsSummary(
            symbol=symbol,
            score=0.4 if with_article else None,
            score_change=None,
            positive_count=1 if with_article else 0,
            neutral_count=0,
            negative_count=0,
            article_count=len(articles),
            latest_published_at=articles[0].published_at if articles else None,
        ),
        articles=articles,
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    captured_limits: list[int] = []

    def fake_get_custom_news(query: str, *, max_articles: int = 10) -> NewsBundle:
        captured_limits.append(max_articles)
        if query == "XYZNOTASYMBOL123":
            return _build_bundle(query, with_article=False)
        return _build_bundle(query)

    class FakeNewsService:
        def refresh_max_articles_from_preferences(self) -> int:
            return 10

        def get_custom_news(self, query: str, *, max_articles: int = 10) -> NewsBundle:
            return fake_get_custom_news(query, max_articles=max_articles)

    def build_news_service() -> FakeNewsService:
        return FakeNewsService()

    monkeypatch.setattr("app.api.news._news_service", build_news_service)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    client.captured_limits = captured_limits  # type: ignore[attr-defined]
    return client


class TestNewsSearchEndpoint:
    """Tests for GET /api/news/search endpoint."""

    def test_news_search_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/news/search?query=AAPL")
        assert response.status_code == 200

    def test_news_search_returns_required_fields(self, client: TestClient) -> None:
        response = client.get("/api/news/search?query=AAPL")
        data = response.json()

        assert "articles" in data
        assert "symbol" in data

    def test_news_search_articles_is_list(self, client: TestClient) -> None:
        response = client.get("/api/news/search?query=AAPL")
        data = response.json()

        assert isinstance(data["articles"], list)

    def test_news_search_article_has_required_fields(self, client: TestClient) -> None:
        response = client.get("/api/news/search?query=AAPL")
        article = response.json()["articles"][0]

        assert "headline" in article
        assert "published_at" in article
        assert "source" in article
        assert "url" in article

    def test_news_search_symbol_matches_query(self, client: TestClient) -> None:
        response = client.get("/api/news/search?query=MSFT")
        data = response.json()

        assert data["symbol"] == "MSFT"

    def test_news_search_accepts_max_results_parameter(self, client: TestClient) -> None:
        response = client.get("/api/news/search?query=AAPL&max_results=5")
        assert response.status_code == 200
        assert "articles" in response.json()
        assert client.captured_limits[-1] == 5  # type: ignore[attr-defined]

    def test_news_search_unknown_symbol_returns_200(self, client: TestClient) -> None:
        response = client.get("/api/news/search?query=XYZNOTASYMBOL123")

        assert response.status_code == 200
        assert "articles" in response.json()

    def test_news_search_has_sentiment(self, client: TestClient) -> None:
        response = client.get("/api/news/search?query=AAPL")
        article = response.json()["articles"][0]

        assert "sentiment" in article
