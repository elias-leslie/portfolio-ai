"""Unified news fetching, caching, and sentiment scoring."""

from __future__ import annotations

import os
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta
from typing import Any

from ..logging_config import get_logger
from ..ml.article_quality_classifier import ArticleQualityClassifier
from ..sources.base import DATASET_NEWS, BaseSource, DatasetRequest
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..storage import PortfolioStorage
from .news_ai_features import NewsAIFeatures
from .news_cache import NewsCacheManager
from .news_cache_refresh import (
    ARTICLE_OVERFETCH_CAP,
    ARTICLE_OVERFETCH_MULTIPLIER,
    DEFAULT_MAX_ARTICLES,
    DEFAULT_TTL_HOURS,
    NewsCacheRefresher,
    ensure_credentials_loaded,
)
from .news_constants import MARKET_SYMBOL
from .news_health_metrics import NewsHealthMetrics
from .news_models import NewsBundle, NewsSummary
from .news_processing import FinBertUnavailableError, NewsProcessor
from .news_quality_scoring import NewsQualityScorer
from .news_sentiment import (
    FINBERT_INSTALL_HINT,
    FinBertSentimentAnalyzer,
    VaderSentimentAnalyzer,
    get_finbert_analyzer,
)
from .news_vendor_manager import NewsVendorManager

logger = get_logger(__name__)

MAX_PARALLEL_SYMBOLS = 5


def _empty_news_bundle(symbol: str) -> NewsBundle:
    """Build an empty news bundle with the expected API shape."""
    return NewsBundle(
        symbol=symbol,
        summary=NewsSummary(
            symbol=symbol, score=None, score_change=None,
            positive_count=0, negative_count=0, neutral_count=0,
            article_count=0, latest_published_at=None,
        ),
        articles=[],
    )


