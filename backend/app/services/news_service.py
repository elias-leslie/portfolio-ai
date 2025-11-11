"""Unified news fetching, caching, and sentiment scoring."""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from importlib import import_module
from typing import Any, Literal, cast

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer  # type: ignore[import-untyped]

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

from ..logging_config import get_logger
from ..sources.base import DATASET_NEWS, BaseSource, DatasetRequest
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..storage import PortfolioStorage
from ..storage.credential_loader import load_credentials_from_database
from .news_ai_features import NewsAIFeatures
from .news_cache import NewsCacheManager
from .news_models import NewsBundle, NewsSummary, SentimentScore
from .news_processing import FinBertUnavailableError, NewsProcessor
from .news_vendor_manager import NewsVendorManager

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


class NewsService:
    """Unified service for fetching, scoring, caching, and aggregating news."""

    def __init__(
        self,
        storage: PortfolioStorage,
        *,
        ttl: timedelta | None = None,
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
        self.finbert_analyzer = finbert_analyzer or FinBertSentimentAnalyzer()
        self.fallback_analyzer = fallback_analyzer or VaderSentimentAnalyzer()
        self.lookback_hours = max(1, int(self.ttl.total_seconds() // 3600))
        self.selection_overfetch = max(1, selection_overfetch)
        self.max_articles = DEFAULT_MAX_ARTICLES

        # Initialize component managers
        self.cache_manager = NewsCacheManager(storage)
        self.vendor_manager = NewsVendorManager(
            storage, vendor_sources=vendor_sources, multi_source_fetcher=multi_source_fetcher
        )
        self.processor = NewsProcessor(
            finbert_analyzer=self.finbert_analyzer, fallback_analyzer=self.fallback_analyzer
        )
        self.ai_features = NewsAIFeatures()

        # Expose multi_source_fetcher for compatibility
        self.multi_source_fetcher = self.vendor_manager.multi_source_fetcher
        self.vendor_sources = self.vendor_manager.vendor_sources

    def set_ttl_hours(self, hours: int) -> None:
        """Update the active TTL/lookback window (in hours)."""
        validated = max(1, hours)
        self.ttl = timedelta(hours=validated)
        self.lookback_hours = validated

    def refresh_ttl_from_preferences(self) -> int:
        """Reload TTL configuration from user preferences."""
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

        # Clamp to avoid unbounded fetches
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

    def get_news_intelligence(
        self,
        ticker: str | None = None,
        *,
        max_articles: int = DEFAULT_MAX_ARTICLES,
        force_refresh: bool = False,
    ) -> NewsBundle:
        """Get unified news intelligence bundle for market or specific ticker.

        This method unifies market-level and ticker-specific news fetching
        into a single interface, supporting both use cases:
        - Market news: ticker=None returns broad market news
        - Ticker news: ticker="AAPL" returns symbol-specific news

        Args:
            ticker: Optional ticker symbol. If None, returns market-level news.
                   If provided, returns ticker-specific news.
            max_articles: Maximum number of articles to return
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            NewsBundle containing summary statistics and scored articles

        Examples:
            >>> service = NewsService()
            >>> market_news = service.get_news_intelligence(None)
            >>> aapl_news = service.get_news_intelligence("AAPL")
        """
        if ticker is None:
            # Market-level news
            return self._get_bundle(
                ticker=MARKET_TICKER,
                query="stock market",
                max_articles=max_articles,
                force_refresh=force_refresh,
            )
        # Ticker-specific news
        query = f"{ticker} stock"
        return self._get_bundle(
            ticker=ticker.upper(),
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

    def get_custom_news(
        self,
        query: str,
        *,
        max_articles: int = DEFAULT_MAX_ARTICLES,
    ) -> NewsBundle:
        """Fetch and score news for an arbitrary query without caching results."""
        now = datetime.now(UTC)

        if self.multi_source_fetcher is None:
            logger.warning("get_custom_news_no_sources", query=query)
            return NewsBundle(
                ticker=query,
                summary=NewsSummary(
                    ticker=query,
                    score=None,
                    score_change=None,
                    positive_count=0,
                    negative_count=0,
                    neutral_count=0,
                    article_count=0,
                    latest_published_at=None,
                ),
                articles=[],
            )

        # Fetch from all sources
        request = DatasetRequest(
            dataset=DATASET_NEWS,
            profile=None,
            tickers=[query],
            start=now - self.ttl,
            end=now,
            timezone="UTC",
        )
        dataframe, _ = self.multi_source_fetcher.fetch_with_fallback(request, verbose=False)

        if dataframe is None or len(dataframe) == 0:
            raw_entries = []
        else:
            raw_entries = dataframe.to_dicts()

        articles = self.processor.score_entries(ticker=query, entries=raw_entries, now=now)
        summary = self.processor.build_summary(
            ticker=query,
            articles=articles,
            previous_articles=[],
            as_of=now,
            ttl=self.ttl,
        )
        return NewsBundle(ticker=query, summary=summary, articles=articles)

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

        cached = self.cache_manager.load_cached_articles(ticker, limit=overfetch_limit)
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

            # Reload after refresh attempt
            cached = self.cache_manager.load_cached_articles(ticker, limit=overfetch_limit)

        recent_articles = self.processor.select_recent_articles(
            cached.articles,
            now,
            max_articles=max_articles,
            ttl=self.ttl,
        )
        previous_window_articles = self.cache_manager.load_articles_in_window(
            ticker=ticker,
            start=now - (self.ttl * 2),
            end=now - self.ttl,
            limit=max_articles,
        )

        summary = self.processor.build_summary(
            ticker=ticker,
            articles=recent_articles,
            previous_articles=previous_window_articles,
            as_of=now,
            ttl=self.ttl,
        )

        return NewsBundle(ticker=ticker, summary=summary, articles=recent_articles)

    def _refresh_cache(self, *, ticker: str, query: str, max_articles: int) -> None:
        """Refresh cache with new articles from vendors."""
        logger.info("Refreshing news cache", ticker=ticker, query=query, max_articles=max_articles)

        now = datetime.now(UTC)
        fetch_limit = max(
            max_articles, min(max_articles * self.selection_overfetch, ARTICLE_OVERFETCH_CAP)
        )

        vendor_entries, vendor_metadata = self.vendor_manager.fetch_vendor_entries(
            ticker=ticker,
            ttl=self.ttl,
            now=now,
            max_entries=fetch_limit,
        )
        self.vendor_manager.apply_vendor_metadata(vendor_metadata, now)

        pre_counts: dict[str, int] = {
            str(name): int(count) for name, count in (vendor_metadata.get("counts") or {}).items()
        }

        combined_entries, post_counts = self.processor.merge_entries(
            ticker=ticker,
            vendor_entries=vendor_entries,
            max_entries=fetch_limit,
        )

        if not combined_entries:
            logger.info("No headlines returned from sources", ticker=ticker)
            return

        self.vendor_manager.update_recent_mix_summary(
            ticker,
            timestamp=now,
            pre_counts=pre_counts,
            post_counts=post_counts,
            combined_entries=combined_entries,
        )

        articles = self.processor.score_entries(ticker=ticker, entries=combined_entries, now=now)

        # Apply AI features
        articles = self.ai_features.apply_story_clustering(articles)
        articles = self.ai_features.apply_plain_language_translation(
            articles, watchlist_tickers=None
        )

        self.cache_manager.save_articles(articles)

        logger.info(
            "news_cache_refreshed",
            ticker=ticker,
            articles=len(articles),
            vendor_counts=vendor_metadata.get("counts", {}),
        )

    def _latest_fetched_at(self, *, market: bool) -> datetime | None:
        """Get latest fetch timestamp for health reporting."""
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

    @staticmethod
    def _to_iso(dt: datetime | None) -> str | None:
        """Convert datetime to ISO 8601 string with Z suffix."""
        if not dt:
            return None
        return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _get_fallback_metrics(self, window_start: datetime) -> dict[str, Any]:
        """Get sentiment fallback metrics for health check.

        Args:
            window_start: Start of time window (now - 24 hours)

        Returns:
            Dict with fallback counts, rates, latencies
        """
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

        return {
            "fallback_count": fallback_count,
            "total_count": total_count,
            "fallback_rate": fallback_rate,
            "avg_latency_ms": avg_latency_ms,
            "p95_latency_ms": p95_latency_ms,
            "last_fallback_at": last_fallback_at,
        }

    def _get_article_mix_metrics(self, now: datetime) -> dict[str, Any]:
        """Get article mix metrics from vendor manager.

        Args:
            now: Current timestamp

        Returns:
            Dict with pre/post dedupe counts by vendor
        """
        recent_mix_summary = self.vendor_manager.get_recent_mix_summary()
        mix_total_pre = 0
        mix_total_post = 0
        mix_vendor_pre: Counter[str] = Counter()
        mix_vendor_post: Counter[str] = Counter()
        last_mix_timestamp: datetime | None = None

        pruning_threshold = now - (self.ttl * 2)
        for stats in list(recent_mix_summary.values()):
            timestamp = stats.get("timestamp")
            if isinstance(timestamp, datetime) and timestamp < pruning_threshold:
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

        return {
            "total_pre": mix_total_pre,
            "total_post": mix_total_post,
            "vendor_pre": mix_vendor_pre,
            "vendor_post": mix_vendor_post,
            "last_timestamp": last_mix_timestamp,
        }

    def _get_vendor_stats(self, window_start: datetime) -> dict[str, dict[str, Any]]:
        """Get per-vendor article stats from database.

        Args:
            window_start: Start of time window

        Returns:
            Dict mapping vendor name to stats
        """
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

        return vendor_stats

    def _build_vendor_health(
        self,
        vendor_stats: dict[str, dict[str, Any]],
        now: datetime,
    ) -> dict[str, Any]:
        """Build vendor health status from config, runtime, and stats.

        Args:
            vendor_stats: Per-vendor article stats
            now: Current timestamp

        Returns:
            Dict mapping vendor name to health status
        """
        vendor_config = self.vendor_manager.get_vendor_config()
        vendor_runtime = self.vendor_manager.get_vendor_runtime()
        vendor_health: dict[str, Any] = {}

        for vendor_name, config in vendor_config.items():
            runtime = vendor_runtime.get(
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
                "last_attempt_at": self._to_iso(runtime.get("last_attempt_at")),
                "last_success_at": self._to_iso(runtime.get("last_success_at")),
                "last_error_at": self._to_iso(runtime.get("last_error_at")),
                "last_error": runtime.get("last_error"),
                "articles_last_fetch": int(runtime.get("articles_last_fetch", 0)),
                "articles_last_fetch_post_dedupe": int(runtime.get("articles_last_fetch_post", 0)),
                "articles_last_24h": int(stats.get("articles_last_24h", 0)),
                "last_article_at": self._to_iso(last_article_at_dt),
                "notes": config.get("notes"),
                "reason": config.get("reason"),
            }

        return vendor_health

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

        # Gather metrics from various sources
        fallback_metrics = self._get_fallback_metrics(window_start)
        mix_metrics = self._get_article_mix_metrics(now)
        vendor_stats = self._get_vendor_stats(window_start)
        vendor_health = self._build_vendor_health(vendor_stats, now)

        return {
            "finbert_available": finbert_available,
            "market_last_refreshed_at": self._to_iso(market_last),
            "watchlist_last_refreshed_at": self._to_iso(watchlist_last),
            "fallback_headlines_24h": fallback_metrics["fallback_count"],
            "headlines_24h": fallback_metrics["total_count"],
            "cache_ttl_hours": round(self.ttl.total_seconds() / 3600.0, 2),
            "lookback_window_hours": self.lookback_hours,
            "fallback_rate_24h": round(fallback_metrics["fallback_rate"], 4),
            "fallback_avg_latency_ms_24h": round(fallback_metrics["avg_latency_ms"], 2)
            if fallback_metrics["avg_latency_ms"] is not None
            else None,
            "fallback_p95_latency_ms_24h": round(fallback_metrics["p95_latency_ms"], 2)
            if fallback_metrics["p95_latency_ms"] is not None
            else None,
            "fallback_last_event_at": self._to_iso(fallback_metrics["last_fallback_at"])
            if fallback_metrics["last_fallback_at"]
            else None,
            "article_mix": {
                "total_pre_dedupe": mix_metrics["total_pre"],
                "total_post_dedupe": mix_metrics["total_post"],
                "dedupe_ratio": round(mix_metrics["total_post"] / mix_metrics["total_pre"], 4)
                if mix_metrics["total_pre"]
                else None,
                "per_vendor_pre_dedupe": {k: int(v) for k, v in mix_metrics["vendor_pre"].items()},
                "per_vendor_post_dedupe": {
                    k: int(v) for k, v in mix_metrics["vendor_post"].items()
                },
                "last_updated_at": self._to_iso(mix_metrics["last_timestamp"]),
            },
            "vendors": vendor_health,
        }
