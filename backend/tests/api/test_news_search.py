"""Tests for news search endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestNewsSearchEndpoint:
    """Tests for GET /api/news/search endpoint."""

    def test_news_search_returns_200(self) -> None:
        """Test news search endpoint returns 200 OK."""
        response = client.get("/api/news/search?query=AAPL")
        assert response.status_code == 200

    def test_news_search_returns_required_fields(self) -> None:
        """Test news search response contains required fields."""
        response = client.get("/api/news/search?query=AAPL")
        data = response.json()

        assert "articles" in data
        assert "symbol" in data

    def test_news_search_articles_is_list(self) -> None:
        """Test articles field is a list."""
        response = client.get("/api/news/search?query=AAPL")
        data = response.json()

        assert isinstance(data["articles"], list)

    def test_news_search_article_has_required_fields(self) -> None:
        """Test each article has required fields."""
        response = client.get("/api/news/search?query=AAPL")
        data = response.json()

        if len(data["articles"]) > 0:
            article = data["articles"][0]
            assert "headline" in article
            assert "published_at" in article
            assert "source" in article
            assert "url" in article

    def test_news_search_symbol_matches_query(self) -> None:
        """Test symbol in response matches query."""
        response = client.get("/api/news/search?query=MSFT")
        data = response.json()

        assert data["symbol"] == "MSFT"

    def test_news_search_accepts_limit_parameter(self) -> None:
        """Test news search accepts limit parameter."""
        # API accepts limit parameter even if it doesn't strictly enforce it
        response = client.get("/api/news/search?query=AAPL&limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data

    def test_news_search_unknown_symbol_returns_200(self) -> None:
        """Test news search returns 200 for unknown symbol."""
        response = client.get("/api/news/search?query=XYZNOTASYMBOL123")

        # API returns 200 with results (may return market news as fallback)
        assert response.status_code == 200
        data = response.json()
        assert "articles" in data

    def test_news_search_has_sentiment(self) -> None:
        """Test articles include sentiment field."""
        response = client.get("/api/news/search?query=AAPL")
        data = response.json()

        if len(data["articles"]) > 0:
            article = data["articles"][0]
            assert "sentiment" in article
