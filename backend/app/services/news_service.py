"""Unified news fetching, caching, and sentiment scoring."""

from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from collections import Counter, deque
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

try:
    from .story_clusterer import NewsArticle as ClustererArticle
    from .story_clusterer import StoryClusterer
except Exception:  # pragma: no cover - handled via availability checks
    ClustererArticle = cast(Any, None)  # type: ignore[misc]
    StoryClusterer = cast(Any, None)  # type: ignore[misc]

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore[import-untyped]

from ..logging_config import get_logger
from ..sources.base import DATASET_NEWS, BaseSource, DatasetRequest
from ..sources.finnhub_source import FinnhubSource
from ..sources.fmp_source import FMPSource
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..sources.news import GoogleNewsSource
from ..sources.polygon_source import PolygonSource
from ..sources.rss_source import (
    CNBCRssSource,
    FinancialTimesRssSource,
    FortuneRssSource,
    InvestingRssSource,
    MarketWatchRssSource,
    NasdaqRssSource,
    SeekingAlphaRssSource,
)
from ..sources.sec_edgar_source import SECEdgarSource
from ..sources.yfinance_source import YFinanceSource
from ..storage import PortfolioStorage
from ..storage.credential_loader import load_credentials_from_database

logger = get_logger(__name__)

_CREDENTIALS_LOADED = False
_CREDENTIALS_LOCK = threading.Lock()


