"""Multi-source data fetcher with priority-based failover and rate limit management.

Enhances source fetching with 60-second rate limit cooldown on HTTP 429,
source performance tracking, and structured logging for failover events.
Ported from market-sim with adaptations for portfolio-ai.
"""

from __future__ import annotations

import time
from collections.abc import Iterable

import polars as pl

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from ._fetch_helpers import (
    combine_results,
    fetch_from_source,
    find_next_available_source,
    process_fetch_result,
)
from .base import DATASET_DAY, DATASET_NEWS, DATASET_REFERENCE, BaseSource, DatasetRequest
from .source_metrics_manager import SourceMetrics, SourceMetricsManager

logger = get_logger(__name__)


class MultiSourceFetcher:
    """Fetch data with priority-based failover and rate limit management."""

    def __init__(
        self, sources: Iterable[BaseSource], storage: PortfolioStorage | None = None
    ) -> None:
        self._sources = sorted([s for s in sources if s.is_enabled()], key=lambda s: s.priority)
        self.storage = storage
        self.metrics_manager = SourceMetricsManager(storage)
        for source in self._sources:
            self.metrics_manager.initialize_metric(source.name)
        if self.storage:
            self.metrics_manager.load_all_from_db()

    @property
    def sources(self) -> list[BaseSource]:
        """Return list of enabled sources sorted by priority."""
        return self._sources

    def get_sources_for_dataset(self, dataset: str) -> list[BaseSource]:
        """Get all sources that support the given dataset type."""
        return [
            s
            for s in self._sources
            if (dataset == DATASET_DAY and s.supports_day)
            or (dataset == DATASET_REFERENCE and s.supports_reference)
            or (dataset == DATASET_NEWS and s.supports_news)
        ]

    def best_source_for_dataset(self, dataset: str) -> BaseSource | None:
        """Get the highest priority source for the given dataset type."""
        candidates = self.get_sources_for_dataset(dataset)
        return candidates[0] if candidates else None

    def get_source_metrics(self, source_name: str | None = None) -> dict[str, SourceMetrics]:
        """Get performance metrics for one source or all sources."""
        if source_name:
            metric = self.metrics_manager.get_metric(source_name)
            return {source_name: metric} if metric else {}
        return self.metrics_manager.get_all_metrics()

    def fetch_with_fallback(
        self, request: DatasetRequest, verbose: bool = True
    ) -> tuple[pl.DataFrame | None, dict[str, list[str]]]:
        """Fetch data with automatic fallback across sources in priority order.

        Args:
            request: DatasetRequest with dataset type, symbols, dates
            verbose: Log fallback messages (default: True)

        Returns:
            Tuple of (DataFrame or None, errors_by_source dict)
        """
        sources = self.get_sources_for_dataset(request.dataset)
        if not sources:
            return None, {"error": [f"No sources available for dataset: {request.dataset}"]}

        cooldown_names = [s.name for s in sources if self.metrics_manager.is_in_cooldown(s.name)]
        if verbose:
            logger.info(
                "fetch_started",
                dataset=request.dataset,
                num_symbols=len(list(request.symbols)),
                available_sources=[s.name for s in sources],
                total_sources=len(sources),
                sources_in_cooldown=cooldown_names,
            )

        all_data: list[pl.DataFrame] = []
        errors: dict[str, list[str]] = {}
        symbols_remaining = set(request.symbols)
        news_dataset = request.dataset == DATASET_NEWS

        for source in sources:
            if not news_dataset and not symbols_remaining:
                break
            if self._skip_if_cooldown(source, verbose, errors):
                continue
            self._fetch_one(source, request, symbols_remaining, news_dataset, verbose, all_data, errors, sources)

        combined = combine_results(all_data, verbose)
        if verbose:
            self._log_outcome(combined, request, sources, cooldown_names, errors)
        return combined, errors

    def _skip_if_cooldown(
        self, source: BaseSource, verbose: bool, errors: dict[str, list[str]]
    ) -> bool:
        """Return True and record error if source is in rate-limit cooldown."""
        if not self.metrics_manager.is_in_cooldown(source.name):
            return False
        remaining = self.metrics_manager.cooldown_remaining(source.name)
        if verbose:
            logger.warning(
                "source_skipped_cooldown",
                source=source.name,
                cooldown_remaining_seconds=remaining,
                reason="rate_limit_429",
            )
        errors[source.name] = [f"Skipped due to rate limit cooldown ({remaining}s remaining)"]
        return True

    def _fetch_one(
        self,
        source: BaseSource,
        request: DatasetRequest,
        symbols_remaining: set[str],
        news_dataset: bool,
        verbose: bool,
        all_data: list[pl.DataFrame],
        errors: dict[str, list[str]],
        sources: list[BaseSource],
    ) -> None:
        """Attempt a single source fetch; mutates all_data and errors in place."""
        if verbose:
            logger.info(
                "source_trying",
                source=source.name,
                priority=source.priority,
                num_symbols=len(symbols_remaining),
                dataset=request.dataset,
            )
        try:
            t0 = time.time()
            data = fetch_from_source(source, request, symbols_remaining)
            duration_ms = int((time.time() - t0) * 1000)
            fetched = process_fetch_result(
                data, source, duration_ms, symbols_remaining,
                news_dataset, verbose, self.metrics_manager,
            )
            if fetched and data is not None:
                all_data.append(data)
        except Exception as e:
            errors.setdefault(source.name, []).append(str(e))
            self.metrics_manager.record_failure(source.name, e)
            nxt = find_next_available_source(sources, source.name, self.metrics_manager)
            if verbose:
                logger.warning(
                    "source_failed",
                    source=source.name,
                    error=str(e),
                    fallback_to=nxt.name if nxt else None,
                )

    def _log_outcome(
        self,
        combined: pl.DataFrame | None,
        request: DatasetRequest,
        sources: list[BaseSource],
        cooldown_names: list[str],
        errors: dict[str, list[str]],
    ) -> None:
        """Log the final fetch outcome (success or full failure)."""
        if combined is None:
            logger.error(
                "fetch_all_sources_failed",
                dataset=request.dataset,
                num_symbols_requested=len(list(request.symbols)),
                sources_tried=len(sources),
                sources_in_cooldown=len(cooldown_names),
                errors=errors,
            )
        else:
            logger.info(
                "fetch_completed",
                dataset=request.dataset,
                total_rows=len(combined),
                sources_used=len(sources),
                sources_tried=len(sources),
            )
