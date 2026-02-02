"""News vendor source management and aggregation."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from ..logging_config import get_logger
from ..sources.base import BaseSource
from ..sources.multi_source_fetcher import MultiSourceFetcher
from ..storage import PortfolioStorage
from .vendor_config import prepare_vendor_sources
from .vendor_fetcher import fetch_vendor_entries
from .vendor_normalizer import normalize_vendor_row

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
        """Initialise vendor sources from overrides or environment configuration."""
        return prepare_vendor_sources(
            self.storage, vendor_sources, self._register_vendor
        )

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
        default_symbol: str,
    ) -> dict[str, Any]:
        """Normalize vendor-specific row format to standard format."""
        return normalize_vendor_row(row, vendor_name=vendor_name, default_symbol=default_symbol)

    def fetch_vendor_entries(
        self,
        *,
        symbol: str,
        ttl: timedelta,
        now: datetime,
        max_entries: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Fetch entries from all configured vendors."""
        return fetch_vendor_entries(
            self.multi_source_fetcher,
            symbol=symbol,
            ttl=ttl,
            now=now,
            max_entries=max_entries,
        )

    def update_recent_mix_summary(
        self,
        symbol: str,
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

        self._recent_mix_summary[symbol.upper()] = {
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
