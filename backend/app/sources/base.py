"""Base classes for multi-source data fetching.

Ported from market-sim with adaptations for portfolio-ai.
"""

from __future__ import annotations

import abc
import dataclasses
import datetime as dt
from collections.abc import Iterable

import polars as pl

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
