"""News vendor source management and aggregation."""

from __future__ import annotations

import json
import os
from collections import Counter, deque
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Any

from ..logging_config import get_logger
from ..sources.base import DATASET_NEWS, BaseSource, DatasetRequest
from ..sources.finnhub_source import FinnhubSource
from ..sources.fmp_source import FMPSource
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..sources.polygon_source import PolygonSource
from ..sources.rss_source import (
    CNBCRssSource,
    FinancialTimesRssSource,
    FortuneRssSource,
    GoogleNewsRssSource,
    InvestingRssSource,
    MarketWatchRssSource,
    NasdaqRssSource,
    SeekingAlphaRssSource,
)
from ..sources.sec_edgar_source import SECEdgarSource
from ..sources.yfinance_source import YFinanceSource
from ..storage import PortfolioStorage

logger = get_logger(__name__)


class NewsVendorManager:
    """Manages news vendor sources and aggregation."""

    def __init__(
        self,
        storage: PortfolioStorage,
        *,
        vendor_sources: Sequence[BaseSource] | None = None,
        multi_source_fetcher: MultiSourceFetcher | None = None,
    ) -> None:
        self.storage = storage
        self._vendor_config: dict[str, dict[str, Any]] = {}
        self._vendor_runtime: dict[str, dict[str, Any]] = {}
        self._recent_mix_summary: dict[str, dict[str, Any]] = {}

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

    def _init_free_vendor(
        self,
        vendor_name: str,
        source_cls: type[BaseSource],
        env_var: str,
        notes: str,
        default_enabled: bool = True,
        *,
        sources: list[BaseSource],
    ) -> None:
        """Initialize a free vendor (no API key required).

        Args:
            vendor_name: Vendor identifier (e.g., 'sec_edgar')
            source_cls: Source class to instantiate
            env_var: Environment variable for enable flag
            notes: Description of vendor
            default_enabled: Default enable state if env var not set
            sources: List to append initialized source to
        """
        flag = self._env_flag(env_var, default=default_enabled)
        enabled = bool(flag)
        reason: str | None = None if flag else "disabled_by_flag"

        if enabled:
            try:
                # Pass storage to SEC EDGAR, YFinance doesn't need it
                if vendor_name == "sec_edgar":
                    sources.append(source_cls(self.storage))  # type: ignore[call-arg]
                else:
                    sources.append(source_cls())
            except Exception as exc:
                reason = f"init_failed: {exc}"
                enabled = False
                logger.warning(f"{vendor_name}_source_init_failed", error=str(exc))

        self._register_vendor(
            vendor_name, configured=True, enabled=enabled, notes=notes, reason=reason
        )

    def _init_api_vendor(
        self,
        vendor_name: str,
        source_cls: type[BaseSource],
        api_key_env: str,
        flag_env: str,
        notes: str | None,
        default_enabled: bool = True,
        *,
        sources: list[BaseSource],
    ) -> None:
        """Initialize a vendor requiring an API key.

        Args:
            vendor_name: Vendor identifier (e.g., 'polygon')
            source_cls: Source class to instantiate
            api_key_env: Environment variable for API key
            flag_env: Environment variable for enable flag
            notes: Description of vendor
            default_enabled: Default enable state if flag not set
            sources: List to append initialized source to
        """
        api_key = os.getenv(api_key_env)
        flag = self._env_flag(flag_env, default=default_enabled)
        configured = bool(api_key)
        enabled = configured and flag

        # Determine reason for disabled state
        reason: str | None = None
        if not configured:
            reason = "missing_api_key"
        elif not flag:
            reason = "disabled_by_flag"

        if enabled:
            try:
                sources.append(source_cls())
            except Exception as exc:
                reason = f"init_failed: {exc}"
                enabled = False
                logger.warning(f"{vendor_name}_news_source_init_failed", error=str(exc))

        self._register_vendor(
            vendor_name, configured=configured, enabled=enabled, notes=notes, reason=reason
        )

    def _init_rss_vendors(self, sources: list[BaseSource]) -> None:
        """Initialize all RSS news vendors.

        Args:
            sources: List to append initialized RSS sources to
        """
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
            (
                "google_news_rss",
                GoogleNewsRssSource,
                "Google News aggregated market & ticker RSS feeds",
                "GOOGLE_NEWS_RSS_ENABLED",
            ),
        ]

        for vendor_name, source_cls, notes, env_var in rss_configs:
            self._init_free_vendor(vendor_name, source_cls, env_var, notes, sources=sources)

    def _prepare_vendor_sources(
        self, vendor_sources: Sequence[BaseSource] | None
    ) -> list[BaseSource]:
        """Initialise vendor sources from overrides or environment configuration."""
        sources: list[BaseSource] = []

        # Handle override sources
        if vendor_sources is not None:
            for source in vendor_sources:
                sources.append(source)
                self._register_vendor(
                    source.name, configured=True, enabled=True, notes=None, reason=None
                )
            return sources

        # Initialize primary news vendors
        self._init_free_vendor(
            "sec_edgar",
            SECEdgarSource,
            "SEC_EDGAR_ENABLED",
            "SEC EDGAR filings (8-K, 10-Q, 10-K, Form 4) - highest quality free source.",
            sources=sources,
        )
        self._init_api_vendor(
            "polygon",
            PolygonSource,
            "POLYGON_API_KEY",
            "POLYGON_NEWS_ENABLED",
            None,
            sources=sources,
        )
        self._init_api_vendor(
            "finnhub",
            FinnhubSource,
            "FINNHUB_API_KEY",
            "FINNHUB_NEWS_ENABLED",
            None,
            sources=sources,
        )
        self._init_api_vendor(
            "fmp",
            FMPSource,
            "FMP_API_KEY",
            "FMP_NEWS_ENABLED",
            "FMP news endpoints require paid tier; enable via FMP_NEWS_ENABLED=1.",
            default_enabled=False,
            sources=sources,
        )
        self._init_free_vendor(
            "yfinance",
            YFinanceSource,
            "YFINANCE_NEWS_ENABLED",
            "Yahoo Finance ticker feed via yfinance; no API key required.",
            sources=sources,
        )

        # Initialize RSS vendors
        self._init_rss_vendors(sources)

        return [source for source in sources if source.is_enabled()]

    def update_vendor_runtime(
        self,
        vendor: str,
        *,
        attempt_at: datetime,
        article_count: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        """Update runtime statistics for a vendor."""
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

    def apply_vendor_metadata(self, metadata: dict[str, Any], attempt_at: datetime) -> None:
        """Apply vendor metadata from fetch results."""
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
            self.update_vendor_runtime(
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
            self.update_vendor_runtime(
                vendor_name,
                attempt_at=attempt_at,
                article_count=0,
                success=False,
                error=error_text or None,
            )

    def normalize_vendor_row(
        self,
        row: dict[str, Any],
        *,
        vendor_name: str,
        default_ticker: str,
    ) -> dict[str, Any]:
        """Normalize vendor-specific row format to standard format."""
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

    def fetch_vendor_entries(
        self,
        *,
        ticker: str,
        ttl: timedelta,
        now: datetime,
        max_entries: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fetch entries from all configured vendors."""
        metadata: dict[str, Any] = {"counts": {}, "errors": {}}
        if self.multi_source_fetcher is None:
            return [], metadata

        request = DatasetRequest(
            dataset=DATASET_NEWS,
            profile=None,
            tickers=[ticker],
            start=now - ttl,
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
            normalized = self.normalize_vendor_row(
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

    def update_recent_mix_summary(
        self,
        ticker: str,
        *,
        timestamp: datetime,
        pre_counts: dict[str, int],
        post_counts: dict[str, int],
        combined_entries: list[dict[str, Any]],
    ) -> None:
        """Update recent mix summary for health reporting."""
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
            "timestamp": timestamp,
            "total_pre": int(sum(pre_counts.values())),
            "total_post": len(combined_entries),
            "per_vendor_pre": pre_counts,
            "per_vendor_post": post_counts,
        }

    def get_vendor_config(self) -> dict[str, dict[str, Any]]:
        """Get vendor configuration dictionary."""
        return self._vendor_config

    def get_vendor_runtime(self) -> dict[str, dict[str, Any]]:
        """Get vendor runtime statistics dictionary."""
        return self._vendor_runtime

    def get_recent_mix_summary(self) -> dict[str, dict[str, Any]]:
        """Get recent mix summary dictionary."""
        return self._recent_mix_summary
