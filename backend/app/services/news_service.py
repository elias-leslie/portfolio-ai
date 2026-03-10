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
from .news_sentiment import FinBertSentimentAnalyzer, VaderSentimentAnalyzer, get_finbert_analyzer
from .news_vendor_manager import NewsVendorManager

logger = get_logger(__name__)

# Max parallel symbol fetches to avoid vendor API rate limits
MAX_PARALLEL_SYMBOLS = 5


def _empty_news_bundle(symbol: str) -> NewsBundle:
    """Build an empty news bundle with the expected API shape."""
    return NewsBundle(
        symbol=symbol,
        summary=NewsSummary(
            symbol=symbol,
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

        # Initialize component managers
        self.cache_manager = NewsCacheManager(storage)
        self.vendor_manager = NewsVendorManager(
            storage, vendor_sources=vendor_sources, multi_source_fetcher=multi_source_fetcher
        )
        self.processor = NewsProcessor(
            finbert_analyzer=self.finbert_analyzer, fallback_analyzer=self.fallback_analyzer
        )
        self.quality_scorer = NewsQualityScorer()
        self.ai_features = NewsAIFeatures()

        # Initialize cache refresher
        self.cache_refresher = NewsCacheRefresher(
            storage=storage,
            cache_manager=self.cache_manager,
            vendor_manager=self.vendor_manager,
            processor=self.processor,
            quality_scorer=self.quality_scorer,
            ai_features=self.ai_features,
            ttl=self.ttl,
            selection_overfetch=self.selection_overfetch,
        )

        # Initialize health metrics collector
        self.health_metrics = NewsHealthMetrics(
            storage=storage,
            vendor_manager=self.vendor_manager,
            ttl=self.ttl,
        )

        # Expose multi_source_fetcher for compatibility
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
    def get_news_intelligence(
        self,
        symbol: str | None = None,
        *,
        max_articles: int = DEFAULT_MAX_ARTICLES,
        force_refresh: bool = False,
    ) -> NewsBundle:
        """Get unified news intelligence bundle for market or specific symbol.

        This method unifies market-level and symbol-specific news fetching
        into a single interface, supporting both use cases:
        - Market news: symbol=None returns broad market news
        - Symbol news: symbol="AAPL" returns symbol-specific news

        Args:
            symbol: Optional symbol. If None, returns market-level news.
                   If provided, returns symbol-specific news.
            max_articles: Maximum number of articles to return
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            NewsBundle containing summary statistics and scored articles

        Examples:
            >>> service = NewsService()
            >>> market_news = service.get_news_intelligence(None)
            >>> aapl_news = service.get_news_intelligence("AAPL")
        """
        if symbol is None:
            # Market-level news
            return self._get_bundle(
                symbol=MARKET_SYMBOL,
                query="stock market",
                max_articles=max_articles,
                force_refresh=force_refresh,
            )
        # Symbol-specific news
        query = f"{symbol} stock"
        return self._get_bundle(
            symbol=symbol.upper(),
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
        """Get news bundles for a collection of symbols.

        Uses ThreadPoolExecutor to fetch symbols in parallel, significantly
        reducing wall time for large watchlists. HTTP I/O overlaps between
        threads while CPU-bound work (FinBERT) naturally serializes via GIL.
        """
        symbol_list = [s.upper() for s in symbols]
        if not symbol_list:
            return {}

        bundles: dict[str, NewsBundle] = {}

        def fetch_single(symbol: str) -> tuple[str, NewsBundle]:
            return symbol, self.get_news_intelligence(
                symbol,
                max_articles=max_articles,
                force_refresh=force_refresh,
            )

        # Use thread pool for parallel I/O (HTTP fetches overlap)
        # Limit workers to avoid vendor rate limits
        max_workers = min(MAX_PARALLEL_SYMBOLS, len(symbol_list))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_single, sym): sym for sym in symbol_list}
            for future in as_completed(futures):
                try:
                    symbol, bundle = future.result()
                    bundles[symbol] = bundle
                except Exception as exc:
                    symbol = futures[future]
                    logger.warning(
                        "parallel_news_fetch_failed",
                        symbol=symbol,
                        error=str(exc),
                    )

        return bundles

    def get_custom_news(
        self,
        query: str,
        *,
        max_articles: int = DEFAULT_MAX_ARTICLES,
    ) -> NewsBundle:
        """Fetch and score news for an arbitrary query without caching results."""
        if os.getenv("PYTEST_RUNNING"):
            return _empty_news_bundle(query)

        now = datetime.now(UTC)

        if self.multi_source_fetcher is None:
            logger.warning("get_custom_news_no_sources", query=query)
            return _empty_news_bundle(query)

        # Fetch from all sources
        request = DatasetRequest(
            dataset=DATASET_NEWS,
            profile=None,
            symbols=[query],
            start=now - self.ttl,
            end=now,
            timezone="UTC",
        )
        dataframe, _ = self.multi_source_fetcher.fetch_with_fallback(request, verbose=False)

        if dataframe is None or len(dataframe) == 0:
            raw_entries = []
        else:
            raw_entries = dataframe.to_dicts()

        articles = self.processor.score_entries(symbol=query, entries=raw_entries, now=now)
        summary = self.processor.build_summary(
            symbol=query,
            articles=articles,
            previous_articles=[],
            as_of=now,
            ttl=self.ttl,
        )
        return NewsBundle(symbol=query, summary=summary, articles=articles)

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _get_bundle(
        self,
        *,
        symbol: str,
        query: str,
        max_articles: int,
        force_refresh: bool,
    ) -> NewsBundle:
        now = datetime.now(UTC)
        # Always load enough articles to calculate accurate summary
        # Use a high limit for summary calculation, independent of display limit
        summary_limit = max(200, max_articles)  # At least 200 for accurate sentiment

        cached = self.cache_manager.load_cached_articles(symbol, limit=summary_limit)
        is_stale = cached.is_stale(self.ttl, now)

        if force_refresh or is_stale:
            try:
                self.cache_refresher.refresh_cache(
                    symbol=symbol, query=query, max_articles=max_articles, now=now
                )
            except Exception as exc:  # pragma: no cover - network/API failure
                logger.warning(
                    "news_refresh_failed",
                    symbol=symbol,
                    error=str(exc),
                )

            # Reload after refresh attempt
            cached = self.cache_manager.load_cached_articles(symbol, limit=summary_limit)

        # Get ALL articles within TTL for summary calculation
        all_recent_articles = self.processor.select_recent_articles(
            cached.articles,
            now,
            max_articles=summary_limit,  # Use high limit for summary
            ttl=self.ttl,
        )

        # Get limited articles for display
        display_articles = all_recent_articles[:max_articles]

        previous_window_articles = self.cache_manager.load_articles_in_window(
            symbol=symbol,
            start=now - (self.ttl * 2),
            end=now - self.ttl,
            limit=summary_limit,
        )

        # Build summary from ALL articles, not just display articles
        summary = self.processor.build_summary(
            symbol=symbol,
            articles=all_recent_articles,
            previous_articles=previous_window_articles,
            as_of=now,
            ttl=self.ttl,
        )

        return NewsBundle(symbol=symbol, summary=summary, articles=display_articles)

    def get_health(self) -> dict[str, Any]:
        """Return lightweight health metrics for the news pipeline."""
        try:
            finbert_available = self.finbert_analyzer.is_available()
        except FinBertUnavailableError:
            finbert_available = False

        market_last = self.cache_refresher.latest_fetched_at(market=True)
        watchlist_last = self.cache_refresher.latest_fetched_at(market=False)

        now = datetime.now(UTC)
        window_start = now - timedelta(hours=24)

        # Gather metrics from health metrics collector
        fallback_metrics = self.health_metrics.get_fallback_metrics(window_start)
        mix_metrics = self.health_metrics.get_article_mix_metrics(now)
        vendor_stats = self.health_metrics.get_vendor_stats(window_start)
        vendor_health = self.health_metrics.build_vendor_health(vendor_stats, now)

        return {
            "finbert_available": finbert_available,
            "finbert_install_hint": None if finbert_available else 'pip install -e ".[dev,ml]"',
            "market_last_refreshed_at": self.health_metrics.to_iso(market_last),
            "watchlist_last_refreshed_at": self.health_metrics.to_iso(watchlist_last),
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
            "fallback_last_event_at": self.health_metrics.to_iso(
                fallback_metrics["last_fallback_at"]
            )
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
                "last_updated_at": self.health_metrics.to_iso(mix_metrics["last_timestamp"]),
            },
            "vendors": vendor_health,
        }
