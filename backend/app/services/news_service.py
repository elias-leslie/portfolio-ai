"""Unified news fetching, caching, and sentiment scoring."""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from collections import Counter
from collections.abc import Iterable, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import import_module
from time import perf_counter
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
from ..sources.base import DATASET_NEWS, BaseSource, DatasetRequest
from ..sources.finnhub_source import FinnhubSource
from ..sources.fmp_source import FMPSource
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..sources.news import GoogleNewsSource
from ..sources.polygon_source import PolygonSource
from ..storage import PortfolioStorage

logger = get_logger(__name__)

MARKET_TICKER = "__MARKET__"
DEFAULT_TTL_HOURS = 6
DEFAULT_MAX_ARTICLES = 10
ARTICLE_OVERFETCH_MULTIPLIER = 3
ARTICLE_OVERFETCH_CAP = 45
ALLOWED_LOOKBACK_HOURS = {6, 12, 24, 48}


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
    vendor: str | None = None


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
        selection_overfetch: int = ARTICLE_OVERFETCH_MULTIPLIER,
        multi_source_fetcher: MultiSourceFetcher | None = None,
        vendor_sources: Sequence[BaseSource] | None = None,
    ) -> None:
        self.storage = storage
        self.ttl = ttl or timedelta(hours=DEFAULT_TTL_HOURS)
        self.news_source = news_source or GoogleNewsSource()
        self.finbert_analyzer = finbert_analyzer or FinBertSentimentAnalyzer()
        self.fallback_analyzer = fallback_analyzer or VaderSentimentAnalyzer()
        self.lookback_hours = max(1, int(self.ttl.total_seconds() // 3600))
        self.selection_overfetch = max(1, selection_overfetch)

        self._vendor_config: dict[str, dict[str, Any]] = {}
        self._vendor_runtime: dict[str, dict[str, Any]] = {}

        # Always register Google News fallback vendor
        self._register_vendor(
            "google_news",
            configured=True,
            enabled=True,
            notes="Google News RSS fallback feed",
            reason=None,
        )

        self.vendor_sources = self._prepare_vendor_sources(vendor_sources)
        self.multi_source_fetcher = multi_source_fetcher

        if self.multi_source_fetcher is not None:
            self.vendor_sources = list(self.multi_source_fetcher.sources)
            for source in self.vendor_sources:
                self._register_vendor(
                    source.name,
                    configured=True,
                    enabled=True,
                    notes=None,
                    reason=None,
                )
        elif self.vendor_sources:
            self.multi_source_fetcher = MultiSourceFetcher(self.vendor_sources, storage)
        else:
            self.multi_source_fetcher = None

    @staticmethod
    def _env_flag(name: str, default: bool = False) -> bool:
        """Parse boolean-like environment variables."""
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on", "y"}

    def _register_vendor(
        self,
        name: str,
        *,
        configured: bool,
        enabled: bool,
        notes: str | None,
        reason: str | None,
    ) -> None:
        """Ensure vendor metadata/runtime tracking entries exist."""
        existing = self._vendor_config.get(name, {})
        existing.update(
            {
                "configured": bool(configured),
                "enabled": bool(enabled),
            }
        )
        if notes is not None:
            existing["notes"] = notes
        existing.setdefault("notes", notes)
        if reason is not None or "reason" not in existing:
            existing["reason"] = reason
        self._vendor_config[name] = existing

        self._vendor_runtime.setdefault(
            name,
            {
                "last_attempt_at": None,
                "last_success_at": None,
                "last_error_at": None,
                "last_error": None,
                "articles_last_fetch": 0,
            },
        )

    def _prepare_vendor_sources(
        self, vendor_sources: Sequence[BaseSource] | None
    ) -> list[BaseSource]:
        """Initialise vendor sources either from overrides or environment configuration."""
        sources: list[BaseSource] = []

        if vendor_sources is not None:
            for source in vendor_sources:
                sources.append(source)
                self._register_vendor(
                    source.name, configured=True, enabled=True, notes=None, reason=None
                )
            return sources

        # Polygon
        polygon_key = os.getenv("POLYGON_API_KEY")
        polygon_flag = self._env_flag("POLYGON_NEWS_ENABLED", default=True)
        polygon_configured = bool(polygon_key)
        polygon_enabled = bool(polygon_configured and polygon_flag)
        polygon_reason: str | None = None
        if not polygon_configured:
            polygon_reason = "missing_api_key"
        elif not polygon_flag:
            polygon_reason = "disabled_by_flag"
        if polygon_enabled:
            try:
                sources.append(PolygonSource())
            except Exception as exc:
                polygon_reason = f"init_failed: {exc}"
                polygon_enabled = False
                logger.warning("polygon_news_source_init_failed", error=str(exc))
        self._register_vendor(
            "polygon",
            configured=polygon_configured,
            enabled=polygon_enabled,
            notes=None,
            reason=polygon_reason,
        )

        # Finnhub
        finnhub_key = os.getenv("FINNHUB_API_KEY")
        finnhub_flag = self._env_flag("FINNHUB_NEWS_ENABLED", default=True)
        finnhub_configured = bool(finnhub_key)
        finnhub_enabled = bool(finnhub_configured and finnhub_flag)
        finnhub_reason: str | None = None
        if not finnhub_configured:
            finnhub_reason = "missing_api_key"
        elif not finnhub_flag:
            finnhub_reason = "disabled_by_flag"
        if finnhub_enabled:
            try:
                sources.append(FinnhubSource())
            except Exception as exc:
                finnhub_reason = f"init_failed: {exc}"
                finnhub_enabled = False
                logger.warning("finnhub_news_source_init_failed", error=str(exc))
        self._register_vendor(
            "finnhub",
            configured=finnhub_configured,
            enabled=finnhub_enabled,
            notes=None,
            reason=finnhub_reason,
        )

        # FMP (news requires paid tier; default disabled)
        fmp_key = os.getenv("FMP_API_KEY")
        fmp_flag = self._env_flag("FMP_NEWS_ENABLED", default=False)
        fmp_configured = bool(fmp_key)
        fmp_enabled = bool(fmp_configured and fmp_flag)
        fmp_reason: str | None = None
        fmp_notes = "FMP news endpoints require paid tier; enable via FMP_NEWS_ENABLED=1."
        if not fmp_configured:
            fmp_reason = "missing_api_key"
        elif not fmp_flag:
            fmp_reason = "disabled_by_flag"
        if fmp_enabled:
            try:
                sources.append(FMPSource())
            except Exception as exc:
                fmp_reason = f"init_failed: {exc}"
                fmp_enabled = False
                logger.warning("fmp_news_source_init_failed", error=str(exc))
        self._register_vendor(
            "fmp",
            configured=fmp_configured,
            enabled=fmp_enabled,
            notes=fmp_notes,
            reason=fmp_reason,
        )

        return [source for source in sources if source.is_enabled()]

    def set_ttl_hours(self, hours: int) -> None:
        """Update the active TTL/lookback window (in hours)."""
        validated = max(1, hours)
        self.ttl = timedelta(hours=validated)
        self.lookback_hours = validated

    def refresh_ttl_from_preferences(self) -> int:
        """Reload TTL configuration from user preferences.

        Returns:
            The active lookback window in hours after applying preferences.
        """
        hours = DEFAULT_TTL_HOURS
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT news_lookback_hours
                FROM user_preferences
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ).fetchone()

        if row:
            raw_value = row[0] if isinstance(row, (list, tuple)) else None
            if raw_value is None and hasattr(row, "news_lookback_hours"):
                raw_value = row.news_lookback_hours
            if raw_value is not None:
                try:
                    candidate = int(raw_value)
                    if candidate in ALLOWED_LOOKBACK_HOURS or candidate > 0:
                        hours = candidate
                except (TypeError, ValueError):
                    pass

        self.set_ttl_hours(hours)
        return self.lookback_hours

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
        initial_limit = max(max_articles * self.selection_overfetch, max_articles)
        if max_articles <= ARTICLE_OVERFETCH_CAP:
            overfetch_limit = min(initial_limit, ARTICLE_OVERFETCH_CAP)
        else:
            overfetch_limit = max_articles
        cached = self._load_cached_articles(ticker, limit=overfetch_limit)
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
            cached = self._load_cached_articles(ticker, limit=overfetch_limit)

        recent_articles = self._select_recent_articles(
            cached.articles,
            now,
            max_articles=max_articles,
        )
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

    # ------------------------------------------------------------------ #
    # Vendor aggregation helpers
    # ------------------------------------------------------------------ #
    def _update_vendor_runtime(
        self,
        vendor: str,
        *,
        attempt_at: datetime,
        article_count: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        self._register_vendor(
            vendor,
            configured=self._vendor_config.get(vendor, {}).get("configured", True),
            enabled=self._vendor_config.get(vendor, {}).get("enabled", True),
            notes=self._vendor_config.get(vendor, {}).get("notes"),
            reason=self._vendor_config.get(vendor, {}).get("reason"),
        )
        runtime = self._vendor_runtime.setdefault(
            vendor,
            {
                "last_attempt_at": None,
                "last_success_at": None,
                "last_error_at": None,
                "last_error": None,
                "articles_last_fetch": 0,
            },
        )
        runtime["last_attempt_at"] = attempt_at
        runtime["articles_last_fetch"] = int(article_count)
        if success:
            runtime["last_success_at"] = attempt_at
            runtime["last_error"] = None
            runtime["last_error_at"] = None
        elif error:
            runtime["last_error"] = error
            runtime["last_error_at"] = attempt_at

    def _apply_vendor_metadata(self, metadata: dict[str, Any], attempt_at: datetime) -> None:
        if not metadata:
            return

        counts_data = metadata.get("counts") or {}
        if isinstance(counts_data, Counter):
            counts = dict(counts_data)
        else:
            counts = {str(k): int(v) for k, v in counts_data.items()}

        errors = metadata.get("errors") or {}
        if not isinstance(errors, dict):
            errors = {}

        for vendor_name, count in counts.items():
            if not vendor_name:
                continue
            self._update_vendor_runtime(
                vendor_name,
                attempt_at=attempt_at,
                article_count=count,
                success=True,
            )

        for vendor_name, error_messages in errors.items():
            if not vendor_name or vendor_name in counts:
                continue
            error_list = error_messages
            if not isinstance(error_list, list):
                error_list = [str(error_list)]
            error_text = "; ".join(str(message) for message in error_list if message)
            self._update_vendor_runtime(
                vendor_name,
                attempt_at=attempt_at,
                article_count=0,
                success=False,
                error=error_text or None,
            )

    def _normalize_vendor_row(
        self,
        row: dict[str, Any],
        *,
        vendor_name: str,
        default_ticker: str,
    ) -> dict[str, Any]:
        entry = dict(row)
        headline = entry.get("headline") or entry.get("title")
        summary = entry.get("summary") or entry.get("description")
        url = entry.get("url") or entry.get("link") or entry.get("article_url")
        news_source_name = entry.get("news_source_name") or entry.get("publisher")
        if isinstance(news_source_name, dict):
            news_source_name = news_source_name.get("name") or news_source_name.get("title")

        published_value = entry.get("published_at") or entry.get("published")
        published_iso = None
        if isinstance(published_value, datetime):
            published_iso = published_value.astimezone(UTC).isoformat()
        elif isinstance(published_value, str):
            published_iso = published_value
        elif isinstance(published_value, (int, float)):
            published_iso = datetime.fromtimestamp(float(published_value), tz=UTC).isoformat()

        ticker_value = entry.get("ticker") or default_ticker
        if isinstance(ticker_value, str):
            ticker_value = ticker_value.upper()

        vendor_payload = entry.get("raw_payload") or entry.get("vendor_payload")
        if isinstance(vendor_payload, str):
            with suppress(Exception):
                vendor_payload = json.loads(vendor_payload)

        normalized = {
            "headline": headline,
            "summary": summary,
            "description": summary,
            "url": url,
            "link": url,
            "source": news_source_name or vendor_name,
            "news_source_name": news_source_name or vendor_name,
            "author": entry.get("author"),
            "image_url": entry.get("image_url"),
            "published": published_iso,
            "published_at": published_iso,
            "vendor": vendor_name,
            "ticker": ticker_value or default_ticker,
        }
        if vendor_payload is not None:
            normalized["vendor_payload"] = vendor_payload

        return normalized

    def _fetch_vendor_entries(
        self,
        *,
        ticker: str,
        query: str,
        now: datetime,
        max_entries: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        metadata: dict[str, Any] = {"counts": {}, "errors": {}}
        if self.multi_source_fetcher is None:
            return [], metadata

        request = DatasetRequest(
            dataset=DATASET_NEWS,
            profile=None,
            tickers=[ticker],
            start=now - self.ttl,
            end=now,
            timezone="UTC",
        )
        dataframe, errors = self.multi_source_fetcher.fetch_with_fallback(request, verbose=False)
        metadata["errors"] = errors or {}

        if dataframe is None or len(dataframe) == 0:
            metadata["counts"] = {}
            return [], metadata

        entries: list[dict[str, Any]] = []
        vendor_counts: Counter[str] = Counter()

        for row in dataframe.to_dicts():
            vendor_name = str(row.get("source") or "").strip() or "unknown"
            normalized = self._normalize_vendor_row(
                row,
                vendor_name=vendor_name,
                default_ticker=ticker,
            )
            if not normalized.get("headline"):
                continue
            vendor_counts[vendor_name] += 1
            entries.append(normalized)
            if len(entries) >= max_entries:
                break

        metadata["counts"] = dict(vendor_counts)
        return entries, metadata

    def _fetch_google_entries(
        self,
        *,
        query: str,
        limit: int,
        ticker: str,
        now: datetime,
    ) -> list[dict[str, Any]]:
        if limit <= 0:
            return []

        entries = self.news_source.fetch_headlines(query, limit)
        normalized_entries: list[dict[str, Any]] = []
        for entry in entries:
            normalized = dict(entry)
            normalized["vendor"] = "google_news"
            if isinstance(normalized.get("source"), dict):
                source_title = normalized["source"].get("title")
                normalized.setdefault("news_source_name", source_title)
            else:
                normalized.setdefault("news_source_name", normalized.get("source"))
            normalized.setdefault("source", normalized.get("news_source_name") or "Google News")
            normalized.setdefault("ticker", ticker)
            normalized_entries.append(normalized)

        self._update_vendor_runtime(
            "google_news",
            attempt_at=now,
            article_count=len(normalized_entries),
            success=True,
        )
        return normalized_entries

    def _merge_entries(
        self,
        *,
        ticker: str,
        vendor_entries: Sequence[dict[str, Any]],
        google_entries: Sequence[dict[str, Any]],
        max_entries: int,
    ) -> list[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()
        merged: list[dict[str, Any]] = []

        def _iter_source(entries: Sequence[dict[str, Any]]) -> Iterable[dict[str, Any]]:
            for entry in entries:
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
            return ()

        _iter_source(vendor_entries)
        if len(merged) < max_entries:
            _iter_source(google_entries)

        return merged[:max_entries]

    def _select_recent_articles(
        self,
        articles: Sequence[NewsArticle],
        now: datetime,
        *,
        max_articles: int,
    ) -> list[NewsArticle]:
        """Filter articles to TTL window with graceful stale backfill.

        Headlines are sorted by recency and deduplicated on ``content_hash``. Items within
        the TTL window are prioritised. If there are insufficient fresh headlines to reach
        ``max_articles``, the method backfills with the most recent stale entries while
        marking them via ``raw["stale"] = True`` so consumers can indicate degraded
        freshness in the UI.
        """

        fresh: list[NewsArticle] = []
        stale_candidates: list[NewsArticle] = []
        seen_hashes: set[str] = set()
        earliest = now - self.ttl

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

        vendor = raw_dict.get("vendor")
        if vendor is None:
            inner_raw = raw_dict.get("raw")
            if isinstance(inner_raw, dict):
                vendor = inner_raw.get("vendor")

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
            vendor=vendor,
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
                ticker=ticker,
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
                ticker=ticker,
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
            if vendor is None and isinstance(self.news_source, GoogleNewsSource):
                vendor = "google_news"

            article_payload = {
                "raw": entry,
                "sentiment_probabilities": sentiment.probabilities,
                "sentiment_model": sentiment.model,
            }
            if vendor:
                article_payload["vendor"] = vendor

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
                ticker=ticker,
                analyzer=analyzer_used,
                articles=len(articles),
                fallback_rate=round(fallback_rate, 4),
                latency_ms=fallback_details.get("latency_ms"),
                reason=fallback_details.get("reason"),
            )

        return articles

    def _article_to_db_row(self, article: NewsArticle) -> dict[str, Any]:
        payload = article.raw
        if "sentiment_probabilities" not in payload:
            payload["sentiment_probabilities"] = article.sentiment.probabilities
        payload.setdefault("sentiment_model", article.sentiment.model)
        if article.vendor:
            payload.setdefault("vendor", article.vendor)

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

        now = datetime.now(UTC)
        fetch_limit = max(
            max_articles, min(max_articles * self.selection_overfetch, ARTICLE_OVERFETCH_CAP)
        )

        vendor_entries, vendor_metadata = self._fetch_vendor_entries(
            ticker=ticker,
            query=query,
            now=now,
            max_entries=fetch_limit,
        )
        self._apply_vendor_metadata(vendor_metadata, now)

        vendor_count = len(vendor_entries)
        google_limit = max(fetch_limit - vendor_count, 0)
        if google_limit == 0 and vendor_count < max_articles:
            google_limit = max_articles - vendor_count

        google_entries = self._fetch_google_entries(
            query=query,
            limit=google_limit,
            ticker=ticker,
            now=now,
        )

        combined_entries = self._merge_entries(
            ticker=ticker,
            vendor_entries=vendor_entries,
            google_entries=google_entries,
            max_entries=fetch_limit,
        )

        if not combined_entries:
            logger.info("No headlines returned from sources", ticker=ticker)
            return

        articles = self._score_entries(ticker=ticker, entries=combined_entries, now=now)
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
            vendor_counts=vendor_metadata.get("counts", {}),
            google_articles=len(google_entries),
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

        summary_articles = [article for article in articles if not article.raw.get("stale")]
        if not summary_articles:
            summary_articles = list(articles)

        ttl_hours = max(self.ttl.total_seconds() / 3600.0, 0.1)
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

    def _latest_fetched_at(self, *, market: bool) -> datetime | None:
        query = (
            "SELECT MAX(fetched_at) FROM news_cache WHERE ticker = %s"
            if market
            else "SELECT MAX(fetched_at) FROM news_cache WHERE ticker <> %s"
        )
        with self.storage.connection() as conn:
            row = conn.execute(query, [MARKET_TICKER]).fetchone()
        if not row:
            return None
        fetched_at = row[0]
        if fetched_at is None:
            return None
        if not isinstance(fetched_at, datetime):
            return None
        return fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=UTC)

    def get_health(self) -> dict[str, Any]:
        """Return lightweight health metrics for the news pipeline."""
        try:
            finbert_available = self.finbert_analyzer.is_available()
        except FinBertUnavailableError:
            finbert_available = False

        market_last = self._latest_fetched_at(market=True)
        watchlist_last = self._latest_fetched_at(market=False)

        now = datetime.now(UTC)
        window_start = now - timedelta(hours=24)

        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN sentiment_model <> %s THEN 1 ELSE 0 END) AS fallback_count,
                    COUNT(*) AS total_count,
                    AVG(
                        CASE
                            WHEN jsonb_exists(raw_payload, 'sentiment_fallback')
                            THEN (raw_payload->'sentiment_fallback'->>'latency_ms')::DOUBLE PRECISION
                        END
                    ) AS avg_latency_ms,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (
                        ORDER BY (raw_payload->'sentiment_fallback'->>'latency_ms')::DOUBLE PRECISION
                    ) FILTER (WHERE jsonb_exists(raw_payload, 'sentiment_fallback')) AS p95_latency_ms,
                    MAX(fetched_at) FILTER (WHERE jsonb_exists(raw_payload, 'sentiment_fallback')) AS last_fallback_at
                FROM news_cache
                WHERE fetched_at >= %s
                """,
                ["finbert", window_start],
            ).fetchone()

        fallback_count = int(row[0] or 0) if row else 0
        total_count = int(row[1] or 0) if row else 0
        avg_latency_ms = float(row[2]) if row and row[2] is not None else None
        p95_latency_ms = float(row[3]) if row and row[3] is not None else None
        last_fallback_at = row[4] if row else None

        fallback_rate = (fallback_count / total_count) if total_count else 0.0

        with self.storage.connection() as conn:
            vendor_rows = conn.execute(
                """
                SELECT
                    raw_payload->'raw'->>'vendor' AS vendor,
                    COUNT(*) AS article_count,
                    MAX(fetched_at) AS last_article_at
                FROM news_cache
                WHERE fetched_at >= %s
                GROUP BY vendor
                """,
                [window_start],
            ).fetchall()

        vendor_stats: dict[str, dict[str, Any]] = {}
        for vendor_name, article_count, last_article_at in vendor_rows:
            key = (vendor_name or "unknown").strip()
            last_at = last_article_at
            if isinstance(last_at, datetime) and last_at.tzinfo is None:
                last_at = last_at.replace(tzinfo=UTC)
            vendor_stats[key] = {
                "articles_last_24h": int(article_count or 0),
                "last_article_at": last_at,
            }
            if key not in self._vendor_config:
                self._register_vendor(key, configured=True, enabled=True, notes=None, reason=None)

        def _iso(dt: datetime | None) -> str | None:
            if not dt:
                return None
            return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")

        vendor_health: dict[str, Any] = {}
        for vendor_name, config in self._vendor_config.items():
            runtime = self._vendor_runtime.get(
                vendor_name,
                {
                    "last_attempt_at": None,
                    "last_success_at": None,
                    "last_error_at": None,
                    "last_error": None,
                    "articles_last_fetch": 0,
                },
            )
            stats = vendor_stats.get(vendor_name, {})
            last_article_at_dt = stats.get("last_article_at")
            active = False
            if config.get("enabled") and isinstance(last_article_at_dt, datetime):
                active = (now - last_article_at_dt) <= (self.ttl * 2)

            vendor_health[vendor_name] = {
                "configured": bool(config.get("configured")),
                "enabled": bool(config.get("enabled")),
                "active": active,
                "last_attempt_at": _iso(runtime.get("last_attempt_at")),
                "last_success_at": _iso(runtime.get("last_success_at")),
                "last_error_at": _iso(runtime.get("last_error_at")),
                "last_error": runtime.get("last_error"),
                "articles_last_fetch": int(runtime.get("articles_last_fetch", 0)),
                "articles_last_24h": int(stats.get("articles_last_24h", 0)),
                "last_article_at": _iso(last_article_at_dt),
                "notes": config.get("notes"),
                "reason": config.get("reason"),
            }

        return {
            "finbert_available": finbert_available,
            "market_last_refreshed_at": _iso(market_last),
            "watchlist_last_refreshed_at": _iso(watchlist_last),
            "fallback_headlines_24h": fallback_count,
            "headlines_24h": total_count,
            "cache_ttl_hours": round(self.ttl.total_seconds() / 3600.0, 2),
            "lookback_window_hours": self.lookback_hours,
            "fallback_rate_24h": round(fallback_rate, 4),
            "fallback_avg_latency_ms_24h": round(avg_latency_ms, 2)
            if avg_latency_ms is not None
            else None,
            "fallback_p95_latency_ms_24h": round(p95_latency_ms, 2)
            if p95_latency_ms is not None
            else None,
            "fallback_last_event_at": _iso(last_fallback_at) if last_fallback_at else None,
            "vendors": vendor_health,
        }
