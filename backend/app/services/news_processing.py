"""News article processing and sentiment scoring."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any, Protocol, cast

from dateutil import parser as date_parser  # type: ignore[import-untyped]

from ..logging_config import get_logger
from .news_models import NewsArticle, NewsSummary, SentimentScore

logger = get_logger(__name__)


# Forward declarations to avoid circular imports
class FinBertUnavailableError(RuntimeError):
    """Raised when FinBERT cannot be loaded or executed."""


class SentimentAnalyzer(Protocol):
    """Protocol for sentiment analyzers."""

    def score_batch(self, texts: Sequence[str]) -> list[SentimentScore]:
        """Score a batch of texts."""
        ...


# Use Protocol for type hints instead of importing concrete classes
FinBertSentimentAnalyzer = SentimentAnalyzer
VaderSentimentAnalyzer = SentimentAnalyzer


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse datetime string to UTC datetime."""
    if not value:
        return None
    with suppress(Exception):
        parsed = cast(datetime, date_parser.parse(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _hash_content(ticker: str, headline: str, source: str | None) -> str:
    """Generate content hash for deduplication."""
    base = f"{ticker}::{headline.strip()}::{source or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _compose_text(entry: dict[str, Any]) -> str:
    """Compose text for sentiment analysis from entry."""
    headline = entry.get("title") or entry.get("headline") or ""
    summary = entry.get("summary") or entry.get("description") or ""
    combined = f"{headline.strip()}. {summary.strip()}" if summary else headline.strip()
    return combined or "No headline available."


class NewsProcessor:
    """Processes news articles with sentiment scoring and aggregation."""

    def __init__(
        self,
        *,
        finbert_analyzer: FinBertSentimentAnalyzer,
        fallback_analyzer: VaderSentimentAnalyzer,
    ) -> None:
        self.finbert_analyzer = finbert_analyzer
        self.fallback_analyzer = fallback_analyzer

    def merge_entries(
        self,
        *,
        ticker: str,
        vendor_entries: Sequence[dict[str, Any]],
        max_entries: int,
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
        """Merge and deduplicate entries from all vendors."""
        seen: set[tuple[str, str]] = set()
        merged: list[dict[str, Any]] = []

        for entry in vendor_entries:
            headline = (entry.get("headline") or entry.get("title") or "").strip()
            if not headline:
                continue
            source_name = entry.get("news_source_name")
            if isinstance(source_name, dict):
                source_name = source_name.get("title")
            if not source_name:
                raw_source = entry.get("source")
                if isinstance(raw_source, dict):
                    source_name = raw_source.get("title")
                else:
                    source_name = raw_source
            key = (headline.lower(), (source_name or "").lower())
            if key in seen:
                continue
            seen.add(key)
            normalized = dict(entry)
            normalized.setdefault("ticker", ticker)
            merged.append(normalized)
            if len(merged) >= max_entries:
                break

        limited = merged[:max_entries]
        post_counts: Counter[str] = Counter()
        for entry in limited:
            vendor = str(entry.get("vendor") or "unknown").strip() or "unknown"
            post_counts[vendor] += 1

        return limited, {vendor: int(count) for vendor, count in post_counts.items()}

    def select_recent_articles(
        self,
        articles: Sequence[NewsArticle],
        now: datetime,
        *,
        max_articles: int,
        ttl: timedelta,
    ) -> list[NewsArticle]:
        """Filter articles to TTL window with graceful stale backfill."""
        fresh: list[NewsArticle] = []
        stale_candidates: list[NewsArticle] = []
        seen_hashes: set[str] = set()
        earliest = now - ttl

        for article in sorted(
            articles, key=lambda a: (a.fetched_at, a.published_at or a.fetched_at), reverse=True
        ):
            if article.content_hash in seen_hashes:
                continue

            seen_hashes.add(article.content_hash)
            reference_dt = article.published_at or article.fetched_at

            if reference_dt >= earliest and len(fresh) < max_articles:
                fresh.append(article)
                continue

            if reference_dt < earliest:
                payload = dict(article.raw)
                payload["stale"] = True
                stale_article = article.model_copy(update={"raw": payload})
                stale_candidates.append(stale_article)

        if len(fresh) >= max_articles:
            return fresh[:max_articles]

        result: list[NewsArticle] = list(fresh)
        for article in stale_candidates:
            result.append(article)
            if len(result) >= max_articles:
                break

        return result

    def score_entries(
        self,
        *,
        ticker: str,
        entries: Sequence[dict[str, Any]],
        now: datetime,
    ) -> list[NewsArticle]:
        """Score entries with sentiment analysis."""
        if not entries:
            return []

        texts = [_compose_text(entry) for entry in entries]
        analyzer_used = "finbert"
        fallback_details: dict[str, Any] | None = None
        finbert_latency_ms: float | None = None

        try:
            start = perf_counter()
            sentiments = self.finbert_analyzer.score_batch(texts)
            finbert_latency_ms = (perf_counter() - start) * 1000.0
        except FinBertUnavailableError:
            finbert_latency_ms = (perf_counter() - start) * 1000.0
            fallback_details = {
                "reason": "unavailable",
                "latency_ms": round(finbert_latency_ms, 2),
            }
            logger.warning(
                "FinBERT unavailable, falling back to VADER",
                symbol=ticker,
                latency_ms=fallback_details["latency_ms"],
            )
            sentiments = self.fallback_analyzer.score_batch(texts)
            analyzer_used = "vader"
        except Exception as exc:  # pragma: no cover - inference failure
            finbert_latency_ms = (perf_counter() - start) * 1000.0
            fallback_details = {
                "reason": "error",
                "latency_ms": round(finbert_latency_ms, 2),
                "error": str(exc),
            }
            logger.error(
                "FinBERT scoring failed; falling back to VADER",
                error=str(exc),
                symbol=ticker,
                latency_ms=fallback_details["latency_ms"],
            )
            sentiments = self.fallback_analyzer.score_batch(texts)
            analyzer_used = "vader"

        articles: list[NewsArticle] = []
        for entry, sentiment in zip(entries, sentiments, strict=True):
            headline = entry.get("title") or entry.get("headline")
            if not headline:
                continue

            source_name = (
                entry.get("source", {}).get("title")
                if isinstance(entry.get("source"), dict)
                else entry.get("source")
            )
            summary = entry.get("summary") or entry.get("description")
            published = _parse_datetime(entry.get("published") or entry.get("published_at"))
            content_hash = _hash_content(ticker, headline, source_name)
            vendor = entry.get("vendor")
            if vendor is None:
                raw_entry = entry.get("raw")
                if isinstance(raw_entry, dict):
                    vendor = raw_entry.get("vendor")

            article_payload = {
                "raw": entry,
                "sentiment_probabilities": sentiment.probabilities,
                "sentiment_model": sentiment.model,
            }
            if vendor:
                article_payload["vendor"] = vendor

            articles.append(
                NewsArticle(
                    symbol=ticker,
                    headline=headline,
                    url=entry.get("link") or entry.get("url"),
                    summary=summary,
                    source=source_name,
                    author=entry.get("author"),
                    image_url=entry.get("image_url"),
                    published_at=published,
                    fetched_at=now,
                    sentiment=sentiment,
                    content_hash=content_hash,
                    raw=article_payload,
                    vendor=vendor,
                )
            )

        total_sentiments = len(sentiments)
        fallback_rate = 0.0
        if total_sentiments:
            fallback_rate = (
                sum(1 for sentiment in sentiments if sentiment.model != "finbert")
                / total_sentiments
            )

        if analyzer_used != "finbert":
            latency_ms = round(finbert_latency_ms or 0.0, 2)
            if fallback_details is None:
                fallback_details = {"reason": "unknown", "latency_ms": latency_ms}
            fallback_details.setdefault("latency_ms", latency_ms)
            fallback_details.update(
                {
                    "rate": round(fallback_rate, 4),
                    "article_count": len(articles),
                }
            )
            for article in articles:
                article.raw.setdefault("sentiment_fallback", dict(fallback_details))

            logger.info(
                "news_sentiment_fallback_used",
                symbol=ticker,
                analyzer=analyzer_used,
                articles=len(articles),
                fallback_rate=round(fallback_rate, 4),
                latency_ms=fallback_details.get("latency_ms"),
                reason=fallback_details.get("reason"),
            )

        return articles

    def build_summary(
        self,
        *,
        ticker: str,
        articles: Sequence[NewsArticle],
        previous_articles: Sequence[NewsArticle],
        as_of: datetime,
        ttl: timedelta,
    ) -> NewsSummary:
        """Build aggregated sentiment summary."""
        if not articles:
            return NewsSummary(
                symbol=ticker,
                score=None,
                score_change=None,
                positive_count=0,
                neutral_count=0,
                negative_count=0,
                article_count=0,
                latest_published_at=None,
                model_breakdown={},
            )

        weights = []
        weighted_scores = []

        latest_published_at = None
        counts: Counter[str] = Counter()
        model_counts: Counter[str] = Counter()

        summary_articles = [article for article in articles if not article.raw.get("stale")]
        if not summary_articles:
            summary_articles = list(articles)

        ttl_hours = max(ttl.total_seconds() / 3600.0, 0.1)
        for article in summary_articles:
            counts[article.sentiment.label] += 1
            model_counts[article.sentiment.model] += 1

            reference_dt = article.published_at or article.fetched_at
            if latest_published_at is None or reference_dt > latest_published_at:
                latest_published_at = reference_dt

            hours_since = max(0.0, (as_of - reference_dt).total_seconds() / 3600.0)
            weight = math.exp(-hours_since / ttl_hours)
            weight = max(weight, 0.1)  # Prevent zero weight
            weights.append(weight)
            weighted_scores.append(article.sentiment.score * weight)

        aggregated_score = sum(weighted_scores) / sum(weights) if weights else None

        previous_score = self._compute_previous_score(previous_articles, as_of, ttl)
        score_change = None
        if aggregated_score is not None and previous_score is not None:
            score_change = aggregated_score - previous_score

        top_positive = max(articles, key=lambda a: a.sentiment.score, default=None)
        top_negative = min(articles, key=lambda a: a.sentiment.score, default=None)

        return NewsSummary(
            symbol=ticker,
            score=aggregated_score,
            score_change=score_change,
            positive_count=counts["positive"],
            neutral_count=counts["neutral"],
            negative_count=counts["negative"],
            article_count=len(summary_articles),
            latest_published_at=latest_published_at,
            top_positive=top_positive
            if top_positive and top_positive.sentiment.score > 0
            else None,
            top_negative=top_negative
            if top_negative and top_negative.sentiment.score < 0
            else None,
            model_breakdown=dict(model_counts),
        )

    def _compute_previous_score(
        self, articles: Sequence[NewsArticle], as_of: datetime, ttl: timedelta
    ) -> float | None:
        """Compute previous score for score_change calculation."""
        if not articles:
            return None

        weights = []
        weighted_scores = []
        ttl_hours = max(ttl.total_seconds() / 3600.0, 0.1)
        for article in articles:
            reference_dt = article.published_at or article.fetched_at
            hours_since = max(0.0, (as_of - reference_dt).total_seconds() / 3600.0)
            weight = math.exp(-hours_since / (ttl_hours * 2))
            weight = max(weight, 0.1)
            weights.append(weight)
            weighted_scores.append(article.sentiment.score * weight)

        return sum(weighted_scores) / sum(weights) if weights else None
