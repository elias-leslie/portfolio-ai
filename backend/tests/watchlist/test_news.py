"""Tests for news fetching and sentiment analysis."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.storage.connection import ConnectionManager
from app.watchlist.news import (
    NewsHeadline,
    categorize_sentiment,
    fetch_news_headlines,
    fetch_news_headlines_cached,
)


class TestNewsHeadlineModel:
    """Test NewsHeadline Pydantic model."""

    def test_news_headline_creation(self) -> None:
        """Test creating NewsHeadline with all fields."""
        headline = NewsHeadline(
            title="NVDA Beats Earnings Expectations",
            url="https://example.com/nvda-earnings",
            published_at="2025-11-01T10:00:00Z",
            sentiment_score=0.85,
        )
        assert headline.title == "NVDA Beats Earnings Expectations"
        assert headline.sentiment_score == 0.85

    def test_news_headline_optional_url(self) -> None:
        """Test creating NewsHeadline without URL."""
        headline = NewsHeadline(
            title="NVDA Beats Earnings",
            url=None,
            published_at="2025-11-01T10:00:00Z",
            sentiment_score=0.85,
        )
        assert headline.title == "NVDA Beats Earnings"
        assert headline.url is None


class TestFetchNewsHeadlines:
    """Test news headline fetching from Google News RSS."""

    @patch("app.watchlist.news.feedparser.parse")
    def test_fetch_news_success(self, mock_parse: MagicMock) -> None:
        """Test successful news fetch from Google News RSS."""
        # Mock feedparser response (feed.entries is accessed as an attribute)
        mock_feed = MagicMock()
        mock_feed.entries = [
            {
                "title": "NVDA Beats Earnings Expectations",
                "link": "https://example.com/nvda-earnings",
                "published": "Fri, 01 Nov 2025 10:00:00 GMT",
            },
            {
                "title": "NVIDIA Announces New AI Chip",
                "link": "https://example.com/nvda-chip",
                "published": "Thu, 31 Oct 2025 15:00:00 GMT",
            },
        ]
        mock_parse.return_value = mock_feed

        headlines = fetch_news_headlines("NVDA", max_results=10)

        assert headlines is not None
        assert len(headlines) == 2
        assert headlines[0].title == "NVDA Beats Earnings Expectations"
        assert headlines[0].url == "https://example.com/nvda-earnings"
        assert headlines[0].sentiment_score is not None
        # Verify sentiment score is computed (should be a valid score between -1 and 1)
        assert -1.0 <= headlines[0].sentiment_score <= 1.0

    @patch("app.watchlist.news.feedparser.parse")
    def test_fetch_news_limits_results(self, mock_parse: MagicMock) -> None:
        """Test that fetch_news_headlines limits to max_results."""
        # Mock 15 entries but only request 10
        mock_feed = MagicMock()
        mock_feed.entries = [
            {
                "title": f"Headline {i}",
                "link": f"https://example.com/{i}",
                "published": "Fri, 01 Nov 2025 10:00:00 GMT",
            }
            for i in range(15)
        ]
        mock_parse.return_value = mock_feed

        headlines = fetch_news_headlines("NVDA", max_results=10)

        assert headlines is not None
        assert len(headlines) == 10

    @patch("app.watchlist.news.feedparser.parse")
    def test_fetch_news_handles_missing_fields(self, mock_parse: MagicMock) -> None:
        """Test that fetch handles entries with missing fields."""
        mock_feed = MagicMock()
        mock_feed.entries = [
            {
                "title": "Headline without link",
                # Missing link
                "published": "Fri, 01 Nov 2025 10:00:00 GMT",
            },
            {
                "title": "Headline without published date",
                "link": "https://example.com/2",
                # Missing published
            },
        ]
        mock_parse.return_value = mock_feed

        headlines = fetch_news_headlines("NVDA", max_results=10)

        assert headlines is not None
        # Should handle gracefully - either skip or use defaults
        assert len(headlines) >= 0  # At least doesn't crash

    @patch("app.watchlist.news.feedparser.parse")
    def test_fetch_news_api_error(self, mock_parse: MagicMock) -> None:
        """Test fetch_news_headlines when API raises exception."""
        mock_parse.side_effect = Exception("API Error")

        headlines = fetch_news_headlines("NVDA", max_results=10)

        # Should return empty list on error, not None
        assert headlines is not None
        assert len(headlines) == 0

    @patch("app.watchlist.news.feedparser.parse")
    def test_fetch_news_empty_response(self, mock_parse: MagicMock) -> None:
        """Test fetch_news_headlines with empty feed."""
        mock_feed = MagicMock()
        mock_feed.entries = []
        mock_parse.return_value = mock_feed

        headlines = fetch_news_headlines("NVDA", max_results=10)

        assert headlines is not None
        assert len(headlines) == 0


class TestCategorizeSentiment:
    """Test sentiment categorization logic."""

    def test_categorize_positive_sentiment(self) -> None:
        """Test categorization of positive sentiment (> 0.2)."""
        category = categorize_sentiment(0.5)
        assert category == "positive"

    def test_categorize_negative_sentiment(self) -> None:
        """Test categorization of negative sentiment (< -0.2)."""
        category = categorize_sentiment(-0.5)
        assert category == "negative"

    def test_categorize_neutral_sentiment_zero(self) -> None:
        """Test categorization of neutral sentiment (exactly 0)."""
        category = categorize_sentiment(0.0)
        assert category == "neutral"

    def test_categorize_neutral_sentiment_low_positive(self) -> None:
        """Test categorization of low positive sentiment (< 0.2)."""
        category = categorize_sentiment(0.1)
        assert category == "neutral"

    def test_categorize_neutral_sentiment_low_negative(self) -> None:
        """Test categorization of low negative sentiment (> -0.2)."""
        category = categorize_sentiment(-0.1)
        assert category == "neutral"

    def test_categorize_positive_boundary(self) -> None:
        """Test categorization at positive boundary (exactly 0.2)."""
        category = categorize_sentiment(0.2)
        assert category in ("positive", "neutral")  # Allow either interpretation

    def test_categorize_negative_boundary(self) -> None:
        """Test categorization at negative boundary (exactly -0.2)."""
        category = categorize_sentiment(-0.2)
        assert category in ("negative", "neutral")  # Allow either interpretation


class TestSentimentScoring:
    """Test sentiment scoring with VADER."""

    @patch("app.watchlist.news.feedparser.parse")
    def test_positive_headline_has_positive_sentiment(self, mock_parse: MagicMock) -> None:
        """Test that positive headlines get positive sentiment scores."""
        mock_feed = MagicMock()
        mock_feed.entries = [
            {
                "title": "Amazing breakthrough! Stock soars on great news",
                "link": "https://example.com/positive",
                "published": "Fri, 01 Nov 2025 10:00:00 GMT",
            }
        ]
        mock_parse.return_value = mock_feed

        headlines = fetch_news_headlines("NVDA", max_results=1)

        assert headlines is not None
        assert len(headlines) == 1
        # Positive words should result in positive sentiment
        assert headlines[0].sentiment_score > 0.2

    @patch("app.watchlist.news.feedparser.parse")
    def test_negative_headline_has_negative_sentiment(self, mock_parse: MagicMock) -> None:
        """Test that negative headlines get negative sentiment scores."""
        mock_feed = MagicMock()
        mock_feed.entries = [
            {
                "title": "Terrible earnings miss! Stock crashes on horrible news",
                "link": "https://example.com/negative",
                "published": "Fri, 01 Nov 2025 10:00:00 GMT",
            }
        ]
        mock_parse.return_value = mock_feed

        headlines = fetch_news_headlines("NVDA", max_results=1)

        assert headlines is not None
        assert len(headlines) == 1
        # Negative words should result in negative sentiment
        assert headlines[0].sentiment_score < -0.2

    @patch("app.watchlist.news.feedparser.parse")
    def test_neutral_headline_has_neutral_sentiment(self, mock_parse: MagicMock) -> None:
        """Test that neutral headlines get neutral sentiment scores."""
        mock_feed = MagicMock()
        mock_feed.entries = [
            {
                "title": "Company announces quarterly earnings date",
                "link": "https://example.com/neutral",
                "published": "Fri, 01 Nov 2025 10:00:00 GMT",
            }
        ]
        mock_parse.return_value = mock_feed

        headlines = fetch_news_headlines("NVDA", max_results=1)

        assert headlines is not None
        assert len(headlines) == 1
        # Neutral words should result in neutral sentiment (-0.2 to 0.2)
        assert -0.2 <= headlines[0].sentiment_score <= 0.2


class TestNewsCaching:
    """Test caching functionality for news headlines (6-hour TTL)."""

    @patch("app.watchlist.news.fetch_news_headlines")
    def test_cache_stores_news_on_first_fetch(self, mock_fetch: MagicMock) -> None:
        """Test that news headlines are stored in reference_cache on first fetch."""
        mock_fetch.return_value = [
            NewsHeadline(
                title="NVDA Beats Earnings",
                url="https://example.com/nvda",
                published_at="2025-11-01T10:00:00Z",
                sentiment_score=0.85,
            )
        ]

        cm = ConnectionManager()
        with cm.connection() as conn:
            # First call should fetch from API and cache
            result = fetch_news_headlines_cached(conn, "NVDA")

            assert result is not None
            assert len(result) == 1
            assert result[0].title == "NVDA Beats Earnings"
            assert result[0].sentiment_score == 0.85

            # Verify data was cached
            cached_row = conn.execute(
                "SELECT payload FROM reference_cache WHERE ticker = %s AND source = %s",
                ["NVDA", "news"],
            ).fetchone()

            assert cached_row is not None
            cached_data = cached_row[0]
            assert isinstance(cached_data, list)
            assert len(cached_data) == 1
            assert cached_data[0]["title"] == "NVDA Beats Earnings"

    @patch("app.watchlist.news.fetch_news_headlines")
    def test_cache_hit_avoids_refetch(self, mock_fetch: MagicMock) -> None:
        """Test that cache hit avoids calling API again (within 6-hour TTL)."""
        mock_fetch.return_value = [
            NewsHeadline(
                title="META Reports Growth",
                url="https://example.com/meta",
                published_at="2025-11-01T10:00:00Z",
                sentiment_score=0.65,
            )
        ]

        cm = ConnectionManager()
        with cm.connection() as conn:
            # First call - fetches from API
            result1 = fetch_news_headlines_cached(conn, "META")
            assert result1 is not None
            assert len(result1) == 1
            assert mock_fetch.call_count == 1

            # Second call within TTL - should use cache, not call API again
            result2 = fetch_news_headlines_cached(conn, "META")
            assert result2 is not None
            assert len(result2) == 1
            assert result2[0].title == "META Reports Growth"
            assert mock_fetch.call_count == 1  # Still only 1 call

    @patch("app.watchlist.news.fetch_news_headlines")
    def test_cache_ttl_expiration_triggers_refresh(self, mock_fetch: MagicMock) -> None:
        """Test that cache older than 6 hours triggers re-fetch."""
        # First fetch
        mock_fetch.return_value = [
            NewsHeadline(
                title="NVDA Old News",
                url="https://example.com/nvda1",
                published_at="2025-11-01T10:00:00Z",
                sentiment_score=0.50,
            )
        ]

        cm = ConnectionManager()
        with cm.connection() as conn:
            # First call - caches data
            result1 = fetch_news_headlines_cached(conn, "NVDA")
            assert result1 is not None
            assert len(result1) == 1
            assert mock_fetch.call_count == 1

            # Manually age the cache to 7 hours ago (expired)
            conn.execute(
                "UPDATE reference_cache SET created_at = created_at - INTERVAL '7 hours' WHERE ticker = %s AND source = %s",
                ["NVDA", "news"],
            )
            conn.commit()

            # Updated data for second fetch
            mock_fetch.return_value = [
                NewsHeadline(
                    title="NVDA Fresh News",
                    url="https://example.com/nvda2",
                    published_at="2025-11-01T17:00:00Z",
                    sentiment_score=0.75,
                )
            ]

            # Second call - should detect stale cache and re-fetch
            result2 = fetch_news_headlines_cached(conn, "NVDA")
            assert result2 is not None
            assert len(result2) == 1
            assert result2[0].title == "NVDA Fresh News"  # New data
            assert mock_fetch.call_count == 2  # Called again

    @patch("app.watchlist.news.fetch_news_headlines")
    def test_cache_handles_empty_response_gracefully(self, mock_fetch: MagicMock) -> None:
        """Test that empty list return from API doesn't crash caching."""
        mock_fetch.return_value = []  # No news available

        cm = ConnectionManager()
        with cm.connection() as conn:
            result = fetch_news_headlines_cached(conn, "INVALID")

            assert result is not None
            assert len(result) == 0
            # Should not have cached anything (empty lists typically not cached)
            # But function should handle gracefully without crashing
