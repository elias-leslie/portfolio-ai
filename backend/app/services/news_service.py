"""Unified news fetching, caching, and sentiment scoring."""

from __future__ import annotations

import hashlib
import json
import math
import threading
from collections import Counter
from collections.abc import Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
from typing import Any, Literal, cast

from dateutil import parser as date_parser  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

try:
    torch = import_module("torch")
except Exception:  # pragma: no cover - handled via availability checks
    torch = cast(Any, None)

try:
    transformers = import_module("transformers")
    AutoModelForSequenceClassification = transformers.AutoModelForSequenceClassification
    AutoTokenizer = transformers.AutoTokenizer
except Exception:  # pragma: no cover - handled via availability checks
    AutoModelForSequenceClassification = cast(Any, None)
    AutoTokenizer = cast(Any, None)

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore[import-untyped]

from ..logging_config import get_logger
from ..sources.news import GoogleNewsSource
from ..storage import PortfolioStorage

logger = get_logger(__name__)

MARKET_TICKER = "__MARKET__"
DEFAULT_TTL_HOURS = 6
DEFAULT_MAX_ARTICLES = 10


class SentimentScore(BaseModel):
    """Normalized sentiment score for a headline."""

    score: float = Field(
        ..., description="Normalized score between -1.0 (negative) and +1.0 (positive)"
    )
    label: Literal["positive", "neutral", "negative"]
    confidence: float = Field(..., description="Model confidence between 0.0 and 1.0")
    model: str = Field(..., description="Sentiment model identifier (e.g., finbert, vader)")
    probabilities: dict[str, float] = Field(default_factory=dict)


class NewsArticle(BaseModel):
    """Processed and scored news article."""

    ticker: str
    headline: str
    url: str | None = None
    summary: str | None = None
    source: str | None = None
    author: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    fetched_at: datetime
    sentiment: SentimentScore
    content_hash: str
    raw: dict[str, Any] = Field(default_factory=dict)


class NewsSummary(BaseModel):
    """Aggregated sentiment summary for a set of articles."""

    ticker: str
    score: float | None
    score_change: float | None
    positive_count: int
    neutral_count: int
    negative_count: int
    article_count: int
    latest_published_at: datetime | None
    top_positive: NewsArticle | None = None
    top_negative: NewsArticle | None = None
    model_breakdown: dict[str, int] = Field(default_factory=dict)


class NewsBundle(BaseModel):
    """Bundle of articles with aggregated summary."""

    ticker: str
    summary: NewsSummary
    articles: list[NewsArticle]


class FinBertUnavailableError(RuntimeError):
    """Raised when FinBERT cannot be loaded or executed."""


class FinBertSentimentAnalyzer:
    """Sentiment analyzer powered by the ProsusAI/finbert model."""

    DEFAULT_MODEL_NAME = "ProsusAI/finbert"

    def __init__(self, model_name: str | None = None, device: str | None = None) -> None:
        self.model_name = model_name or self.DEFAULT_MODEL_NAME
        self.device = device or "cpu"
        self._tokenizer: Any | None = None
        self._model: Any | None = None
        self._lock = threading.Lock()

    def _ensure_model(self) -> None:
        if self._model is not None and self._tokenizer is not None:
            return

        if AutoTokenizer is None or AutoModelForSequenceClassification is None or torch is None:
            raise FinBertUnavailableError("transformers/torch not available")

        with self._lock:
            if self._model is not None and self._tokenizer is not None:
                return

            logger.info(
                "Loading FinBERT sentiment model", model_name=self.model_name, device=self.device
            )
            try:
                self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
                self._model.to(self.device)
                self._model.eval()
            except Exception as exc:  # pragma: no cover - heavy dependency handling
                logger.error("Failed to load FinBERT model", error=str(exc))
                raise FinBertUnavailableError(str(exc)) from exc

    def is_available(self) -> bool:
        try:
            self._ensure_model()
            return True
        except FinBertUnavailableError:
            return False

    def score_batch(self, texts: Sequence[str]) -> list[SentimentScore]:
        if not texts:
            return []

        self._ensure_model()
        assert self._tokenizer is not None  # For mypy
        assert self._model is not None

        encoded = self._tokenizer(
            list(texts),
            padding=True,
            truncation=True,
            max_length=128,
            return_tensors="pt",
        )
        encoded = {k: v.to(self.device) for k, v in encoded.items()}

        with torch.no_grad():
            outputs = self._model(**encoded)
            logits = outputs.logits
            probabilities = torch.softmax(logits, dim=-1)

        id2label = cast(
            dict[int, str],
            getattr(self._model.config, "id2label", {0: "positive", 1: "negative", 2: "neutral"}),
        )
        results: list[SentimentScore] = []

        for idx in range(probabilities.shape[0]):
            probs = probabilities[idx].detach().cpu().tolist()
            prob_map: dict[str, float] = {
                id2label.get(i, f"LABEL_{i}").lower(): float(p) for i, p in enumerate(probs)
            }
            positive = prob_map.get("positive", 0.0)
            negative = prob_map.get("negative", 0.0)
            neutral = prob_map.get("neutral", 0.0)

            label_key = max(prob_map, key=lambda lbl: prob_map[lbl])
            if label_key not in {"positive", "neutral", "negative"}:
                label_key = "neutral"
            label = cast(Literal["positive", "neutral", "negative"], label_key)
            confidence = float(max(prob_map.values()))
            score = float(positive - negative)

            results.append(
                SentimentScore(
                    score=max(-1.0, min(1.0, score)),
                    label=label,
                    confidence=confidence,
                    model="finbert",
                    probabilities={"positive": positive, "negative": negative, "neutral": neutral},
                )
            )

        return results


