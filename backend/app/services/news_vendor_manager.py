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
        sec_edgar_notes = (
            "SEC EDGAR filings (8-K, 10-Q, 10-K, Form 4) - highest quality free source."
        )
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
            (
                "google_news_rss",
                GoogleNewsRssSource,
                "Google News aggregated market & ticker RSS feeds",
                "GOOGLE_NEWS_RSS_ENABLED",
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
