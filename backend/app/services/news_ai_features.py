"""AI-powered news features: story clustering and insight generation."""

from __future__ import annotations

from typing import Any, cast

try:
    from .story_clusterer import NewsArticle as ClustererArticle
    from .story_clusterer import StoryClusterer
except Exception:  # pragma: no cover - handled via availability checks
    ClustererArticle = cast(Any, None)
    StoryClusterer = cast(Any, None)

try:
    from .plain_language_news import (
        classify_event_category,
        generate_actionable_insight,
        generate_impact_summary,
    )
except Exception:  # pragma: no cover - handled via availability checks
    classify_event_category = cast(Any, None)
    generate_actionable_insight = cast(Any, None)
    generate_impact_summary = cast(Any, None)

from ..logging_config import get_logger
from .news_models import NewsArticle

logger = get_logger(__name__)


def _build_clusterer_articles(articles: list[NewsArticle]) -> list[Any]:
    """Convert Pydantic NewsArticle list to story_clusterer dataclass list."""
    result = []
    for article in articles:
        result.append(
            ClustererArticle(
                id=article.content_hash,
                symbol=article.symbol,
                headline=article.headline,
                summary=article.summary,
                vendor=article.vendor or "unknown",
                published_at=article.published_at or article.fetched_at,
                sentiment_score=article.sentiment.score,
                is_material_event=article.is_material_event,
                filing_type=article.filing_type,
            )
        )
    return result


def _apply_article_insights(
    article: NewsArticle, watchlist_symbols: list[str] | None
) -> None:
    """Generate and set impact_summary and actionable_insight on a single article."""
    event_category = classify_event_category(
        headline=article.headline,
        summary=article.summary,
        filing_type=article.filing_type,
    )
    article.impact_summary = generate_impact_summary(
        category=event_category,
        sentiment_score=article.sentiment.score,
    )
    in_watchlist = article.symbol in watchlist_symbols if watchlist_symbols else False
    article.actionable_insight = generate_actionable_insight(
        category=event_category,
        sentiment_score=article.sentiment.score,
        symbol=article.symbol,
        in_watchlist=in_watchlist,
    )


class NewsAIFeatures:
    """Manages AI-powered news features."""

    def apply_story_clustering(self, articles: list[NewsArticle]) -> list[NewsArticle]:
        """Apply story clustering to group articles by semantic similarity.

        Args:
            articles: List of scored NewsArticle objects

        Returns:
            List of NewsArticle objects with story_id, is_primary_article, and coverage_count set
        """
        if not articles or ClustererArticle is None or StoryClusterer is None:
            return articles

        try:
            clusterer_articles = _build_clusterer_articles(articles)
            clusterer = StoryClusterer()
            stories = clusterer.cluster_articles(clusterer_articles, min_coverage_for_story=1)
            metadata = clusterer.update_article_clustering_metadata(stories)

            for article in articles:
                article_metadata = metadata.get(article.content_hash)
                if article_metadata:
                    article.story_id = article_metadata["story_id"]
                    article.is_primary_article = article_metadata["is_primary_article"]
                    article.coverage_count = article_metadata["coverage_count"]

            logger.info(
                "story_clustering_applied",
                num_articles=len(articles),
                num_stories=len(stories),
                avg_coverage=sum(s.coverage_count for s in stories) / len(stories)
                if stories
                else 0,
            )

        except Exception as exc:
            logger.warning("story_clustering_failed", error=str(exc), error_type=type(exc).__name__)

        return articles

    def apply_insight_generation(
        self, articles: list[NewsArticle], watchlist_symbols: list[str] | None = None
    ) -> list[NewsArticle]:
        """Apply rule-based insight generation to articles.

        Generates impact_summary and actionable_insight based on event category
        and sentiment score (pure rule-based, no LLM calls).

        Args:
            articles: List of scored NewsArticle objects
            watchlist_symbols: Optional list of symbols in user's watchlist for context-aware insights

        Returns:
            List of NewsArticle objects with impact_summary and actionable_insight set
        """
        _missing = classify_event_category is None or generate_actionable_insight is None or generate_impact_summary is None
        if not articles or _missing:
            return articles

        try:
            for article in articles:
                _apply_article_insights(article, watchlist_symbols)

            logger.info(
                "insight_generation_applied",
                num_articles=len(articles),
                num_with_insights=sum(1 for a in articles if a.actionable_insight),
            )

        except Exception as exc:
            logger.warning(
                "insight_generation_failed", error=str(exc), error_type=type(exc).__name__
            )

        return articles