def _ensure_credentials_loaded(*, force: bool = False) -> None:
    """Load credentials from database into environment once per process."""
    global _CREDENTIALS_LOADED  # noqa: PLW0603

    if not force and _CREDENTIALS_LOADED:
        return

    with _CREDENTIALS_LOCK:
        if not force and _CREDENTIALS_LOADED:
            return
        try:
            load_credentials_from_database()
            _CREDENTIALS_LOADED = True
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning(
                "news_credentials_load_failed",
                error=str(exc),
            )


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
    # SEC filing metadata
    filing_type: str | None = None
    is_material_event: bool = False
    plain_language_headline: str | None = None
    # Story clustering metadata
    story_id: str | None = None
    is_primary_article: bool = False
    coverage_count: int = 1


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
        auto_load_credentials: bool = True,
        force_credential_reload: bool = False,
    ) -> None:
        if auto_load_credentials:
            _ensure_credentials_loaded(force=force_credential_reload)

        self.storage = storage
        self.ttl = ttl or timedelta(hours=DEFAULT_TTL_HOURS)
        self.news_source = news_source or GoogleNewsSource()
        self.finbert_analyzer = finbert_analyzer or FinBertSentimentAnalyzer()
        self.fallback_analyzer = fallback_analyzer or VaderSentimentAnalyzer()
        self.lookback_hours = max(1, int(self.ttl.total_seconds() // 3600))
        self.selection_overfetch = max(1, selection_overfetch)
        self.max_articles = DEFAULT_MAX_ARTICLES

        self._vendor_config: dict[str, dict[str, Any]] = {}
        self._vendor_runtime: dict[str, dict[str, Any]] = {}
        self._recent_mix_summary: dict[str, dict[str, Any]] = {}

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
                "articles_last_fetch_post": 0,
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

        # SEC EDGAR (free, highest priority)
        sec_edgar_flag = self._env_flag("SEC_EDGAR_ENABLED", default=True)
        sec_edgar_enabled = bool(sec_edgar_flag)
        sec_edgar_reason: str | None = None
        sec_edgar_notes = "SEC EDGAR filings (8-K, 10-Q, 10-K, Form 4) - highest quality free source."
        if not sec_edgar_flag:
            sec_edgar_reason = "disabled_by_flag"
        if sec_edgar_enabled:
            try:
                sources.append(SECEdgarSource(self.storage))
            except Exception as exc:
                sec_edgar_reason = f"init_failed: {exc}"
                sec_edgar_enabled = False
                logger.warning("sec_edgar_source_init_failed", error=str(exc))
        self._register_vendor(
            "sec_edgar",
            configured=True,
            enabled=sec_edgar_enabled,
            notes=sec_edgar_notes,
            reason=sec_edgar_reason,
        )

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

        # YFinance (free ticker feed)
        yfinance_flag = self._env_flag("YFINANCE_NEWS_ENABLED", default=True)
        yfinance_enabled = bool(yfinance_flag)
        yfinance_reason: str | None = None
        yfinance_notes = "Yahoo Finance ticker feed via yfinance; no API key required."
        if yfinance_enabled:
            try:
                sources.append(YFinanceSource())
            except Exception as exc:
                yfinance_reason = f"init_failed: {exc}"
                yfinance_enabled = False
                logger.warning("yfinance_news_source_init_failed", error=str(exc))
        self._register_vendor(
            "yfinance",
            configured=True,
            enabled=yfinance_enabled,
            notes=yfinance_notes,
            reason=yfinance_reason,
        )

        rss_configs: list[tuple[str, type[BaseSource], str, str]] = [
            ("cnbc_rss", CNBCRssSource, "CNBC finance/earnings RSS feed", "CNBC_RSS_ENABLED"),
            (
                "marketwatch_rss",
                MarketWatchRssSource,
                "MarketWatch Top Stories RSS feed",
                "MARKETWATCH_RSS_ENABLED",
            ),
            (
                "nasdaq_rss",
                NasdaqRssSource,
                "Nasdaq original & ticker RSS feeds",
                "NASDAQ_RSS_ENABLED",
            ),
            ("fortune_rss", FortuneRssSource, "Fortune business RSS feed", "FORTUNE_RSS_ENABLED"),
            (
                "investing_rss",
                InvestingRssSource,
                "Investing.com market overview RSS feed",
                "INVESTING_RSS_ENABLED",
            ),
            (
                "ft_rss",
                FinancialTimesRssSource,
                "Financial Times global markets RSS feed",
                "FT_RSS_ENABLED",
            ),
            (
                "seeking_alpha_rss",
                SeekingAlphaRssSource,
                "Seeking Alpha combined RSS feed",
                "SEEKING_ALPHA_RSS_ENABLED",
            ),
        ]

        for vendor_name, source_cls, notes, env_var in rss_configs:
            flag = self._env_flag(env_var, default=True)
            enabled = bool(flag)
            reason: str | None = None
            instance: BaseSource | None = None

            if enabled:
                try:
                    instance = source_cls()
                    sources.append(instance)
                except Exception as exc:  # pragma: no cover - initialization issues logged
                    enabled = False
                    reason = f"init_failed: {exc}"
                    logger.warning("%s_init_failed", vendor_name, error=str(exc))

            self._register_vendor(
                vendor_name,
                configured=True,
                enabled=enabled,
                notes=notes,
                reason=reason,
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

    def refresh_max_articles_from_preferences(self) -> int:
        """Reload max-article preference from user settings."""
        max_articles = DEFAULT_MAX_ARTICLES
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT news_max_articles
                FROM user_preferences
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ).fetchone()

        if row:
            raw_value = row[0] if isinstance(row, (list, tuple)) else None
            if raw_value is None and hasattr(row, "news_max_articles"):
                raw_value = row.news_max_articles
            if raw_value is not None:
                try:
                    candidate = int(raw_value)
                    if candidate > 0:
                        max_articles = candidate
                except (TypeError, ValueError):
                    pass

        # Clamp to avoid unbounded fetches (match selection cap)
        max_articles = max(1, min(max_articles, ARTICLE_OVERFETCH_CAP))
        self.max_articles = max_articles
        return self.max_articles

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
                "articles_last_fetch_post": 0,
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

        vendor_counts: Counter[str] = Counter()
        vendor_buckets: dict[str, deque[dict[str, Any]]] = {}
        priority_lookup = {
            source.name: index for index, source in enumerate(self.multi_source_fetcher.sources)
        }

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
            bucket = vendor_buckets.setdefault(vendor_name, deque())
            bucket.append(normalized)

        metadata["counts"] = dict(vendor_counts)

        if not vendor_buckets or max_entries <= 0:
            return [], metadata

        vendor_order = sorted(
            vendor_buckets.keys(),
            key=lambda name: priority_lookup.get(name, len(priority_lookup) + 1),
        )

        selected: list[dict[str, Any]] = []
        while vendor_order and len(selected) < max_entries:
            progressed = False
            for vendor_name in list(vendor_order):
                queue = vendor_buckets.get(vendor_name)
                if not queue:
                    vendor_order.remove(vendor_name)
                    continue

                selected.append(queue.popleft())
                progressed = True

                if not queue:
                    vendor_order.remove(vendor_name)

                if len(selected) >= max_entries:
                    break

            if not progressed:
                break

        return selected, metadata

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
    ) -> tuple[list[dict[str, Any]], dict[str, int]]:
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

        limited = merged[:max_entries]
        post_counts: Counter[str] = Counter()
        for entry in limited:
            vendor = str(entry.get("vendor") or "unknown").strip() or "unknown"
            post_counts[vendor] += 1

        return limited, {vendor: int(count) for vendor, count in post_counts.items()}

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
                    updated_at,
                    filing_type,
                    is_material_event,
                    plain_language_headline
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
                    updated_at,
                    filing_type,
                    is_material_event,
                    plain_language_headline
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
            filing_type,
            is_material_event,
            plain_language_headline,
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
            filing_type=filing_type,
            is_material_event=bool(is_material_event),
            plain_language_headline=plain_language_headline,
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

    def _apply_story_clustering(self, articles: list[NewsArticle]) -> list[NewsArticle]:
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
                    ticker=article.ticker,
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
            "filing_type": article.filing_type,
            "is_material_event": article.is_material_event,
            "plain_language_headline": article.plain_language_headline,
            "story_id": article.story_id,
            "is_primary_article": article.is_primary_article,
            "coverage_count": article.coverage_count,
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

        pre_counts: dict[str, int] = {
            str(name): int(count) for name, count in (vendor_metadata.get("counts") or {}).items()
        }
        if google_entries:
            pre_counts["google_news"] = pre_counts.get("google_news", 0) + len(google_entries)

        combined_entries, post_counts = self._merge_entries(
            ticker=ticker,
            vendor_entries=vendor_entries,
            google_entries=google_entries,
            max_entries=fetch_limit,
        )

        if not combined_entries:
            logger.info("No headlines returned from sources", ticker=ticker)
            return

        for vendor_name, post_count in post_counts.items():
            runtime = self._vendor_runtime.setdefault(
                vendor_name,
                {
                    "last_attempt_at": None,
                    "last_success_at": None,
                    "last_error_at": None,
                    "last_error": None,
                    "articles_last_fetch": 0,
                    "articles_last_fetch_post": 0,
                },
            )
            runtime["articles_last_fetch_post"] = int(post_count)

        self._recent_mix_summary[ticker.upper()] = {
            "timestamp": now,
            "total_pre": int(sum(pre_counts.values())),
            "total_post": len(combined_entries),
            "per_vendor_pre": pre_counts,
            "per_vendor_post": post_counts,
        }

        articles = self._score_entries(ticker=ticker, entries=combined_entries, now=now)

        # Apply story clustering to group articles by semantic similarity
        articles = self._apply_story_clustering(articles)

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
                        updated_at,
                        filing_type,
                        is_material_event,
                        plain_language_headline,
                        story_id,
                        is_primary_article,
                        coverage_count
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
                        %(updated_at)s,
                        %(filing_type)s,
                        %(is_material_event)s,
                        %(plain_language_headline)s,
                        %(story_id)s,
                        %(is_primary_article)s,
                        %(coverage_count)s
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
                        updated_at = EXCLUDED.updated_at,
                        story_id = EXCLUDED.story_id,
                        is_primary_article = EXCLUDED.is_primary_article,
                        coverage_count = EXCLUDED.coverage_count
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

        mix_total_pre = 0
        mix_total_post = 0
        mix_vendor_pre: Counter[str] = Counter()
        mix_vendor_post: Counter[str] = Counter()
        last_mix_timestamp: datetime | None = None

        pruning_threshold = now - (self.ttl * 2)
        for ticker_key, stats in list(self._recent_mix_summary.items()):
            timestamp = stats.get("timestamp")
            if isinstance(timestamp, datetime) and timestamp < pruning_threshold:
                self._recent_mix_summary.pop(ticker_key, None)
                continue

            if isinstance(timestamp, datetime) and (
                not last_mix_timestamp or timestamp > last_mix_timestamp
            ):
                last_mix_timestamp = timestamp

            mix_total_pre += int(stats.get("total_pre", 0) or 0)
            mix_total_post += int(stats.get("total_post", 0) or 0)

            for vendor_name, count in (stats.get("per_vendor_pre") or {}).items():
                mix_vendor_pre[vendor_name] += int(count or 0)
            for vendor_name, count in (stats.get("per_vendor_post") or {}).items():
                mix_vendor_post[vendor_name] += int(count or 0)

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
                "articles_last_fetch_post_dedupe": int(runtime.get("articles_last_fetch_post", 0)),
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
            "article_mix": {
                "total_pre_dedupe": mix_total_pre,
                "total_post_dedupe": mix_total_post,
                "dedupe_ratio": round(mix_total_post / mix_total_pre, 4) if mix_total_pre else None,
                "per_vendor_pre_dedupe": {k: int(v) for k, v in mix_vendor_pre.items()},
                "per_vendor_post_dedupe": {k: int(v) for k, v in mix_vendor_post.items()},
                "last_updated_at": _iso(last_mix_timestamp) if last_mix_timestamp else None,
            },
            "vendors": vendor_health,
        }
