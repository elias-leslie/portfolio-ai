"""Unit tests for news story clustering service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.story_clusterer import (
    SOURCE_PRIORITY,
    NewsArticle,
    Story,
    StoryClusterer,
)


@pytest.fixture
def sample_articles() -> list[NewsArticle]:
    """Create sample articles for testing."""
    base_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
    return [
        NewsArticle(
            id="art-1",
            symbol="NVDA",
            headline="NVIDIA beats Q3 earnings expectations",
            summary="NVIDIA reported strong Q3 results, exceeding analyst estimates.",
            vendor="reuters",
            published_at=base_time,
            sentiment_score=0.8,
            is_material_event=True,
        ),
        NewsArticle(
            id="art-2",
            symbol="NVDA",
            headline="Nvidia crushes quarterly earnings with AI growth",
            summary="Nvidia's AI business drives record revenue in latest quarter.",
            vendor="yfinance",
            published_at=base_time + timedelta(hours=1),
            sentiment_score=0.9,
            is_material_event=False,
        ),
        NewsArticle(
            id="art-3",
            symbol="AAPL",
            headline="Apple announces new iPhone 16 lineup",
            summary="Apple unveils iPhone 16 with new camera features.",
            vendor="wsj",
            published_at=base_time + timedelta(hours=2),
            sentiment_score=0.6,
            is_material_event=False,
        ),
    ]


@pytest.fixture
def clusterer() -> StoryClusterer:
    """Create StoryClusterer instance."""
    return StoryClusterer()


class TestNewsArticleDataclass:
    """Tests for NewsArticle dataclass."""

    def test_article_creation(self) -> None:
        """Test creating a NewsArticle with all fields."""
        article = NewsArticle(
            id="test-1",
            symbol="AAPL",
            headline="Test headline",
            summary="Test summary",
            vendor="reuters",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
            sentiment_score=0.5,
            is_material_event=True,
            filing_type="8-K",
        )
        assert article.id == "test-1"
        assert article.symbol == "AAPL"
        assert article.sentiment_score == 0.5
        assert article.is_material_event is True
        assert article.filing_type == "8-K"

    def test_article_optional_fields_defaults(self) -> None:
        """Test NewsArticle default values for optional fields."""
        article = NewsArticle(
            id="test-2",
            symbol="AAPL",
            headline="Test",
            summary=None,
            vendor="yfinance",
            published_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
        assert article.sentiment_score is None
        assert article.is_material_event is False
        assert article.filing_type is None


class TestStoryDataclass:
    """Tests for Story dataclass."""

    def test_story_creation(self, sample_articles: list[NewsArticle]) -> None:
        """Test creating a Story with all fields."""
        story = Story(
            story_id="story-1",
            primary_article=sample_articles[0],
            related_articles=[sample_articles[1]],
            coverage_count=2,
            avg_sentiment=0.85,
            has_material_event=True,
        )
        assert story.story_id == "story-1"
        assert story.primary_article.id == "art-1"
        assert len(story.related_articles) == 1
        assert story.coverage_count == 2
        assert story.avg_sentiment == 0.85


class TestSourcePriority:
    """Tests for source priority configuration."""

    def test_sec_edgar_highest_priority(self) -> None:
        """Test SEC EDGAR has highest priority."""
        assert SOURCE_PRIORITY["sec_edgar"] == 5
        assert all(p <= 5 for p in SOURCE_PRIORITY.values())

    def test_google_news_lowest_priority(self) -> None:
        """Test Google News has lowest priority."""
        assert SOURCE_PRIORITY["google_news"] == 1
        assert all(p >= 1 for p in SOURCE_PRIORITY.values())

    def test_premium_sources_high_priority(self) -> None:
        """Test premium sources have high priority."""
        assert SOURCE_PRIORITY["reuters"] == 4
        assert SOURCE_PRIORITY["wsj"] == 4
        assert SOURCE_PRIORITY["bloomberg"] == 4
        assert SOURCE_PRIORITY["ft"] == 4


class TestStoryClustererBuildArticleText:
    """Tests for _build_article_text method."""

    def test_headline_only(self, clusterer: StoryClusterer) -> None:
        """Test building text from headline only."""
        article = NewsArticle(
            id="1",
            symbol="AAPL",
            headline="Apple stock rises",
            summary=None,
            vendor="yfinance",
            published_at=datetime.now(UTC),
        )
        text = clusterer._build_article_text(article)
        assert text == "Apple stock rises"

    def test_headline_and_summary(self, clusterer: StoryClusterer) -> None:
        """Test building text from headline + summary."""
        article = NewsArticle(
            id="1",
            symbol="AAPL",
            headline="Apple stock rises",
            summary="Shares up 5% on strong earnings",
            vendor="yfinance",
            published_at=datetime.now(UTC),
        )
        text = clusterer._build_article_text(article)
        assert text == "Apple stock rises Shares up 5% on strong earnings"


class TestStoryClustererSelectPrimaryArticle:
    """Tests for _select_primary_article method."""

    def test_selects_highest_priority_source(self, clusterer: StoryClusterer) -> None:
        """Test primary article selected by source priority."""
        base_time = datetime.now(UTC)
        articles = [
            NewsArticle(
                id="1",
                symbol="AAPL",
                headline="Same news",
                summary=None,
                vendor="yfinance",  # priority 2
                published_at=base_time,
            ),
            NewsArticle(
                id="2",
                symbol="AAPL",
                headline="Same news",
                summary=None,
                vendor="reuters",  # priority 4
                published_at=base_time,
            ),
            NewsArticle(
                id="3",
                symbol="AAPL",
                headline="Same news",
                summary=None,
                vendor="google_news",  # priority 1
                published_at=base_time,
            ),
        ]
        primary = clusterer._select_primary_article(articles)
        assert primary.id == "2"  # Reuters has highest priority

    def test_selects_newer_when_priority_tied(self, clusterer: StoryClusterer) -> None:
        """Test newer article selected when priority is tied."""
        base_time = datetime.now(UTC)
        articles = [
            NewsArticle(
                id="1",
                symbol="AAPL",
                headline="Same news",
                summary=None,
                vendor="reuters",  # priority 4
                published_at=base_time,  # Older
            ),
            NewsArticle(
                id="2",
                symbol="AAPL",
                headline="Same news",
                summary=None,
                vendor="wsj",  # priority 4 (tied)
                published_at=base_time + timedelta(hours=1),  # Newer
            ),
        ]
        primary = clusterer._select_primary_article(articles)
        assert primary.id == "2"  # Newer article wins on tie

    def test_unknown_vendor_lowest_priority(self, clusterer: StoryClusterer) -> None:
        """Test unknown vendor gets priority 0."""
        base_time = datetime.now(UTC)
        articles = [
            NewsArticle(
                id="1",
                symbol="AAPL",
                headline="Same news",
                summary=None,
                vendor="unknown_vendor",  # Not in SOURCE_PRIORITY
                published_at=base_time,
            ),
            NewsArticle(
                id="2",
                symbol="AAPL",
                headline="Same news",
                summary=None,
                vendor="google_news",  # priority 1
                published_at=base_time,
            ),
        ]
        primary = clusterer._select_primary_article(articles)
        assert primary.id == "2"  # Google News (1) > unknown (0)


class TestStoryClustererClusterBySimilarity:
    """Tests for _cluster_by_similarity method."""

    def test_similar_articles_clustered(self, clusterer: StoryClusterer) -> None:
        """Test articles above threshold are clustered together."""
        articles = [
            NewsArticle(
                id="1",
                symbol="AAPL",
                headline="A",
                summary=None,
                vendor="yfinance",
                published_at=datetime.now(UTC),
            ),
            NewsArticle(
                id="2",
                symbol="AAPL",
                headline="B",
                summary=None,
                vendor="yfinance",
                published_at=datetime.now(UTC),
            ),
        ]
        # Similarity matrix where articles 0 and 1 are very similar
        similarity = np.array([[1.0, 0.95], [0.95, 1.0]])
        clusters = clusterer._cluster_by_similarity(articles, similarity)
        # Should be 1 cluster with both articles
        assert len(clusters) == 1
        assert set(clusters[0]) == {0, 1}

    def test_dissimilar_articles_separate_clusters(self, clusterer: StoryClusterer) -> None:
        """Test articles below threshold are in separate clusters."""
        articles = [
            NewsArticle(
                id="1",
                symbol="AAPL",
                headline="A",
                summary=None,
                vendor="yfinance",
                published_at=datetime.now(UTC),
            ),
            NewsArticle(
                id="2",
                symbol="NVDA",
                headline="B",
                summary=None,
                vendor="yfinance",
                published_at=datetime.now(UTC),
            ),
        ]
        # Similarity matrix where articles are dissimilar
        similarity = np.array([[1.0, 0.3], [0.3, 1.0]])
        clusters = clusterer._cluster_by_similarity(articles, similarity)
        # Should be 2 separate clusters
        assert len(clusters) == 2
        assert [0] in clusters
        assert [1] in clusters


class TestStoryClustererUpdateMetadata:
    """Tests for update_article_clustering_metadata method."""

    def test_metadata_for_primary_article(
        self, clusterer: StoryClusterer, sample_articles: list[NewsArticle]
    ) -> None:
        """Test metadata marks primary article correctly."""
        story = Story(
            story_id="story-123",
            primary_article=sample_articles[0],
            related_articles=[sample_articles[1]],
            coverage_count=2,
            avg_sentiment=0.85,
            has_material_event=True,
        )
        metadata = clusterer.update_article_clustering_metadata([story])

        primary_meta = metadata["art-1"]
        assert primary_meta["story_id"] == "story-123"
        assert primary_meta["is_primary_article"] is True
        assert primary_meta["coverage_count"] == 2

    def test_metadata_for_related_articles(
        self, clusterer: StoryClusterer, sample_articles: list[NewsArticle]
    ) -> None:
        """Test metadata marks related articles correctly."""
        story = Story(
            story_id="story-123",
            primary_article=sample_articles[0],
            related_articles=[sample_articles[1]],
            coverage_count=2,
            avg_sentiment=0.85,
            has_material_event=True,
        )
        metadata = clusterer.update_article_clustering_metadata([story])

        related_meta = metadata["art-2"]
        assert related_meta["story_id"] == "story-123"
        assert related_meta["is_primary_article"] is False
        assert related_meta["coverage_count"] == 2


class TestStoryClustererClusterArticles:
    """Tests for cluster_articles method."""

    def test_empty_articles_returns_empty(self, clusterer: StoryClusterer) -> None:
        """Test empty input returns empty list."""
        result = clusterer.cluster_articles([])
        assert result == []

    @patch.object(StoryClusterer, "_generate_embeddings")
    @patch.object(StoryClusterer, "_calculate_similarity_matrix")
    def test_single_article_returns_story(
        self,
        mock_similarity: MagicMock,
        mock_embeddings: MagicMock,
        clusterer: StoryClusterer,
    ) -> None:
        """Test single article creates single story."""
        article = NewsArticle(
            id="1",
            symbol="AAPL",
            headline="Test",
            summary=None,
            vendor="reuters",
            published_at=datetime.now(UTC),
            sentiment_score=0.5,
        )

        mock_embeddings.return_value = np.array([[0.1, 0.2, 0.3]])
        mock_similarity.return_value = np.array([[1.0]])

        stories = clusterer.cluster_articles([article])

        assert len(stories) == 1
        assert stories[0].coverage_count == 1
        assert stories[0].primary_article.id == "1"

    @patch.object(StoryClusterer, "_generate_embeddings")
    @patch.object(StoryClusterer, "_calculate_similarity_matrix")
    def test_min_coverage_filters_small_clusters(
        self,
        mock_similarity: MagicMock,
        mock_embeddings: MagicMock,
        clusterer: StoryClusterer,
        sample_articles: list[NewsArticle],
    ) -> None:
        """Test min_coverage_for_story filters small clusters."""
        mock_embeddings.return_value = np.random.rand(3, 384)
        # All articles dissimilar - 3 clusters of 1
        mock_similarity.return_value = np.eye(3)

        # With min_coverage=2, no stories should be returned
        stories = clusterer.cluster_articles(sample_articles, min_coverage_for_story=2)
        assert len(stories) == 0

    @patch.object(StoryClusterer, "_generate_embeddings")
    @patch.object(StoryClusterer, "_calculate_similarity_matrix")
    def test_stories_sorted_by_coverage(
        self,
        mock_similarity: MagicMock,
        mock_embeddings: MagicMock,
        clusterer: StoryClusterer,
    ) -> None:
        """Test stories are sorted by coverage count descending."""
        articles = [
            NewsArticle(
                id=f"art-{i}",
                symbol="AAPL",
                headline=f"Article {i}",
                summary=None,
                vendor="yfinance",
                published_at=datetime.now(UTC),
            )
            for i in range(4)
        ]

        mock_embeddings.return_value = np.random.rand(4, 384)
        # Cluster articles 0,1,2 together (high similarity), article 3 separate
        similarity = np.array(
            [
                [1.0, 0.9, 0.9, 0.1],
                [0.9, 1.0, 0.9, 0.1],
                [0.9, 0.9, 1.0, 0.1],
                [0.1, 0.1, 0.1, 1.0],
            ]
        )
        mock_similarity.return_value = similarity

        stories = clusterer.cluster_articles(articles)

        # First story should have higher coverage
        assert len(stories) == 2
        assert stories[0].coverage_count >= stories[1].coverage_count

    @patch.object(StoryClusterer, "_generate_embeddings")
    @patch.object(StoryClusterer, "_calculate_similarity_matrix")
    def test_avg_sentiment_calculated(
        self,
        mock_similarity: MagicMock,
        mock_embeddings: MagicMock,
        clusterer: StoryClusterer,
    ) -> None:
        """Test average sentiment is calculated for clustered articles."""
        articles = [
            NewsArticle(
                id="1",
                symbol="AAPL",
                headline="Test",
                summary=None,
                vendor="yfinance",
                published_at=datetime.now(UTC),
                sentiment_score=0.6,
            ),
            NewsArticle(
                id="2",
                symbol="AAPL",
                headline="Test 2",
                summary=None,
                vendor="reuters",
                published_at=datetime.now(UTC),
                sentiment_score=0.8,
            ),
        ]

        mock_embeddings.return_value = np.random.rand(2, 384)
        mock_similarity.return_value = np.array([[1.0, 0.95], [0.95, 1.0]])

        stories = clusterer.cluster_articles(articles)

        assert len(stories) == 1
        assert stories[0].avg_sentiment == pytest.approx(0.7, rel=0.01)

    @patch.object(StoryClusterer, "_generate_embeddings")
    @patch.object(StoryClusterer, "_calculate_similarity_matrix")
    def test_has_material_event_flag(
        self,
        mock_similarity: MagicMock,
        mock_embeddings: MagicMock,
        clusterer: StoryClusterer,
    ) -> None:
        """Test has_material_event is True if any article has material event."""
        articles = [
            NewsArticle(
                id="1",
                symbol="AAPL",
                headline="Test",
                summary=None,
                vendor="yfinance",
                published_at=datetime.now(UTC),
                is_material_event=False,
            ),
            NewsArticle(
                id="2",
                symbol="AAPL",
                headline="Test 2",
                summary=None,
                vendor="sec_edgar",
                published_at=datetime.now(UTC),
                is_material_event=True,  # One article has material event
            ),
        ]

        mock_embeddings.return_value = np.random.rand(2, 384)
        mock_similarity.return_value = np.array([[1.0, 0.95], [0.95, 1.0]])

        stories = clusterer.cluster_articles(articles)

        assert stories[0].has_material_event is True
