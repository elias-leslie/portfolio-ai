"""Multi-source data fetcher with priority-based failover and rate limit management.

This module extends SourceManager with:
- 60-second rate limit cooldown on HTTP 429
- Source performance tracking (success rate, latency, rate limit hits)
- Enhanced structured logging for failover events

Ported from market-sim with adaptations for portfolio-ai.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import time
from collections.abc import Iterable

import polars as pl

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from .base import DATASET_DAY, DATASET_NEWS, DATASET_REFERENCE, BaseSource, DatasetRequest
from .source_metrics_manager import SourceMetrics, SourceMetricsManager

logger = get_logger(__name__)


class MultiSourceFetcher:
    """Fetch data with priority-based failover and rate limit management.

    Enhances SourceManager with:
    - Automatic rate limit cooldown (skips sources with recent 429 errors)
    - Performance metrics tracking (success rate, latency, rate limit hits)
    - Database persistence of source performance metrics
    """

    def __init__(
        self, sources: Iterable[BaseSource], storage: PortfolioStorage | None = None
    ) -> None:
        """Initialize multi-source fetcher.

        Args:
            sources: Iterable of BaseSource implementations
            storage: PortfolioStorage instance for metrics persistence (optional)
        """
        # Sort sources by priority (lower = preferred)
        self._sources = sorted([s for s in sources if s.is_enabled()], key=lambda s: s.priority)
        self.storage = storage

        # Initialize metrics manager
        self.metrics_manager = SourceMetricsManager(storage)
        for source in self._sources:
            self.metrics_manager.initialize_metric(source.name)

        # Load metrics from database if available
        if self.storage:
            self.metrics_manager.load_all_from_db()

    def get_sources_for_dataset(self, dataset: str) -> list[BaseSource]:
        """Get all sources that support the given dataset type.

        Args:
            dataset: Dataset type (day, reference, news)

        Returns:
            List of sources sorted by priority
        """
        filtered: list[BaseSource] = []
        for source in self._sources:
            if (
                (dataset == DATASET_DAY and source.supports_day)
                or (dataset == DATASET_REFERENCE and source.supports_reference)
                or (dataset == DATASET_NEWS and source.supports_news)
            ):
                filtered.append(source)
        return filtered

    def best_source_for_dataset(self, dataset: str) -> BaseSource | None:
        """Get the highest priority source for the given dataset type.

        Args:
            dataset: Dataset type (day, reference, news)

        Returns:
            Best available source or None
        """
        candidates = self.get_sources_for_dataset(dataset)
        return candidates[0] if candidates else None

    def _normalize_news_schema(self, df: pl.DataFrame) -> pl.DataFrame:
        """Normalize dataframe schema to ensure consistent types across sources.

        This prevents Polars concat errors when one source has a column with
        all None values (inferred as Null type) and another has String values.

        Args:
            df: Dataframe from any news source

        Returns:
            Dataframe with normalized column types
        """
        # Define expected schema for standard news columns
        # All nullable columns must be explicitly cast to Utf8 (not Null type)
        standard_casts = {
            "ticker": pl.Utf8,
            "headline": pl.Utf8,
            "url": pl.Utf8,
            "summary": pl.Utf8,
            "news_source_name": pl.Utf8,
            "author": pl.Utf8,  # Often null, needs explicit cast
            "image_url": pl.Utf8,  # Often null, needs explicit cast
            "raw_payload": pl.Utf8,  # Often null, needs explicit cast
            "source": pl.Utf8,
            "vendor": pl.Utf8,
        }

        # SEC EDGAR-specific columns (may not exist in other sources)
        sec_edgar_casts = {
            "filing_type": pl.Utf8,
            "plain_language_headline": pl.Utf8,
            "is_material_event": pl.Boolean,
        }

        # Apply casts only for columns that exist in this dataframe
        cast_exprs = []
        for col, dtype in {**standard_casts, **sec_edgar_casts}.items():
            if col in df.columns:
                cast_exprs.append(pl.col(col).cast(dtype, strict=False))

        if cast_exprs:
            df = df.with_columns(cast_exprs)

        return df

    def _check_source_cooldown(
        self, source: BaseSource, verbose: bool, errors_by_source: dict[str, list[str]]
    ) -> bool:
        """Check if source is in rate limit cooldown.

        Args:
            source: Source to check
            verbose: Whether to log warnings
            errors_by_source: Dict to add error message to

        Returns:
            True if source is in cooldown (should skip), False otherwise
        """
        if self.metrics_manager.is_in_cooldown(source.name):
            cooldown_remaining = self.metrics_manager.cooldown_remaining(source.name)
            if verbose:
                logger.warning(
                    "source_skipped_cooldown",
                    source=source.name,
                    cooldown_remaining_seconds=cooldown_remaining,
                    reason="rate_limit_429",
                )
            errors_by_source[source.name] = [
                f"Skipped due to rate limit cooldown ({cooldown_remaining}s remaining)"
            ]
            return True
        return False

    def _fetch_from_source(
        self, source: BaseSource, request: DatasetRequest, tickers: set[str]
    ) -> pl.DataFrame | None:
        """Fetch data from a specific source based on dataset type.

        Args:
            source: Source to fetch from
            request: Original request with dataset type and date range
            tickers: Tickers to fetch

        Returns:
            DataFrame with fetched data, or None if no data
        """
        if request.dataset == DATASET_DAY:
            remaining_request = dataclasses.replace(request, tickers=list(tickers))
            return source.fetch_day_bars(remaining_request)

        if request.dataset == DATASET_REFERENCE:
            # Ensure start is a date for reference data
            as_of_date: dt.date = (
                request.start.date() if isinstance(request.start, dt.datetime) else request.start
            )
            return source.fetch_reference_payload(list(tickers), as_of_date)

        if request.dataset == DATASET_NEWS:
            # Ensure start/end are datetime for news
            start_dt = (
                request.start
                if isinstance(request.start, dt.datetime)
                else dt.datetime.combine(request.start, dt.time.min)
            )
            end_dt = (
                request.end
                if isinstance(request.end, dt.datetime)
                else dt.datetime.combine(request.end, dt.time.max)
            )
            return source.fetch_news_payload(list(tickers), start_dt, end_dt)

        return None

    def _process_fetch_result(
        self,
        data: pl.DataFrame | None,
        source: BaseSource,
        fetch_duration_ms: int,
        tickers_remaining: set[str],
        news_dataset: bool,
        verbose: bool,
    ) -> bool:
        """Process fetch result and update metrics.

        Args:
            data: Fetched data (or None)
            source: Source that fetched the data
            fetch_duration_ms: Fetch duration in milliseconds
            tickers_remaining: Set of tickers still needing data
            news_dataset: Whether this is a news dataset
            verbose: Whether to log info messages

        Returns:
            True if data was fetched, False otherwise
        """
        if data is not None and len(data) > 0:
            # Track which tickers were successfully fetched
            if "ticker" in data.columns and not news_dataset:
                fetched_tickers = set(data["ticker"].unique().to_list())
                tickers_remaining -= fetched_tickers

                if verbose:
                    logger.info(
                        "source_fetched_partial",
                        source=source.name,
                        tickers_fetched=len(fetched_tickers),
                        tickers_remaining=len(tickers_remaining),
                        rows=len(data),
                    )
            else:
                # Assume all tickers fetched if no ticker column
                if verbose:
                    logger.info("source_fetched_all", source=source.name, rows=len(data))
                if not news_dataset:
                    tickers_remaining.clear()

            self.metrics_manager.record_success(source.name, fetch_duration_ms)
            return True

        # No data, but still success (no error)
        if verbose:
            logger.info("source_no_data", source=source.name)
        self.metrics_manager.record_success(source.name, fetch_duration_ms)
        return False

    def _combine_results(self, all_data: list[pl.DataFrame], verbose: bool) -> pl.DataFrame | None:
        """Combine data from multiple sources.

        Args:
            all_data: List of DataFrames from successful sources
            verbose: Whether to log info

        Returns:
            Combined DataFrame, or None if no data
        """
        if not all_data:
            return None

        # Normalize schemas before concat to avoid type incompatibility
        normalized_data = [self._normalize_news_schema(df) for df in all_data]
        combined = (
            pl.concat(normalized_data, how="diagonal")
            if len(normalized_data) > 1
            else normalized_data[0]
        )

        if verbose:
            logger.info(
                "multi_source_fetch_complete",
                total_rows=len(combined),
                num_sources_used=len(all_data),
            )

        return combined

    def fetch_with_fallback(
        self, request: DatasetRequest, verbose: bool = True
    ) -> tuple[pl.DataFrame | None, dict[str, list[str]]]:
        """Fetch data with automatic fallback across sources.

        Tries sources in priority order with rate limit awareness.

        Args:
            request: DatasetRequest with dataset type, tickers, dates
            verbose: Log fallback messages (default: True)

        Returns:
            Tuple of (DataFrame, errors_by_source)
        """
        sources = self.get_sources_for_dataset(request.dataset)
        if not sources:
            return None, {"error": [f"No sources available for dataset: {request.dataset}"]}

        # Log available sources at start
        available_sources = [s.name for s in sources]
        sources_in_cooldown = [
            s.name for s in sources if self.metrics_manager.is_in_cooldown(s.name)
        ]
        if verbose:
            logger.info(
                "fetch_started",
                dataset=request.dataset,
                num_tickers=len(list(request.tickers)),
                available_sources=available_sources,
                total_sources=len(available_sources),
                sources_in_cooldown=sources_in_cooldown,
            )

        all_data = []
        errors_by_source: dict[str, list[str]] = {}
        tickers_remaining = set(request.tickers)
        news_dataset = request.dataset == DATASET_NEWS

        for source in sources:
            # Stop if all tickers fetched (non-news datasets)
            if not news_dataset and not tickers_remaining:
                break

            # Skip sources in cooldown
            if self._check_source_cooldown(source, verbose, errors_by_source):
                continue

            try:
                if verbose:
                    logger.info(
                        "source_trying",
                        source=source.name,
                        priority=source.priority,
                        num_tickers=len(tickers_remaining),
                        dataset=request.dataset,
                    )

                # Fetch data
                start_time = time.time()
                data = self._fetch_from_source(source, request, tickers_remaining)
                fetch_duration_ms = int((time.time() - start_time) * 1000)

                # Process result
                if (
                    self._process_fetch_result(
                        data, source, fetch_duration_ms, tickers_remaining, news_dataset, verbose
                    )
                    and data is not None
                ):  # Narrow type for mypy
                    all_data.append(data)

            except Exception as e:
                if source.name not in errors_by_source:
                    errors_by_source[source.name] = []
                errors_by_source[source.name].append(str(e))
                self.metrics_manager.record_failure(source.name, e)

                # Log source failure with fallback info
                next_source = None
                for idx, s in enumerate(sources):
                    if s.name == source.name and idx + 1 < len(sources):
                        # Find next source not in cooldown
                        for next_s in sources[idx + 1 :]:
                            if not self.metrics_manager.is_in_cooldown(next_s.name):
                                next_source = next_s
                                break
                        break

                if verbose:
                    logger.warning(
                        "source_failed",
                        source=source.name,
                        error=str(e),
                        fallback_to=next_source.name if next_source else None,
                    )

        # Combine and return results
        combined = self._combine_results(all_data, verbose)

        if combined is None and verbose:
            logger.error(
                "fetch_all_sources_failed",
                dataset=request.dataset,
                num_tickers_requested=len(list(request.tickers)),
                sources_tried=len(sources),
                sources_in_cooldown=len(sources_in_cooldown),
                errors=errors_by_source,
            )
        elif combined is not None and verbose:
            sources_used = len(all_data)
            logger.info(
                "fetch_completed",
                dataset=request.dataset,
                total_rows=len(combined),
                sources_used=sources_used,
                sources_tried=len(sources),
            )

        return combined, errors_by_source

    def get_source_metrics(self, source_name: str | None = None) -> dict[str, SourceMetrics]:
        """Get performance metrics for sources.

        Args:
            source_name: Specific source name, or None for all sources

        Returns:
            Dictionary mapping source name to SourceMetrics
        """
        if source_name:
            metric = self.metrics_manager.get_metric(source_name)
            return {source_name: metric} if metric else {}

        return self.metrics_manager.get_all_metrics()

    @property
    def sources(self) -> list[BaseSource]:
        """Return list of enabled sources sorted by priority."""
        return self._sources
