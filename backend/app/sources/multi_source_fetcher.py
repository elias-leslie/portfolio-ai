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
from httpx import HTTPStatusError

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from .base import DATASET_DAY, DATASET_NEWS, DATASET_REFERENCE, BaseSource, DatasetRequest

logger = get_logger(__name__)

# Rate limit cooldown duration (60 seconds)
RATE_LIMIT_COOLDOWN_SECONDS = 60


@dataclasses.dataclass
class SourceMetrics:
    """Performance metrics for a data source."""

    source_name: str
    success_count: int = 0
    failure_count: int = 0
    total_latency_ms: int = 0
    rate_limit_hits: int = 0
    last_success_at: dt.datetime | None = None
    last_failure_at: dt.datetime | None = None
    last_rate_limit_at: dt.datetime | None = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        total = self.success_count + self.failure_count
        return (self.success_count / total * 100) if total > 0 else 0.0

    @property
    def avg_latency_ms(self) -> float:
        """Calculate average latency in milliseconds."""
        return self.total_latency_ms / self.success_count if self.success_count > 0 else 0.0

    def is_in_cooldown(self) -> bool:
        """Check if source is in rate limit cooldown."""
        if self.last_rate_limit_at is None:
            return False

        cooldown_until = self.last_rate_limit_at + dt.timedelta(seconds=RATE_LIMIT_COOLDOWN_SECONDS)
        return dt.datetime.now(dt.UTC) < cooldown_until

    def cooldown_remaining_seconds(self) -> int:
        """Calculate remaining cooldown time in seconds."""
        if not self.is_in_cooldown() or self.last_rate_limit_at is None:
            return 0

        cooldown_until = self.last_rate_limit_at + dt.timedelta(seconds=RATE_LIMIT_COOLDOWN_SECONDS)
        remaining = (cooldown_until - dt.datetime.now(dt.UTC)).total_seconds()
        return max(0, int(remaining))


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

        # In-memory metrics tracking
        self._metrics: dict[str, SourceMetrics] = {}
        for source in self._sources:
            self._metrics[source.name] = SourceMetrics(source_name=source.name)

        # Load metrics from database if available
        if self.storage:
            self._load_metrics_from_db()

    def _load_metrics_from_db(self) -> None:
        """Load source performance metrics from database.

        Reads from source_performance table if it exists.
        Silently skips if table doesn't exist (not created yet).
        """
        if not self.storage:
            return

        try:
            df = self.storage.query(
                """
                SELECT source_name, success_count, failure_count,
                       total_latency_ms, rate_limit_hits, last_success_at
                FROM source_performance
                """,
                [],
            )

            if df.is_empty():
                return

            for row in df.iter_rows(named=True):
                source_name = row["source_name"]
                if source_name in self._metrics:
                    self._metrics[source_name].success_count = row["success_count"] or 0
                    self._metrics[source_name].failure_count = row["failure_count"] or 0
                    self._metrics[source_name].total_latency_ms = row["total_latency_ms"] or 0
                    self._metrics[source_name].rate_limit_hits = row["rate_limit_hits"] or 0
                    self._metrics[source_name].last_success_at = row.get("last_success_at")

            logger.info(
                "metrics_loaded_from_db", num_sources=len(self._metrics), table="source_performance"
            )

        except Exception as e:
            # Table might not exist yet (Task 1.2.1 creates it)
            logger.debug("metrics_load_skipped", error=str(e), reason="table_not_ready")

    def _save_metrics_to_db(self, source_name: str) -> None:
        """Save source performance metrics to database.

        Args:
            source_name: Name of source to save metrics for
        """
        if not self.storage or source_name not in self._metrics:
            return

        metrics = self._metrics[source_name]

        try:
            self.storage.insert_dict(
                "source_performance",
                {
                    "source_name": source_name,
                    "success_count": metrics.success_count,
                    "failure_count": metrics.failure_count,
                    "total_latency_ms": metrics.total_latency_ms,
                    "rate_limit_hits": metrics.rate_limit_hits,
                    "last_success_at": metrics.last_success_at,
                },
            )

            logger.debug("metrics_saved_to_db", source=source_name)

        except Exception as e:
            # Non-fatal - metrics still tracked in memory
            logger.debug("metrics_save_failed", source=source_name, error=str(e))

    def _record_success(self, source_name: str, latency_ms: int) -> None:
        """Record successful fetch.

        Args:
            source_name: Name of source
            latency_ms: Request latency in milliseconds
        """
        if source_name not in self._metrics:
            self._metrics[source_name] = SourceMetrics(source_name=source_name)

        metrics = self._metrics[source_name]
        metrics.success_count += 1
        metrics.total_latency_ms += latency_ms
        metrics.last_success_at = dt.datetime.now(dt.UTC)

        logger.info(
            "source_success",
            source=source_name,
            latency_ms=latency_ms,
            success_rate=f"{metrics.success_rate:.1f}%",
            avg_latency_ms=int(metrics.avg_latency_ms),
        )

        # Persist to database
        if self.storage:
            self._save_metrics_to_db(source_name)

    def _record_failure(self, source_name: str, error: Exception) -> None:
        """Record failed fetch.

        Args:
            source_name: Name of source
            error: Exception that occurred
        """
        if source_name not in self._metrics:
            self._metrics[source_name] = SourceMetrics(source_name=source_name)

        metrics = self._metrics[source_name]
        metrics.failure_count += 1
        metrics.last_failure_at = dt.datetime.now(dt.UTC)

        # Check if rate limit error (HTTP 429)
        is_rate_limit = False
        if isinstance(error, HTTPStatusError) and error.response.status_code == 429:
            is_rate_limit = True
            metrics.rate_limit_hits += 1
            metrics.last_rate_limit_at = dt.datetime.now(dt.UTC)

            logger.warning(
                "source_rate_limit_hit",
                source=source_name,
                cooldown_seconds=RATE_LIMIT_COOLDOWN_SECONDS,
                total_rate_limit_hits=metrics.rate_limit_hits,
            )

        if not is_rate_limit:
            logger.warning(
                "source_failure",
                source=source_name,
                error=str(error),
                error_type=type(error).__name__,
                success_rate=f"{metrics.success_rate:.1f}%",
            )

        # Persist to database
        if self.storage:
            self._save_metrics_to_db(source_name)

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

    def fetch_with_fallback(
        self, request: DatasetRequest, verbose: bool = True
    ) -> tuple[pl.DataFrame | None, dict[str, list[str]]]:
        """Fetch data with automatic fallback across sources.

        Tries sources in priority order with rate limit awareness:
        - Skips sources in cooldown (recent HTTP 429)
        - Tracks performance metrics (success rate, latency)
        - Persists metrics to database

        Args:
            request: DatasetRequest with dataset type, tickers, dates
            verbose: Log fallback messages (default: True)

        Returns:
            Tuple of (DataFrame, errors_by_source)
            - DataFrame: Combined data from all successful sources (or None if all failed)
            - errors_by_source: Dict mapping source name to list of error messages

        Example:
            >>> fetcher = MultiSourceFetcher([polygon, yfinance, finnhub], storage)
            >>> request = DatasetRequest(dataset='reference', tickers=['AAPL', 'MSFT'], ...)
            >>> df, errors = fetcher.fetch_with_fallback(request)
            >>> # Automatically tries: polygon → yfinance → finnhub (skips if in cooldown)
        """
        sources = self.get_sources_for_dataset(request.dataset)
        if not sources:
            return None, {"error": [f"No sources available for dataset: {request.dataset}"]}

        all_data = []
        errors_by_source: dict[str, list[str]] = {}
        tickers_remaining = set(request.tickers)
        news_dataset = request.dataset == DATASET_NEWS

        for source in sources:
            if not news_dataset and not tickers_remaining:
                break  # All tickers fetched successfully

            # Check rate limit cooldown
            metrics = self._metrics.get(source.name)
            if metrics and metrics.is_in_cooldown():
                cooldown_remaining = metrics.cooldown_remaining_seconds()
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
                continue

            # Create request for remaining tickers
            remaining_request = dataclasses.replace(
                request,
                tickers=list(tickers_remaining) if not news_dataset else list(request.tickers),
            )

            try:
                if verbose:
                    logger.info(
                        "source_trying",
                        source=source.name,
                        priority=source.priority,
                        num_tickers=len(tickers_remaining),
                        dataset=request.dataset,
                    )

                # Track performance per source
                start_time = time.time()

                # Fetch data based on dataset type
                data: pl.DataFrame | None = None
                if request.dataset == DATASET_DAY:
                    data = source.fetch_day_bars(remaining_request)
                elif request.dataset == DATASET_REFERENCE:
                    # Ensure start is a date for reference data
                    as_of_date: dt.date
                    if isinstance(remaining_request.start, dt.datetime):
                        as_of_date = remaining_request.start.date()
                    else:
                        as_of_date = remaining_request.start
                    data = source.fetch_reference_payload(list(tickers_remaining), as_of_date)
                elif request.dataset == DATASET_NEWS:
                    # Ensure start/end are datetime for news
                    start_dt = (
                        remaining_request.start
                        if isinstance(remaining_request.start, dt.datetime)
                        else dt.datetime.combine(remaining_request.start, dt.time.min)
                    )
                    end_dt = (
                        remaining_request.end
                        if isinstance(remaining_request.end, dt.datetime)
                        else dt.datetime.combine(remaining_request.end, dt.time.max)
                    )
                    data = source.fetch_news_payload(list(tickers_remaining), start_dt, end_dt)
                else:
                    continue

                fetch_duration_ms = int((time.time() - start_time) * 1000)

                if data is not None and len(data) > 0:
                    all_data.append(data)

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

                    # Record success metrics
                    self._record_success(source.name, fetch_duration_ms)

                elif verbose:
                    logger.info("source_no_data", source=source.name)
                    # Still record as success (no error, just no data)
                    self._record_success(source.name, fetch_duration_ms)

            except Exception as e:
                error_msg = str(e)
                if source.name not in errors_by_source:
                    errors_by_source[source.name] = []
                errors_by_source[source.name].append(error_msg)

                # Record failure metrics (checks for rate limit)
                self._record_failure(source.name, e)

                # Continue to next source for failover

        # Combine data from all sources
        # Use diagonal concat to handle different schemas (e.g., SEC EDGAR has extra fields)
        if all_data:
            # Normalize schemas before concat to avoid type incompatibility errors
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
                    tickers_remaining=len(tickers_remaining),
                )

            return combined, errors_by_source

        if verbose:
            logger.warning(
                "multi_source_fetch_failed",
                dataset=request.dataset,
                num_tickers_requested=len(list(request.tickers)),
                errors=errors_by_source,
            )

        return None, errors_by_source

    def get_source_metrics(self, source_name: str | None = None) -> dict[str, SourceMetrics]:
        """Get performance metrics for sources.

        Args:
            source_name: Specific source name, or None for all sources

        Returns:
            Dictionary mapping source name to SourceMetrics
        """
        if source_name:
            return {source_name: self._metrics[source_name]} if source_name in self._metrics else {}

        return dict(self._metrics)

    @property
    def sources(self) -> list[BaseSource]:
        """Return list of enabled sources sorted by priority."""
        return self._sources
