"""Story clustering service for news article deduplication.

This module implements semantic story clustering using sentence-transformers
to group news articles that describe the same event, even with different headlines.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, ClassVar

import numpy as np
from numpy.typing import NDArray
from sklearn.metrics.pairwise import cosine_similarity

from ..logging_config import get_logger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

# Lazy import to avoid startup overhead
_model: SentenceTransformer | None = None

logger = get_logger(__name__)

# Source priority for selecting primary article (higher = better)
SOURCE_PRIORITY: dict[str, int] = {
    "sec_edgar": 5,  # Highest - official SEC filings
    "ft": 4,  # Financial Times
    "reuters": 4,  # Reuters
    "wsj": 4,  # Wall Street Journal
    "bloomberg": 4,  # Bloomberg
    "polygon": 3,  # Polygon (paid tier)
    "finnhub": 3,  # Finnhub
    "yfinance": 2,  # Yahoo Finance
    "seeking_alpha_rss": 2,  # Seeking Alpha RSS
    "google_news": 1,  # Lowest - news aggregator
}


@dataclass
class NewsArticle:
    """News article for clustering."""

    id: str
    ticker: str
    headline: str
    summary: str | None
    vendor: str
    published_at: datetime
    sentiment_score: float | None = None
    is_material_event: bool = False
    filing_type: str | None = None


@dataclass
class Story:
    """Clustered story with primary article and related coverage."""

    story_id: str
    primary_article: NewsArticle
    related_articles: list[NewsArticle]
    coverage_count: int
    avg_sentiment: float | None
    has_material_event: bool


class StoryClusterer:
    """Semantic story clustering using sentence-transformers.

    Clusters news articles by semantic similarity to group articles about
    the same event/story from different sources. Selects primary article
    from highest-priority source.

    Example:
        >>> clusterer = StoryClusterer()
        >>> articles = [...]  # List of NewsArticle objects
        >>> stories = clusterer.cluster_articles(articles)
        >>> for story in stories:
        ...     print(f"{story.coverage_count} articles about: {story.primary_article.headline}")
    """

    # Similarity threshold for clustering (0.0-1.0)
    SIMILARITY_THRESHOLD: ClassVar[float] = 0.85

    # Model name (lightweight, fast, good quality)
    MODEL_NAME: ClassVar[str] = "all-MiniLM-L6-v2"

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize story clusterer with sentence transformer model.

        Args:
            model_name: Optional model name (default: all-MiniLM-L6-v2)
        """
        self.model_name = model_name or self.MODEL_NAME
        logger.info("story_clusterer_initialized", model=self.model_name)

    def _get_model(self) -> SentenceTransformer:
        """Lazy load sentence transformer model.

        Returns:
            Loaded SentenceTransformer model

        Note:
            Model is cached globally to avoid reloading on each request.
        """
        global _model  # noqa: PLW0603

        if _model is None:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            logger.info("loading_sentence_transformer", model=self.model_name)
            _model = SentenceTransformer(self.model_name)
            logger.info("sentence_transformer_loaded", model=self.model_name)

        return _model

    def _generate_embeddings(self, texts: Sequence[str]) -> NDArray[np.float32]:
        """Generate sentence embeddings for text list.

        Args:
            texts: List of strings to embed

        Returns:
            2D array of embeddings (shape: [num_texts, embedding_dim])
        """
        model = self._get_model()
        # Convert to list for type compatibility with sentence-transformers
        texts_list = list(texts)
        embeddings: NDArray[np.float32] = model.encode(
            texts_list, convert_to_numpy=True, show_progress_bar=False
        )
        return embeddings

    def _build_article_text(self, article: NewsArticle) -> str:
        """Build text representation of article for embedding.

        Args:
            article: NewsArticle to convert to text

        Returns:
            Combined headline + summary text
        """
        # Combine headline and summary for better semantic representation
        text = article.headline
        if article.summary:
            text += f" {article.summary}"
        return text

    def _calculate_similarity_matrix(self, embeddings: NDArray[np.float32]) -> NDArray[np.float64]:
        """Calculate cosine similarity matrix between embeddings.

        Args:
            embeddings: 2D array of embeddings

        Returns:
            2D similarity matrix (values 0.0-1.0)
        """
        similarity: NDArray[np.float64] = cosine_similarity(embeddings)
        return similarity

    def _select_primary_article(self, cluster: list[NewsArticle]) -> NewsArticle:
        """Select primary article from cluster based on source priority.

        Args:
            cluster: List of articles in same cluster

        Returns:
            Primary article (highest priority source, newest if tied)
        """
        # Sort by: priority (desc), published time (desc)
        sorted_articles = sorted(
            cluster,
            key=lambda a: (
                SOURCE_PRIORITY.get(a.vendor, 0),  # Higher priority first
                a.published_at,  # Newer first
            ),
            reverse=True,
        )

        return sorted_articles[0]

    def _cluster_by_similarity(
        self, articles: Sequence[NewsArticle], similarity_matrix: NDArray[np.float64]
    ) -> list[list[int]]:
        """Cluster articles by similarity threshold.

        Uses simple agglomerative clustering: articles with similarity > threshold
        are grouped together.

        Args:
            articles: List of articles
            similarity_matrix: Pairwise similarity matrix

        Returns:
            List of clusters, where each cluster is a list of article indices
        """
        num_articles = len(articles)
        visited = set()
        clusters: list[list[int]] = []

        for i in range(num_articles):
            if i in visited:
                continue

            # Start new cluster with article i
            cluster = [i]
            visited.add(i)

            # Find all similar articles
            for j in range(i + 1, num_articles):
                if j not in visited and similarity_matrix[i][j] > self.SIMILARITY_THRESHOLD:
                    cluster.append(j)
                    visited.add(j)

            clusters.append(cluster)

        return clusters

    def cluster_articles(
        self,
        articles: Sequence[NewsArticle],
        min_coverage_for_story: int = 1,
    ) -> list[Story]:
        """Cluster news articles into stories by semantic similarity.

        Args:
            articles: List of NewsArticle objects to cluster
            min_coverage_for_story: Minimum articles required to form a story (default: 1)

        Returns:
            List of Story objects with primary article and coverage metadata

        Example:
            >>> clusterer = StoryClusterer()
            >>> articles = [
            ...     NewsArticle(id="1", headline="NVDA beats earnings", ...),
            ...     NewsArticle(id="2", headline="Nvidia crushes Q2 results", ...),
            ...     NewsArticle(id="3", headline="Apple announces M3 chip", ...),
            ... ]
            >>> stories = clusterer.cluster_articles(articles)
            >>> # stories[0] = Story with 2 articles about NVDA earnings
            >>> # stories[1] = Story with 1 article about Apple M3
        """
        if not articles:
            logger.debug("no_articles_to_cluster")
            return []

        logger.info("clustering_articles_start", num_articles=len(articles))

        # Step 1: Generate embeddings for all articles
        texts = [self._build_article_text(article) for article in articles]
        embeddings = self._generate_embeddings(texts)

        # Step 2: Calculate similarity matrix
        similarity_matrix = self._calculate_similarity_matrix(embeddings)

        # Step 3: Cluster by similarity
        clusters = self._cluster_by_similarity(articles, similarity_matrix)

        # Step 4: Build Story objects from clusters
        stories: list[Story] = []

        for cluster_indices in clusters:
            if len(cluster_indices) < min_coverage_for_story:
                continue

            cluster_articles = [articles[i] for i in cluster_indices]

            # Select primary article (highest priority source)
            primary = self._select_primary_article(cluster_articles)

            # Calculate statistics
            coverage_count = len(cluster_articles)
            sentiment_scores = [
                a.sentiment_score for a in cluster_articles if a.sentiment_score is not None
            ]
            avg_sentiment = float(np.mean(sentiment_scores)) if sentiment_scores else None
            has_material_event = any(a.is_material_event for a in cluster_articles)

            # Remove primary from related articles
            related = [a for a in cluster_articles if a.id != primary.id]

            story = Story(
                story_id=str(uuid.uuid4()),
                primary_article=primary,
                related_articles=related,
                coverage_count=coverage_count,
                avg_sentiment=avg_sentiment,
                has_material_event=has_material_event,
            )

            stories.append(story)

        logger.info(
            "clustering_articles_complete",
            num_articles=len(articles),
            num_stories=len(stories),
            avg_coverage=float(np.mean([s.coverage_count for s in stories])) if stories else 0,
        )

        # Sort stories by coverage count (descending)
        stories.sort(key=lambda s: s.coverage_count, reverse=True)

        return stories

    def update_article_clustering_metadata(
        self, stories: Sequence[Story]
    ) -> dict[str, dict[str, Any]]:
        """Generate clustering metadata for database updates.

        Args:
            stories: List of clustered stories

        Returns:
            Dict mapping article_id to clustering metadata:
            {
                "article_id": {
                    "story_id": "uuid",
                    "is_primary_article": bool,
                    "coverage_count": int
                }
            }
        """
        metadata: dict[str, dict[str, Any]] = {}

        for story in stories:
            # Primary article
            metadata[story.primary_article.id] = {
                "story_id": story.story_id,
                "is_primary_article": True,
                "coverage_count": story.coverage_count,
            }

            # Related articles
            for article in story.related_articles:
                metadata[article.id] = {
                    "story_id": story.story_id,
                    "is_primary_article": False,
                    "coverage_count": story.coverage_count,
                }

        return metadata
