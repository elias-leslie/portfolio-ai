"""AI-powered news features: story clustering and plain language translation."""

from __future__ import annotations

from typing import Any, cast

try:
    from .story_clusterer import NewsArticle as ClustererArticle
    from .story_clusterer import StoryClusterer
except Exception:  # pragma: no cover - handled via availability checks
    ClustererArticle = cast(Any, None)  # type: ignore[misc]
    StoryClusterer = cast(Any, None)  # type: ignore[misc]

try:
    from .plain_language_news import (
        classify_event_category,
        generate_actionable_insight,
        generate_impact_summary,
        translate_to_plain_language,
    )
except Exception:  # pragma: no cover - handled via availability checks
    classify_event_category = cast(Any, None)
    generate_actionable_insight = cast(Any, None)
    generate_impact_summary = cast(Any, None)
    translate_to_plain_language = cast(Any, None)

from ..logging_config import get_logger
from .news_models import NewsArticle

logger = get_logger(__name__)

# Feature flags
ENABLE_PLAIN_LANGUAGE_HEADLINES = False  # Disabled due to broken keyword-based transformation


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
            # Convert NewsArticle (Pydantic) to story_clusterer.NewsArticle (dataclass)
            clusterer_articles = []
            for article in articles:
                # Generate unique ID for clustering (use content_hash)
                clusterer_article = ClustererArticle(
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
                clusterer_articles.append(clusterer_article)

            # Run clustering
            clusterer = StoryClusterer()
            stories = clusterer.cluster_articles(clusterer_articles, min_coverage_for_story=1)

            # Get clustering metadata
            metadata = clusterer.update_article_clustering_metadata(stories)

            # Apply metadata to original articles
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
            # Non-fatal: clustering is enhancement, not critical
            logger.warning("story_clustering_failed", error=str(exc), error_type=type(exc).__name__)

        return articles

    def apply_plain_language_translation(
        self, articles: list[NewsArticle], watchlist_tickers: list[str] | None = None
    ) -> list[NewsArticle]:
        """Apply plain language translation to articles.

        Args:
            articles: List of scored NewsArticle objects
            watchlist_tickers: Optional list of tickers in user's watchlist for context-aware insights

        Returns:
            List of NewsArticle objects with impact_summary and actionable_insight set
        """
        if (
            not articles
            or classify_event_category is None
            or generate_actionable_insight is None
            or generate_impact_summary is None
            or translate_to_plain_language is None
        ):
            return articles

        try:
            for article in articles:
                # Classify event category
                event_category = classify_event_category(
                    headline=article.headline,
                    summary=article.summary,
                    filing_type=article.filing_type,
                )

                # Generate plain language headline if not already set
                # DISABLED: Keyword-based transformation is broken (wrong transformations, sentiment mismatch)
                # TODO: Re-enable when proper LLM-based transformation is implemented
                if ENABLE_PLAIN_LANGUAGE_HEADLINES and not article.plain_language_headline:
                    translation_result = translate_to_plain_language(
                        headline=article.headline,
                        summary=article.summary,
                        filing_type=article.filing_type,
                        sentiment_score=article.sentiment.score,
                        symbol=article.symbol,
                    )
                    article.plain_language_headline = translation_result["plain_language_headline"]

                # Generate impact summary
                article.impact_summary = generate_impact_summary(
                    category=event_category,
                    sentiment_score=article.sentiment.score,
                )

                # Generate actionable insight
                in_watchlist = article.symbol in watchlist_tickers if watchlist_tickers else False
                article.actionable_insight = generate_actionable_insight(
                    category=event_category,
                    sentiment_score=article.sentiment.score,
                    symbol=article.symbol,
                    in_watchlist=in_watchlist,
                )

            logger.info(
                "plain_language_translation_applied",
                num_articles=len(articles),
                num_with_insights=sum(1 for a in articles if a.actionable_insight),
            )

        except Exception as exc:
            # Non-fatal: plain language translation is enhancement, not critical
            logger.warning(
                "plain_language_translation_failed", error=str(exc), error_type=type(exc).__name__
            )

        return articles