def _parse_max_articles_row(row: Any) -> int | None:
    """Return a validated positive int from a DB row, or None."""
    raw = row[0] if isinstance(row, (list, tuple)) else getattr(row, "news_max_articles", None)
    if raw is None:
        return None
    try:
        v = int(raw)
        return v if v > 0 else None
    except (TypeError, ValueError):
        logger.debug("news_max_articles_parse_failed", raw_value=str(raw))
        return None


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
        vendor_sources: list[BaseSource] | None = None,
        auto_load_credentials: bool = True,
        force_credential_reload: bool = False,
    ) -> None:
        if auto_load_credentials:
            ensure_credentials_loaded(force=force_credential_reload)

        self.storage = storage
        self.ttl = ttl or timedelta(hours=DEFAULT_TTL_HOURS)
        self.finbert_analyzer = finbert_analyzer or get_finbert_analyzer()
        self.fallback_analyzer = fallback_analyzer or VaderSentimentAnalyzer()
        self.lookback_hours = max(1, int(self.ttl.total_seconds() // 3600))
        self.selection_overfetch = max(1, selection_overfetch)
        self.max_articles = DEFAULT_MAX_ARTICLES

        self.cache_manager = NewsCacheManager(storage)
        self.vendor_manager = NewsVendorManager(
            storage, vendor_sources=vendor_sources, multi_source_fetcher=multi_source_fetcher
        )
        self.processor = NewsProcessor(
            finbert_analyzer=self.finbert_analyzer, fallback_analyzer=self.fallback_analyzer
        )
        self.quality_scorer = NewsQualityScorer()
        self.ai_features = NewsAIFeatures()
        self.cache_refresher = NewsCacheRefresher(
            storage=storage, cache_manager=self.cache_manager,
            vendor_manager=self.vendor_manager, processor=self.processor,
            quality_scorer=self.quality_scorer, ai_features=self.ai_features,
            ttl=self.ttl, selection_overfetch=self.selection_overfetch,
        )
        self.health_metrics = NewsHealthMetrics(
            storage=storage, vendor_manager=self.vendor_manager, ttl=self.ttl,
        )
        self.multi_source_fetcher = self.vendor_manager.multi_source_fetcher
        self.vendor_sources = self.vendor_manager.vendor_sources
        self.quality_model: ArticleQualityClassifier | None = self.quality_scorer.quality_model

    def set_ttl_hours(self, hours: int) -> None:
        """Update the active TTL/lookback window (in hours)."""
        validated = max(1, hours)
        self.ttl = timedelta(hours=validated)
        self.lookback_hours = validated
        self.cache_refresher.set_ttl_hours(hours)

    def refresh_ttl_from_preferences(self) -> int:
        """Reload TTL configuration from user preferences."""
        hours = self.cache_refresher.refresh_ttl_from_preferences()
        self.ttl = timedelta(hours=hours)
        self.lookback_hours = hours
        return hours

    def refresh_max_articles_from_preferences(self) -> int:
        """Reload max-article preference from user settings."""
        max_articles = DEFAULT_MAX_ARTICLES
        with self.storage.connection() as conn:
            row = conn.execute(
                "SELECT news_max_articles FROM user_preferences ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if row:
            parsed = _parse_max_articles_row(row)
            if parsed is not None:
                max_articles = parsed
        self.max_articles = max(1, min(max_articles, ARTICLE_OVERFETCH_CAP))
        return self.max_articles

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    def get_news_intelligence(
        self,
        symbol: str | None = None,
        *,
        max_articles: int = DEFAULT_MAX_ARTICLES,
        force_refresh: bool = False,
    ) -> NewsBundle:
        """Get unified news intelligence bundle for market or specific symbol.

        symbol=None → market-level news; symbol="AAPL" → symbol-specific news.
        """
        if symbol is None:
            return self._get_bundle(
                symbol=MARKET_SYMBOL, query="stock market",
                max_articles=max_articles, force_refresh=force_refresh,
            )
        return self._get_bundle(
            symbol=symbol.upper(), query=f"{symbol} stock",
            max_articles=max_articles, force_refresh=force_refresh,
        )

    def get_watchlist_news(
        self,
        symbols: Iterable[str],
        *,
        max_articles: int = DEFAULT_MAX_ARTICLES,
        force_refresh: bool = False,
    ) -> dict[str, NewsBundle]:
        """Get news bundles for a collection of symbols (parallel I/O)."""
        symbol_list = [s.upper() for s in symbols]
        if not symbol_list:
            return {}

        def fetch_single(sym: str) -> tuple[str, NewsBundle]:
            return sym, self.get_news_intelligence(sym, max_articles=max_articles, force_refresh=force_refresh)

        bundles: dict[str, NewsBundle] = {}
        max_workers = min(MAX_PARALLEL_SYMBOLS, len(symbol_list))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_single, sym): sym for sym in symbol_list}
            for future in as_completed(futures):
                try:
                    sym, bundle = future.result()
                    bundles[sym] = bundle
                except Exception as exc:
                    logger.warning("parallel_news_fetch_failed", symbol=futures[future], error=str(exc))
        return bundles

    def get_custom_news(self, query: str, *, max_articles: int = DEFAULT_MAX_ARTICLES) -> NewsBundle:
        """Fetch and score news for an arbitrary query without caching results."""
        if os.getenv("PYTEST_RUNNING"):
            return _empty_news_bundle(query)
        now = datetime.now(UTC)
        if self.multi_source_fetcher is None:
            logger.warning("get_custom_news_no_sources", query=query)
            return _empty_news_bundle(query)
        request = DatasetRequest(
            dataset=DATASET_NEWS, profile=None, symbols=[query],
            start=now - self.ttl, end=now, timezone="UTC",
        )
        dataframe, _ = self.multi_source_fetcher.fetch_with_fallback(request, verbose=False)
        raw_entries = [] if (dataframe is None or len(dataframe) == 0) else dataframe.to_dicts()
        articles = self.processor.score_entries(symbol=query, entries=raw_entries, now=now)
        summary = self.processor.build_summary(
            symbol=query, articles=articles, previous_articles=[], as_of=now, ttl=self.ttl,
        )
        return NewsBundle(symbol=query, summary=summary, articles=articles)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_bundle(self, *, symbol: str, query: str, max_articles: int, force_refresh: bool) -> NewsBundle:
        now = datetime.now(UTC)
        summary_limit = max(200, max_articles)

        cached = self.cache_manager.load_cached_articles(symbol, limit=summary_limit)
        if force_refresh or cached.is_stale(self.ttl, now):
            self._try_refresh_cache(symbol=symbol, query=query, max_articles=max_articles, now=now)
            cached = self.cache_manager.load_cached_articles(symbol, limit=summary_limit)

        all_recent = self.processor.select_recent_articles(
            cached.articles, now, max_articles=summary_limit, ttl=self.ttl,
        )
        previous = self.cache_manager.load_articles_in_window(
            symbol=symbol, start=now - (self.ttl * 2), end=now - self.ttl, limit=summary_limit,
        )
        summary = self.processor.build_summary(
            symbol=symbol, articles=all_recent, previous_articles=previous, as_of=now, ttl=self.ttl,
        )
        return NewsBundle(symbol=symbol, summary=summary, articles=all_recent[:max_articles])

    def _try_refresh_cache(self, *, symbol: str, query: str, max_articles: int, now: datetime) -> None:
        """Attempt a cache refresh, logging on failure."""
        try:
            self.cache_refresher.refresh_cache(symbol=symbol, query=query, max_articles=max_articles, now=now)
        except Exception as exc:  # pragma: no cover - network/API failure
            logger.warning("news_refresh_failed", symbol=symbol, error=str(exc))

    def get_health(self) -> dict[str, Any]:
        """Return lightweight health metrics for the news pipeline."""
        try:
            finbert_available = self.finbert_analyzer.is_available()
        except FinBertUnavailableError:
            finbert_available = False

        now = datetime.now(UTC)
        window_start = now - timedelta(hours=24)
        fm = self.health_metrics.get_fallback_metrics(window_start)
        mx = self.health_metrics.get_article_mix_metrics(now)
        vendor_health = self.health_metrics.build_vendor_health(
            self.health_metrics.get_vendor_stats(window_start), now
        )
        to_iso = self.health_metrics.to_iso
        avg_ms, p95_ms = fm["avg_latency_ms"], fm["p95_latency_ms"]
        market_last_refreshed_at = self.cache_refresher.latest_fetched_at(market=True)
        watchlist_last_refreshed_at = self.cache_refresher.latest_fetched_at(market=False)
        pipeline_health = self.health_metrics.build_pipeline_health(
            now=now,
            ttl=self.ttl,
            headlines_24h=int(fm["total_count"]),
            fallback_headlines_24h=int(fm["fallback_count"]),
            market_last_refreshed_at=market_last_refreshed_at,
            watchlist_last_refreshed_at=watchlist_last_refreshed_at,
            primary_sentiment_available=finbert_available,
        )

        return {
            "status": pipeline_health["status"],
            "message": pipeline_health["message"],
            "finbert_available": finbert_available,
            "finbert_install_hint": None if finbert_available else FINBERT_INSTALL_HINT,
            "market_last_refreshed_at": to_iso(market_last_refreshed_at),
            "watchlist_last_refreshed_at": to_iso(watchlist_last_refreshed_at),
            "latest_refreshed_at": to_iso(pipeline_health["latest_refreshed_at"]),
            "latest_refresh_age_hours": pipeline_health["latest_refresh_age_hours"],
            "fallback_headlines_24h": fm["fallback_count"],
            "headlines_24h": fm["total_count"],
            "cache_ttl_hours": round(self.ttl.total_seconds() / 3600.0, 2),
            "lookback_window_hours": self.lookback_hours,
            "fallback_rate_24h": round(fm["fallback_rate"], 4),
            "fallback_avg_latency_ms_24h": round(avg_ms, 2) if avg_ms is not None else None,
            "fallback_p95_latency_ms_24h": round(p95_ms, 2) if p95_ms is not None else None,
            "fallback_last_event_at": to_iso(fm["last_fallback_at"]) if fm["last_fallback_at"] else None,
            "article_mix": {
                "total_pre_dedupe": mx["total_pre"],
                "total_post_dedupe": mx["total_post"],
                "dedupe_ratio": round(mx["total_post"] / mx["total_pre"], 4) if mx["total_pre"] else None,
                "per_vendor_pre_dedupe": {k: int(v) for k, v in mx["vendor_pre"].items()},
                "per_vendor_post_dedupe": {k: int(v) for k, v in mx["vendor_post"].items()},
                "last_updated_at": to_iso(mx["last_timestamp"]),
            },
            "vendors": vendor_health,
        }