class VaderSentimentAnalyzer:
    """Fallback VADER sentiment analyzer."""

    def __init__(self) -> None:
        self._analyzer = SentimentIntensityAnalyzer()

    @staticmethod
    def _label_from_score(score: float) -> Literal["positive", "neutral", "negative"]:
        if score >= 0.2:
            return "positive"
        if score <= -0.2:
            return "negative"
        return "neutral"

    def score_batch(self, texts: Sequence[str]) -> list[SentimentScore]:
        results: list[SentimentScore] = []
        for text in texts:
            compound = float(self._analyzer.polarity_scores(text)["compound"])
            label = self._label_from_score(compound)
            confidence = float(min(1.0, abs(compound)))
            results.append(
                SentimentScore(
                    score=max(-1.0, min(1.0, compound)),
                    label=label,
                    confidence=confidence,
                    model="vader",
                    probabilities={"compound": compound},
                )
            )
        return results


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    with suppress(Exception):
        parsed = cast(datetime, date_parser.parse(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    return None


def _hash_content(ticker: str, headline: str, source: str | None) -> str:
    base = f"{ticker}::{headline.strip()}::{source or ''}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _compose_text(entry: dict[str, Any]) -> str:
    headline = entry.get("title") or entry.get("headline") or ""
    summary = entry.get("summary") or entry.get("description") or ""
    combined = f"{headline.strip()}. {summary.strip()}" if summary else headline.strip()
    return combined or "No headline available."


@dataclass(frozen=True)
class CachedArticles:
    """Cached article payload with staleness metadata."""

    articles: list[NewsArticle]
    fetched_at: datetime | None

    def is_stale(self, ttl: timedelta, now: datetime) -> bool:
        if not self.fetched_at:
            return True
        return self.fetched_at < now - ttl


class NewsService:
    """Unified service for fetching, scoring, caching, and aggregating news."""

    def __init__(
        self,
        storage: PortfolioStorage,
        *,
        ttl: timedelta | None = None,
        news_source: GoogleNewsSource | None = None,
        finbert_analyzer: FinBertSentimentAnalyzer | None = None,
        fallback_analyzer: VaderSentimentAnalyzer | None = None,
    ) -> None:
        self.storage = storage
        self.ttl = ttl or timedelta(hours=DEFAULT_TTL_HOURS)
        self.news_source = news_source or GoogleNewsSource()
        self.finbert_analyzer = finbert_analyzer or FinBertSentimentAnalyzer()
        self.fallback_analyzer = fallback_analyzer or VaderSentimentAnalyzer()

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def get_market_news(
        self, *, max_articles: int = DEFAULT_MAX_ARTICLES, force_refresh: bool = False
    ) -> NewsBundle:
        """Get market-level news bundle."""
        return self._get_bundle(
            ticker=MARKET_TICKER,
            query="stock market",
            max_articles=max_articles,
            force_refresh=force_refresh,
        )

    def get_symbol_news(
        self,
        symbol: str,
        *,
        max_articles: int = DEFAULT_MAX_ARTICLES,
        force_refresh: bool = False,
    ) -> NewsBundle:
        """Get news bundle for a specific ticker symbol."""
        query = f"{symbol} stock"
        return self._get_bundle(
            ticker=symbol.upper(),
            query=query,
            max_articles=max_articles,
            force_refresh=force_refresh,
        )

    def get_watchlist_news(
        self,
        symbols: Iterable[str],
        *,
        max_articles: int = DEFAULT_MAX_ARTICLES,
        force_refresh: bool = False,
    ) -> dict[str, NewsBundle]:
        """Get news bundles for a collection of symbols."""
        bundles: dict[str, NewsBundle] = {}
        for symbol in symbols:
            bundles[symbol.upper()] = self.get_symbol_news(
                symbol,
                max_articles=max_articles,
                force_refresh=force_refresh,
            )
        return bundles

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_bundle(
        self,
        *,
        ticker: str,
        query: str,
        max_articles: int,
        force_refresh: bool,
    ) -> NewsBundle:
        now = datetime.now(UTC)
        cached = self._load_cached_articles(ticker, limit=max_articles)
        is_stale = cached.is_stale(self.ttl, now)

        if force_refresh or is_stale:
            try:
                self._refresh_cache(ticker=ticker, query=query, max_articles=max_articles)
            except Exception as exc:  # pragma: no cover - network/API failure
                logger.warning(
                    "news_refresh_failed",
                    ticker=ticker,
                    error=str(exc),
                )

            # Reload after refresh attempt (fall back to previous cache if failure)
            cached = self._load_cached_articles(ticker, limit=max_articles)

        recent_articles = self._select_recent_articles(cached.articles, now)
        previous_window_articles = self._load_articles_in_window(
            ticker=ticker,
            start=now - (self.ttl * 2),
            end=now - self.ttl,
            limit=max_articles,
        )

        summary = self._build_summary(
            ticker=ticker,
            articles=recent_articles,
            previous_articles=previous_window_articles,
            as_of=now,
        )

        return NewsBundle(ticker=ticker, summary=summary, articles=recent_articles)

    def _select_recent_articles(
        self, articles: Sequence[NewsArticle], now: datetime
    ) -> list[NewsArticle]:
        """Filter articles to TTL window and limit duplicates by hash."""
        recent: list[NewsArticle] = []
        seen_hashes: set[str] = set()
        earliest = now - self.ttl

        for article in sorted(
            articles, key=lambda a: (a.fetched_at, a.published_at or a.fetched_at), reverse=True
        ):
            if article.content_hash in seen_hashes:
                continue

            reference_dt = article.published_at or article.fetched_at
            if reference_dt < earliest:
                continue

            recent.append(article)
            seen_hashes.add(article.content_hash)

        return recent

    # ----------------------- Database operations ----------------------- #
    def _load_cached_articles(self, ticker: str, limit: int) -> CachedArticles:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    ticker,
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
                    updated_at
                FROM news_cache
                WHERE ticker = %s
                ORDER BY fetched_at DESC, published_at DESC NULLS LAST
                LIMIT %s
                """,
                [ticker, limit],
            ).fetchall()

        articles = [self._row_to_article(row) for row in rows]
        latest_fetched_at = max((article.fetched_at for article in articles), default=None)
        return CachedArticles(articles=articles, fetched_at=latest_fetched_at)

    def _load_articles_in_window(
        self,
        *,
        ticker: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[NewsArticle]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    ticker,
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
                    updated_at
                FROM news_cache
                WHERE ticker = %s
                  AND fetched_at >= %s
                  AND fetched_at < %s
                ORDER BY fetched_at DESC, published_at DESC NULLS LAST
                LIMIT %s
                """,
                [ticker, start, end, limit],
            ).fetchall()

        return [self._row_to_article(row) for row in rows]

    def _row_to_article(self, row: Sequence[Any]) -> NewsArticle:
        (
            ticker,
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
        ) = row

        published_dt = published_at.astimezone(UTC) if isinstance(published_at, datetime) else None
        fetched_dt = (
            fetched_at.astimezone(UTC) if isinstance(fetched_at, datetime) else datetime.now(UTC)
        )

        raw_dict = {}
        if raw_payload:
            if isinstance(raw_payload, dict):
                raw_dict = raw_payload
            else:
                with suppress(Exception):
                    raw_dict = json.loads(raw_payload)

        return NewsArticle(
            ticker=ticker,
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
        )

    def _score_entries(
        self,
        *,
        ticker: str,
        entries: Sequence[dict[str, Any]],
        now: datetime,
    ) -> list[NewsArticle]:
        if not entries:
            return []

        texts = [_compose_text(entry) for entry in entries]
        analyzer_used = "finbert"

        try:
            sentiments = self.finbert_analyzer.score_batch(texts)
        except FinBertUnavailableError:
            logger.warning("FinBERT unavailable, falling back to VADER", ticker=ticker)
            sentiments = self.fallback_analyzer.score_batch(texts)
            analyzer_used = "vader"
        except Exception as exc:  # pragma: no cover - inference failure
            logger.error(
                "FinBERT scoring failed; falling back to VADER", error=str(exc), ticker=ticker
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
            article_payload = {
                "raw": entry,
                "sentiment_probabilities": sentiment.probabilities,
                "sentiment_model": sentiment.model,
            }

            articles.append(
                NewsArticle(
                    ticker=ticker,
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
                )
            )

        if analyzer_used != "finbert":
            logger.info(
                "news_sentiment_fallback_used",
                ticker=ticker,
                analyzer=analyzer_used,
                articles=len(articles),
            )

        return articles

    def _article_to_db_row(self, article: NewsArticle) -> dict[str, Any]:
        payload = article.raw
        if "sentiment_probabilities" not in payload:
            payload["sentiment_probabilities"] = article.sentiment.probabilities
        payload.setdefault("sentiment_model", article.sentiment.model)

        return {
            "ticker": article.ticker,
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
        }

    def _refresh_cache(self, *, ticker: str, query: str, max_articles: int) -> None:
        logger.info("Refreshing news cache", ticker=ticker, query=query, max_articles=max_articles)
        raw_entries = self.news_source.fetch_headlines(query, max_articles)
        if not raw_entries:
            logger.info("No headlines returned from source", ticker=ticker)
            return

        now = datetime.now(UTC)
        articles = self._score_entries(ticker=ticker, entries=raw_entries, now=now)
        rows_to_insert = [self._article_to_db_row(article) for article in articles]

        if not rows_to_insert:
            return

        with self.storage.connection() as conn:
            for row in rows_to_insert:
                conn.execute(
                    """
                    INSERT INTO news_cache (
                        ticker,
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
                        updated_at
                    ) VALUES (
                        %(ticker)s,
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
                        %(updated_at)s
                    )
                    ON CONFLICT (ticker, content_hash) DO UPDATE SET
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
                        updated_at = EXCLUDED.updated_at
                    """,
                    row,
                )
            conn.commit()

        logger.info(
            "news_cache_refreshed",
            ticker=ticker,
            articles=len(rows_to_insert),
        )

    def get_custom_news(
        self,
        query: str,
        *,
        max_articles: int = DEFAULT_MAX_ARTICLES,
    ) -> NewsBundle:
        """Fetch and score news for an arbitrary query without caching results."""
        raw_entries = self.news_source.fetch_headlines(query, max_articles)
        now = datetime.now(UTC)
        articles = self._score_entries(ticker=query, entries=raw_entries, now=now)
        summary = self._build_summary(
            ticker=query,
            articles=articles,
            previous_articles=[],
            as_of=now,
        )
        return NewsBundle(ticker=query, summary=summary, articles=articles)

    # ----------------------- Aggregation helpers ----------------------- #
    def _build_summary(
        self,
        *,
        ticker: str,
        articles: Sequence[NewsArticle],
        previous_articles: Sequence[NewsArticle],
        as_of: datetime,
    ) -> NewsSummary:
        if not articles:
            return NewsSummary(
                ticker=ticker,
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

        ttl_hours = max(self.ttl.total_seconds() / 3600.0, 0.1)
        for article in articles:
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

        previous_score = self._compute_previous_score(previous_articles, as_of)
        score_change = None
        if aggregated_score is not None and previous_score is not None:
            score_change = aggregated_score - previous_score

        top_positive = max(articles, key=lambda a: a.sentiment.score, default=None)
        top_negative = min(articles, key=lambda a: a.sentiment.score, default=None)

        return NewsSummary(
            ticker=ticker,
            score=aggregated_score,
            score_change=score_change,
            positive_count=counts["positive"],
            neutral_count=counts["neutral"],
            negative_count=counts["negative"],
            article_count=len(articles),
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
        self, articles: Sequence[NewsArticle], as_of: datetime
    ) -> float | None:
        if not articles:
            return None

        weights = []
        weighted_scores = []
        ttl_hours = max(self.ttl.total_seconds() / 3600.0, 0.1)
        for article in articles:
            reference_dt = article.published_at or article.fetched_at
            hours_since = max(0.0, (as_of - reference_dt).total_seconds() / 3600.0)
            weight = math.exp(-hours_since / (ttl_hours * 2))
            weight = max(weight, 0.1)
            weights.append(weight)
            weighted_scores.append(article.sentiment.score * weight)

        return sum(weighted_scores) / sum(weights) if weights else None
