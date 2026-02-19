"""Helper functions for multi-source data fetching.

Standalone utilities for schema normalization, source dispatch,
result processing, and combining data from multiple sources.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import polars as pl

from ..logging_config import get_logger
from .base import DATASET_DAY, DATASET_NEWS, DATASET_REFERENCE, BaseSource, DatasetRequest
from .source_metrics_manager import SourceMetricsManager

logger = get_logger(__name__)

# Schema constants for news normalization
_NEWS_STANDARD_COLUMNS: dict[str, pl.PolarsDataType] = {
    "symbol": pl.Utf8,
    "headline": pl.Utf8,
    "url": pl.Utf8,
    "summary": pl.Utf8,
    "news_source_name": pl.Utf8,
    "author": pl.Utf8,
    "image_url": pl.Utf8,
    "raw_payload": pl.Utf8,
    "source": pl.Utf8,
    "vendor": pl.Utf8,
}

_NEWS_SEC_EDGAR_COLUMNS: dict[str, pl.PolarsDataType] = {
    "filing_type": pl.Utf8,
    "is_material_event": pl.Boolean,
}


def normalize_news_schema(df: pl.DataFrame) -> pl.DataFrame:
    """Normalize dataframe schema to ensure consistent types across sources.

    Prevents Polars concat errors when one source has a column with
    all None values (inferred as Null type) and another has String values.

    Args:
        df: Dataframe from any news source

    Returns:
        Dataframe with normalized column types
    """
    all_casts = {**_NEWS_STANDARD_COLUMNS, **_NEWS_SEC_EDGAR_COLUMNS}
    cast_exprs = [
        pl.col(col).cast(dtype, strict=False)
        for col, dtype in all_casts.items()
        if col in df.columns
    ]
    return df.with_columns(cast_exprs) if cast_exprs else df


def fetch_from_source(
    source: BaseSource, request: DatasetRequest, symbols: set[str]
) -> pl.DataFrame | None:
    """Fetch data from a specific source based on dataset type.

    Args:
        source: Source to fetch from
        request: Original request with dataset type and date range
        symbols: Symbols to fetch

    Returns:
        DataFrame with fetched data, or None if no data
    """
    if request.dataset == DATASET_DAY:
        return source.fetch_day_bars(dataclasses.replace(request, symbols=list(symbols)))

    if request.dataset == DATASET_REFERENCE:
        as_of_date: dt.date = (
            request.start.date() if isinstance(request.start, dt.datetime) else request.start
        )
        return source.fetch_reference_payload(list(symbols), as_of_date)

    if request.dataset == DATASET_NEWS:
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
        return source.fetch_news_payload(list(symbols), start_dt, end_dt)

    return None


def process_fetch_result(
    data: pl.DataFrame | None,
    source: BaseSource,
    fetch_duration_ms: int,
    symbols_remaining: set[str],
    news_dataset: bool,
    verbose: bool,
    metrics_manager: SourceMetricsManager,
) -> bool:
    """Process fetch result and update metrics.

    Args:
        data: Fetched data (or None)
        source: Source that fetched the data
        fetch_duration_ms: Fetch duration in milliseconds
        symbols_remaining: Set of symbols still needing data (mutated in-place)
        news_dataset: Whether this is a news dataset
        verbose: Whether to log info messages
        metrics_manager: Manager for recording success metrics

    Returns:
        True if data was fetched, False otherwise
    """
    if data is None or len(data) == 0:
        if verbose:
            logger.info("source_no_data", source=source.name)
        return False

    if "symbol" in data.columns and not news_dataset:
        fetched_symbols = set(data["symbol"].unique().to_list())
        symbols_remaining -= fetched_symbols
        if verbose:
            logger.info(
                "source_fetched_partial",
                source=source.name,
                symbols_fetched=len(fetched_symbols),
                symbols_remaining=len(symbols_remaining),
                rows=len(data),
            )
    else:
        if verbose:
            logger.info("source_fetched_all", source=source.name, rows=len(data))
        if not news_dataset:
            symbols_remaining.clear()

    metrics_manager.record_success(source.name, fetch_duration_ms)
    return True


def combine_results(all_data: list[pl.DataFrame], verbose: bool) -> pl.DataFrame | None:
    """Combine data from multiple sources.

    Args:
        all_data: List of DataFrames from successful sources
        verbose: Whether to log info

    Returns:
        Combined DataFrame, or None if no data
    """
    if not all_data:
        return None

    normalized = [normalize_news_schema(df) for df in all_data]
    combined = pl.concat(normalized, how="diagonal") if len(normalized) > 1 else normalized[0]

    if verbose:
        logger.info(
            "multi_source_fetch_complete",
            total_rows=len(combined),
            num_sources_used=len(all_data),
        )
    return combined


def find_next_available_source(
    sources: list[BaseSource],
    current_name: str,
    metrics_manager: SourceMetricsManager,
) -> BaseSource | None:
    """Find the next source after current_name that is not in cooldown.

    Args:
        sources: Ordered list of sources
        current_name: Name of the current (failed) source
        metrics_manager: Used to check cooldown status

    Returns:
        Next available source, or None
    """
    for idx, s in enumerate(sources):
        if s.name != current_name:
            continue
        for next_s in sources[idx + 1 :]:
            if not metrics_manager.is_in_cooldown(next_s.name):
                return next_s
        break
    return None
