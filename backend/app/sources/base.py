"""Base classes for multi-source data fetching.

Ported from market-sim with adaptations for portfolio-ai.
"""

from __future__ import annotations

import abc
import dataclasses
import datetime as dt
import time
from collections.abc import Iterable

import polars as pl

from ..logging_config import get_logger

logger = get_logger(__name__)

# Dataset type constants
DATASET_DAY = "day"
DATASET_REFERENCE = "reference"
DATASET_NEWS = "news"


@dataclasses.dataclass(frozen=True)
class DatasetRequest:
    """Request for fetching dataset from a source."""

    dataset: str
    profile: str | None
    symbols: Iterable[str]
    start: dt.datetime | dt.date
    end: dt.datetime | dt.date
    timezone: str = "UTC"
    ingest_run_id: str | None = None


def standardize_dates(request: DatasetRequest) -> tuple[dt.date, dt.date]:
    """Convert request start/end to date objects.

    Handles both dt.date and dt.datetime inputs consistently across all sources.
    This consolidates ~240 lines of duplicate date conversion logic.

    Args:
        request: DatasetRequest with start and end dates

    Returns:
        Tuple of (start_date, end_date) as dt.date objects
    """
    # Handle start date
    if isinstance(request.start, dt.datetime):
        start_date = request.start.date()
    else:
        start_date = request.start

    # Handle end date
    if isinstance(request.end, dt.datetime):
        end_date = request.end.date()
    else:
        end_date = request.end

    return start_date, end_date


class BaseSource(abc.ABC):
    """Abstract base class for all data sources."""

    name: str = "base"
    priority: int = 100  # lower = preferred

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} priority={self.priority}>"

    # --- capability flags -------------------------------------------------
    supports_day: bool = False
    supports_reference: bool = False
    supports_news: bool = False
    supports_macro: bool = False

    # --- lifecycle --------------------------------------------------------
    def is_enabled(self) -> bool:
        """Override if the source has optional credentials."""
        return True

    # --- ingestion methods ------------------------------------------------
    @abc.abstractmethod
    def fetch_day_bars(self, request: DatasetRequest) -> pl.DataFrame | None:
        """Fetch daily OHLCV bars."""
        ...

    @abc.abstractmethod
    def fetch_reference_payload(
        self, symbols: Iterable[str], as_of: dt.date
    ) -> pl.DataFrame | None:
        """Fetch reference data (company info, sector, etc.)."""
        ...

    @abc.abstractmethod
    def fetch_news_payload(
        self, symbols: Iterable[str], start: dt.datetime, end: dt.datetime
    ) -> pl.DataFrame | None:
        """Fetch news articles."""
        ...


class SourceManager:
    """Utility to coordinate between multiple sources with automatic fallback."""

    def __init__(self, sources: Iterable[BaseSource]) -> None:
        """Initialize source manager with enabled sources sorted by priority."""
        self._sources = sorted([s for s in sources if s.is_enabled()], key=lambda s: s.priority)

    def get_sources_for_dataset(self, dataset: str) -> list[BaseSource]:
        """Get all sources that support the given dataset type."""
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
        """Get the highest priority source for the given dataset type."""
        candidates = self.get_sources_for_dataset(dataset)
        return candidates[0] if candidates else None

    def fetch_with_fallback(
        self, request: DatasetRequest, verbose: bool = True
    ) -> tuple[pl.DataFrame | None, dict[str, list[str]]]:
        """Fetch data with automatic fallback across sources.

        Tries sources in priority order. If a source fails or returns None,
        automatically tries the next available source.

        Args:
            request: DatasetRequest with dataset type, symbols, dates
            verbose: Log fallback messages (default: True)

        Returns:
            Tuple of (DataFrame, errors_by_source)
            - DataFrame: Combined data from all successful sources (or None if all failed)
            - errors_by_source: Dict mapping source name to list of error messages

        Example:
            >>> manager = SourceManager([polygon, yfinance, finnhub])
            >>> request = DatasetRequest(dataset='reference', symbols=['AAPL', 'MSFT'], ...)
            >>> df, errors = manager.fetch_with_fallback(request)
            >>> # Automatically tries: polygon → yfinance → finnhub
        """
        sources = self.get_sources_for_dataset(request.dataset)
        if not sources:
            return None, {"error": [f"No sources available for dataset: {request.dataset}"]}

        all_data = []
        errors_by_source: dict[str, list[str]] = {}
        symbols_remaining = set(request.symbols)

        for source in sources:
            if not symbols_remaining:
                break  # All symbols fetched successfully

            # Create request for remaining symbols
            remaining_request = dataclasses.replace(request, symbols=list(symbols_remaining))

            try:
                if verbose:
                    logger.info(
                        "source_manager_trying",
                        source=source.name,
                        num_symbols=len(symbols_remaining),
                        dataset=request.dataset,
                    )

                # Track performance per source
                start_time = time.time()

                # Fetch data based on dataset type
                if request.dataset == DATASET_DAY:
                    data = source.fetch_day_bars(remaining_request)
                elif request.dataset == DATASET_REFERENCE:
                    # Ensure start is a date for reference data
                    as_of_date: dt.date
                    if isinstance(remaining_request.start, dt.datetime):
                        as_of_date = remaining_request.start.date()
                    else:
                        as_of_date = remaining_request.start
                    data = source.fetch_reference_payload(list(symbols_remaining), as_of_date)
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
                    data = source.fetch_news_payload(list(symbols_remaining), start_dt, end_dt)
                else:
                    continue

                fetch_duration_ms = int((time.time() - start_time) * 1000)

                if data is not None and len(data) > 0:
                    all_data.append(data)

                    # Track which symbols were successfully fetched
                    if "symbol" in data.columns:
                        fetched_symbols = set(data["symbol"].unique().to_list())
                        symbols_remaining -= fetched_symbols

                        if verbose:
                            logger.info(
                                "source_manager_success",
                                source=source.name,
                                symbols_fetched=len(fetched_symbols),
                                symbols_remaining=len(symbols_remaining),
                                duration_ms=fetch_duration_ms,
                                rows=len(data),
                            )
                    else:
                        # Assume all symbols fetched if no ticker column
                        if verbose:
                            logger.info(
                                "source_manager_success",
                                source=source.name,
                                rows=len(data),
                                duration_ms=fetch_duration_ms,
                            )
                        symbols_remaining.clear()
                elif verbose:
                    logger.info(
                        "source_manager_no_data",
                        source=source.name,
                        duration_ms=fetch_duration_ms,
                    )

            except Exception as e:
                error_msg = str(e)
                if source.name not in errors_by_source:
                    errors_by_source[source.name] = []
                errors_by_source[source.name].append(error_msg)

                if verbose:
                    logger.warning(
                        "source_manager_error",
                        source=source.name,
                        error=error_msg,
                        error_type=type(e).__name__,
                    )

        # Combine data from all sources
        if all_data:
            combined = pl.concat(all_data) if len(all_data) > 1 else all_data[0]
            return combined, errors_by_source

        return None, errors_by_source

    @property
    def sources(self) -> list[BaseSource]:
        """Return list of enabled sources sorted by priority."""
        return self._sources
