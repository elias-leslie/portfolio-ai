"""News caching and database operations."""

from __future__ import annotations

import json
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from .news_models import NewsArticle, SentimentScore
from .news_types import ArticleDbRowDict

logger = get_logger(__name__)


@dataclass(frozen=True)
class CachedArticles:
    """Cached article payload with staleness metadata."""

    articles: list[NewsArticle]
    fetched_at: datetime | None

    def is_stale(self, ttl: timedelta, now: datetime) -> bool:
        if not self.fetched_at:
            return True
        return self.fetched_at < now - ttl


class NewsCacheManager:
    """Manages news article caching and database operations."""

    def __init__(self, storage: PortfolioStorage) -> None:
        self.storage = storage

    def load_cached_articles(self, ticker: str, limit: int) -> CachedArticles:
        """Load cached articles from database for a given ticker."""
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    symbol,
                    headline,
                    url,
                    summary,
                    news_source_name,
                    author,
                    image_url,
                    published_at,
                    sentiment_score,
                    sentiment_label,
                    sentiment_confidence,
                    sentiment_model,
                    raw_payload,
                    content_hash,
                    fetched_at,
                    updated_at,
                    filing_type,
                    is_material_event,
                    plain_language_headline,
                    story_id,
                    is_primary_article,
                    coverage_count,
                    impact_summary,
                    actionable_insight,
                    quality_prediction,
                    quality_confidence
                FROM news_cache
                WHERE symbol = %s
                ORDER BY fetched_at DESC, published_at DESC NULLS LAST
                LIMIT %s
                """,
                [ticker, limit],
            ).fetchall()

        articles = [self._row_to_article(row) for row in rows]
        latest_fetched_at = max((article.fetched_at for article in articles), default=None)
        return CachedArticles(articles=articles, fetched_at=latest_fetched_at)

    def load_articles_in_window(
        self,
        *,
        ticker: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[NewsArticle]:
        """Load articles within a specific time window."""
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    symbol,
                    headline,
                    url,
                    summary,
                    news_source_name,
                    author,
                    image_url,
                    published_at,
                    sentiment_score,
                    sentiment_label,
                    sentiment_confidence,
                    sentiment_model,
                    raw_payload,
                    content_hash,
                    fetched_at,
                    updated_at,
                    filing_type,
                    is_material_event,
                    plain_language_headline,
                    story_id,
                    is_primary_article,
                    coverage_count,
                    impact_summary,
                    actionable_insight,
                    quality_prediction,
                    quality_confidence
                FROM news_cache
                WHERE symbol = %s
                  AND fetched_at >= %s
                  AND fetched_at < %s
                ORDER BY fetched_at DESC, published_at DESC NULLS LAST
                LIMIT %s
                """,
                [ticker, start, end, limit],
            ).fetchall()

        return [self._row_to_article(row) for row in rows]

    def _row_to_article(self, row: Sequence[Any]) -> NewsArticle:
        """Convert database row to NewsArticle object."""
        (
            symbol,
            headline,
            url,
            summary,
            news_source_name,
            author,
            image_url,
            published_at,
            sentiment_score,
            sentiment_label,
            sentiment_confidence,
            sentiment_model,
            raw_payload,
            content_hash,
            fetched_at,
            _updated_at,
            filing_type,
            is_material_event,
            plain_language_headline,
            story_id,
            is_primary_article,
            coverage_count,
            impact_summary,
            actionable_insight,
            quality_prediction,
            quality_confidence,
        ) = row

        published_dt = published_at.astimezone(UTC) if isinstance(published_at, datetime) else None
        fetched_dt = (
            fetched_at.astimezone(UTC) if isinstance(fetched_at, datetime) else datetime.now(UTC)
        )

        raw_dict: dict[str, Any] = {}
        if raw_payload:
            if isinstance(raw_payload, dict):
                raw_dict = raw_payload
            else:
                with suppress(Exception):
                    parsed = json.loads(raw_payload)
                    # Ensure we always have a dict (JSON might be an array)
                    if isinstance(parsed, dict):
                        raw_dict = parsed
                    else:
                        logger.warning(
                            "raw_payload_not_dict",
                            content_hash=content_hash,
                            parsed_type=type(parsed).__name__,
                        )

        vendor = raw_dict.get("vendor")
        if vendor is None:
            inner_raw = raw_dict.get("raw")
            if isinstance(inner_raw, dict):
                vendor = inner_raw.get("vendor")

        return NewsArticle(
            symbol=symbol,
            headline=headline,
            url=url,
            summary=summary,
            source=news_source_name,
            author=author,
            image_url=image_url,
            published_at=published_dt,
            fetched_at=fetched_dt,
            sentiment=SentimentScore(
                score=float(sentiment_score) if sentiment_score is not None else 0.0,
                label=sentiment_label or "neutral",
                confidence=float(sentiment_confidence) if sentiment_confidence is not None else 0.0,
                model=sentiment_model or "unknown",
                probabilities=raw_dict.get("sentiment_probabilities", {}),
            ),
            content_hash=content_hash,
            raw=raw_dict,
            vendor=vendor,
            filing_type=filing_type,
            is_material_event=bool(is_material_event),
            plain_language_headline=plain_language_headline,
            story_id=story_id,
            is_primary_article=bool(is_primary_article),
            coverage_count=int(coverage_count) if coverage_count is not None else 1,
            impact_summary=impact_summary,
            actionable_insight=actionable_insight,
            quality_prediction=quality_prediction,
            quality_confidence=float(quality_confidence)
            if quality_confidence is not None
            else None,
        )

    def article_to_db_row(self, article: NewsArticle) -> ArticleDbRowDict:
        """Convert NewsArticle to database row format."""
        payload = article.raw
        # Defensive check: ensure payload is a dict (fix for list indices error)
        if not isinstance(payload, dict):
            logger.warning(
                "article_raw_not_dict",
                symbol=article.symbol,
                headline=article.headline[:50] if article.headline else "",
                raw_type=type(payload).__name__,
            )
            payload = {}
        if "sentiment_probabilities" not in payload:
            payload["sentiment_probabilities"] = article.sentiment.probabilities
        payload.setdefault("sentiment_model", article.sentiment.model)
        if article.vendor:
            payload.setdefault("vendor", article.vendor)

        return {
            "symbol": article.ticker,
            "headline": article.headline,
            "url": article.url,
            "summary": article.summary,
            "news_source_name": article.source,
            "author": article.author,
            "image_url": article.image_url,
            "published_at": article.published_at,
            "sentiment_score": article.sentiment.score,
            "sentiment_label": article.sentiment.label,
            "sentiment_confidence": article.sentiment.confidence,
            "sentiment_model": article.sentiment.model,
            "raw_payload": json.dumps(payload),
            "content_hash": article.content_hash,
            "fetched_at": article.fetched_at,
            "created_at": article.fetched_at,
            "updated_at": article.fetched_at,
            "filing_type": article.filing_type,
            "is_material_event": article.is_material_event,
            "plain_language_headline": article.plain_language_headline,
            "story_id": article.story_id,
            "is_primary_article": article.is_primary_article,
            "coverage_count": article.coverage_count,
            "impact_summary": article.impact_summary,
            "actionable_insight": article.actionable_insight,
            "quality_prediction": getattr(article, "quality_prediction", None),
            "quality_confidence": getattr(article, "quality_confidence", None),
        }

    def save_articles(self, articles: list[NewsArticle]) -> None:
        """Save articles to database with upsert logic."""
        if not articles:
            return

        rows_to_insert = [self.article_to_db_row(article) for article in articles]

        with self.storage.connection() as conn:
            for row in rows_to_insert:
                conn.execute(
                    """
                    INSERT INTO news_cache (
                        symbol,
                        headline,
                        url,
                        summary,
                        news_source_name,
                        author,
                        image_url,
                        published_at,
                        sentiment_score,
                        sentiment_label,
                        sentiment_confidence,
                        sentiment_model,
                        raw_payload,
                        content_hash,
                        fetched_at,
                        created_at,
                        updated_at,
                        filing_type,
                        is_material_event,
                        plain_language_headline,
                        story_id,
                        is_primary_article,
                        coverage_count,
                        impact_summary,
                        actionable_insight,
                        quality_prediction,
                        quality_confidence
                    ) VALUES (
                        %(symbol)s,
                        %(headline)s,
                        %(url)s,
                        %(summary)s,
                        %(news_source_name)s,
                        %(author)s,
                        %(image_url)s,
                        %(published_at)s,
                        %(sentiment_score)s,
                        %(sentiment_label)s,
                        %(sentiment_confidence)s,
                        %(sentiment_model)s,
                        %(raw_payload)s,
                        %(content_hash)s,
                        %(fetched_at)s,
                        %(created_at)s,
                        %(updated_at)s,
                        %(filing_type)s,
                        %(is_material_event)s,
                        %(plain_language_headline)s,
                        %(story_id)s,
                        %(is_primary_article)s,
                        %(coverage_count)s,
                        %(impact_summary)s,
                        %(actionable_insight)s,
                        %(quality_prediction)s,
                        %(quality_confidence)s
                    )
                    ON CONFLICT (symbol, content_hash) DO UPDATE SET
                        url = EXCLUDED.url,
                        summary = EXCLUDED.summary,
                        news_source_name = EXCLUDED.news_source_name,
                        author = EXCLUDED.author,
                        image_url = EXCLUDED.image_url,
                        published_at = COALESCE(EXCLUDED.published_at, news_cache.published_at),
                        sentiment_score = EXCLUDED.sentiment_score,
                        sentiment_label = EXCLUDED.sentiment_label,
                        sentiment_confidence = EXCLUDED.sentiment_confidence,
                        sentiment_model = EXCLUDED.sentiment_model,
                        raw_payload = EXCLUDED.raw_payload,
                        fetched_at = EXCLUDED.fetched_at,
                        updated_at = EXCLUDED.updated_at,
                        story_id = EXCLUDED.story_id,
                        is_primary_article = EXCLUDED.is_primary_article,
                        coverage_count = EXCLUDED.coverage_count,
                        impact_summary = EXCLUDED.impact_summary,
                        actionable_insight = EXCLUDED.actionable_insight,
                        quality_prediction = EXCLUDED.quality_prediction,
                        quality_confidence = EXCLUDED.quality_confidence
                    """,
                    dict(row),  # type: ignore[arg-type]  # Dict for named placeholders %(name)s
                )
            conn.commit()
