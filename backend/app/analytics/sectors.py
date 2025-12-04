"""Sector rotation analysis for trading intelligence.

This module provides functions for analyzing sector performance and momentum
to identify sector rotation patterns and relative sector strength.
"""

from __future__ import annotations

import datetime as dt
from typing import cast

import polars as pl

from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def _parse_target_date(date: dt.date | str) -> dt.date:
    """Convert date input to date object.

    Args:
        date: Date as string (YYYY-MM-DD) or date object

    Returns:
        Date object
    """
    if isinstance(date, str):
        return dt.datetime.strptime(date, "%Y-%m-%d").date()
    return date


def _fetch_sector_mapping(storage: PortfolioStorage) -> pl.DataFrame | None:
    """Fetch latest sector mapping for all symbols.

    Args:
        storage: PortfolioStorage instance

    Returns:
        DataFrame with symbol and sector columns, or None if no data
    """
    sector_query = """
        WITH latest_sectors AS (
            SELECT DISTINCT ON (symbol)
                symbol,
                sector
            FROM price_cache
            WHERE sector IS NOT NULL
                AND sector != ''
            ORDER BY symbol, cached_at DESC
        )
        SELECT symbol, sector
        FROM latest_sectors
    """
    return storage.query(sector_query, [])


def _calculate_momentum_dates(target_date: dt.date) -> tuple[dt.date, dt.date]:
    """Calculate lookback dates for momentum periods.

    Args:
        target_date: Target analysis date

    Returns:
        Tuple of (date_5d, date_20d) for momentum calculations
    """
    date_5d = target_date - dt.timedelta(days=7)
    date_20d = target_date - dt.timedelta(days=28)
    return date_5d, date_20d


def _fetch_symbol_returns(
    storage: PortfolioStorage,
    target_date: dt.date,
    date_5d: dt.date,
    date_20d: dt.date,
) -> pl.DataFrame | None:
    """Fetch price returns for all symbols across multiple periods.

    Args:
        storage: PortfolioStorage instance
        target_date: Current date for returns calculation
        date_5d: Start date for 5-day returns
        date_20d: Start date for 20-day returns

    Returns:
        DataFrame with symbol, returns, and volume data, or None if no data
    """
    returns_query = """
        WITH price_now AS (
            SELECT symbol, close as close_now, volume
            FROM day_bars
            WHERE date = ?
        ),
        price_5d AS (
            SELECT symbol, close as close_5d
            FROM day_bars
            WHERE date >= ?
                AND date < ?
            QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date ASC) = 1
        ),
        price_20d AS (
            SELECT symbol, close as close_20d
            FROM day_bars
            WHERE date >= ?
                AND date < ?
            QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date ASC) = 1
        )
        SELECT
            p.symbol,
            p.close_now,
            p.volume,
            p5.close_5d,
            p20.close_20d,
            CASE
                WHEN p5.close_5d > 0 THEN ((p.close_now - p5.close_5d) / p5.close_5d) * 100
                ELSE NULL
            END as return_5d,
            CASE
                WHEN p20.close_20d > 0 THEN ((p.close_now - p20.close_20d) / p20.close_20d) * 100
                ELSE NULL
            END as return_20d
        FROM price_now p
        LEFT JOIN price_5d p5 ON p.symbol = p5.symbol
        LEFT JOIN price_20d p20 ON p.symbol = p20.symbol
    """
    return storage.query(
        returns_query,
        [
            target_date.isoformat(),
            date_5d.isoformat(),
            target_date.isoformat(),
            date_20d.isoformat(),
            target_date.isoformat(),
        ],
    )


def _aggregate_sector_stats(combined: pl.DataFrame) -> pl.DataFrame:
    """Aggregate symbol data by sector and calculate sector-level metrics.

    Args:
        combined: DataFrame with symbol-level returns and sector information

    Returns:
        DataFrame with sector-level aggregated statistics
    """
    return (
        combined.group_by("sector")
        .agg(
            [
                pl.col("return_5d").mean().alias("momentum_5d"),
                pl.col("return_20d").mean().alias("momentum_20d"),
                pl.col("symbol").count().alias("num_stocks"),
                pl.col("volume").mean().alias("avg_volume"),
            ]
        )
        .filter(pl.col("momentum_20d").is_not_null())
        .sort("momentum_20d", descending=True)
    )


def get_sector_rotation(
    storage: PortfolioStorage,
    date: dt.date | str,
    lookback_days: int = 20,
) -> pl.DataFrame | None:
    """Calculate sector rotation metrics showing relative sector momentum.

    Aggregates stock returns by sector and calculates momentum over multiple
    time periods (5-day, 20-day, 60-day) to identify sector rotation patterns.

    Args:
        storage: PortfolioStorage instance for database access
        date: Date to calculate sector rotation for (YYYY-MM-DD format or date object)
        lookback_days: Maximum lookback period for momentum calculation (default: 20)
            Note: This determines data availability check, actual momentum uses fixed windows

    Returns:
        Polars DataFrame with columns:
            - sector: Sector name
            - momentum_5d: 5-day cumulative return (%)
            - momentum_20d: 20-day cumulative return (%)
            - num_stocks: Number of stocks in sector with data
            - avg_volume_ratio: Average RVOL across sector stocks
        Sorted by momentum_20d descending (strongest sectors first)
        Returns None if insufficient data available

    Example:
        >>> storage = get_storage()
        >>> rotation = get_sector_rotation(storage, "2025-01-15")
        >>> if rotation is not None:
        ...     for row in rotation.iter_rows(named=True):
        ...         print(f"{row['sector']}: {row['momentum_20d']:.2f}% momentum")
    """
    target_date = _parse_target_date(date)

    logger.debug(
        "get_sector_rotation_start",
        date=str(target_date),
        lookback_days=lookback_days,
    )

    # Get sector mapping for all symbols
    sector_data = _fetch_sector_mapping(storage)
    if sector_data is None or len(sector_data) == 0:
        logger.warning("get_sector_rotation_no_sector_data", date=str(target_date))
        return None

    # Calculate momentum period dates
    date_5d, date_20d = _calculate_momentum_dates(target_date)

    # Fetch returns data for all symbols
    returns_data = _fetch_symbol_returns(storage, target_date, date_5d, date_20d)
    if returns_data is None or len(returns_data) == 0:
        logger.warning("get_sector_rotation_no_returns_data", date=str(target_date))
        return None

    # Join sector information with returns data
    combined = returns_data.join(sector_data, on="symbol", how="inner")
    if len(combined) == 0:
        logger.warning("get_sector_rotation_no_joined_data", date=str(target_date))
        return None

    # Aggregate by sector
    sector_stats = _aggregate_sector_stats(combined)

    logger.info(
        "get_sector_rotation_complete",
        date=str(target_date),
        num_sectors=len(sector_stats),
        total_stocks=len(combined),
    )

    return sector_stats


def _fetch_sector_symbols(storage: PortfolioStorage, sector: str) -> pl.DataFrame | None:
    """Fetch all symbols in a specific sector.

    Args:
        storage: PortfolioStorage instance
        sector: Sector name to filter by

    Returns:
        DataFrame with symbol column, or None if no symbols found
    """
    sector_symbols_query = """
        SELECT DISTINCT ON (symbol)
            symbol
        FROM price_cache
        WHERE sector = ?
        ORDER BY symbol, cached_at DESC
    """
    return storage.query(sector_symbols_query, [sector])


def _fetch_sector_performance(
    storage: PortfolioStorage,
    symbols_list: list[str],
    sector: str,
    target_date: dt.date,
    date_5d: dt.date,
    date_20d: dt.date,
) -> pl.DataFrame | None:
    """Fetch performance metrics for symbols in a sector.

    Args:
        storage: PortfolioStorage instance
        symbols_list: List of symbols to fetch
        sector: Sector name for labeling
        target_date: Current date for performance calculation
        date_5d: Start date for 5-day returns
        date_20d: Start date for 20-day returns
    Returns:
        DataFrame with performance metrics per symbol, or None if no data
    """
    performance_query = """
        WITH price_now AS (
            SELECT symbol, close as close_now, volume
            FROM day_bars
            WHERE date = ?
                AND symbol IN (SELECT UNNEST(?))
        ),
        price_5d AS (
            SELECT symbol, close as close_5d
            FROM day_bars
            WHERE date >= ?
                AND date < ?
                AND symbol IN (SELECT UNNEST(?))
            QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date ASC) = 1
        ),
        price_20d AS (
            SELECT symbol, close as close_20d
            FROM day_bars
            WHERE date >= ?
                AND date < ?
                AND symbol IN (SELECT UNNEST(?))
            QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date ASC) = 1
        )
        SELECT
            p.symbol,
            ? as sector,
            p.close_now as close,
            p.volume,
            CASE
                WHEN p5.close_5d > 0 THEN ((p.close_now - p5.close_5d) / p5.close_5d) * 100
                ELSE NULL
            END as return_5d,
            CASE
                WHEN p20.close_20d > 0 THEN ((p.close_now - p20.close_20d) / p20.close_20d) * 100
                ELSE NULL
            END as return_20d
        FROM price_now p
        LEFT JOIN price_5d p5 ON p.symbol = p5.symbol
        LEFT JOIN price_20d p20 ON p.symbol = p20.symbol
        ORDER BY return_20d DESC NULLS LAST
    """
    # Cast list[str] to expected parameter type for UNNEST compatibility
    params: list[
        str | int | float | bool | dt.datetime | list[str | int | float | bool | None] | None
    ] = [
        target_date.isoformat(),
        cast(list[str | int | float | bool | None], symbols_list),
        date_5d.isoformat(),
        target_date.isoformat(),
        cast(list[str | int | float | bool | None], symbols_list),
        date_20d.isoformat(),
        target_date.isoformat(),
        cast(list[str | int | float | bool | None], symbols_list),
        sector,
    ]

    return storage.query(performance_query, params)


def get_sector_performance_detail(
    storage: PortfolioStorage,
    sector: str,
    date: dt.date | str,
    lookback_days: int = 20,
) -> pl.DataFrame | None:
    """Get detailed performance metrics for all stocks in a specific sector.

    Args:
        storage: PortfolioStorage instance for database access
        sector: Sector name (e.g., "Technology", "Healthcare")
        date: Date to calculate performance for (YYYY-MM-DD format or date object)
        lookback_days: Lookback period for momentum calculation (default: 20)

    Returns:
        Polars DataFrame with columns:
            - symbol: Stock symbol
            - sector: Sector name
            - return_5d: 5-day return (%)
            - return_20d: 20-day return (%)
            - volume: Current volume
            - close: Current close price
        Sorted by return_20d descending (best performers first)
        Returns None if no data available for sector

    Example:
        >>> storage = get_storage()
        >>> tech_detail = get_sector_performance_detail(storage, "Technology", "2025-01-15")
        >>> if tech_detail is not None:
        ...     print(f"Top tech stock: {tech_detail['symbol'][0]}")
    """
    target_date = _parse_target_date(date)

    logger.debug(
        "get_sector_performance_detail_start",
        sector=sector,
        date=str(target_date),
        lookback_days=lookback_days,
    )

    # Get symbols in this sector
    symbols_data = _fetch_sector_symbols(storage, sector)
    if symbols_data is None or len(symbols_data) == 0:
        logger.warning(
            "get_sector_performance_detail_no_symbols",
            sector=sector,
            date=str(target_date),
        )
        return None

    # Calculate date ranges
    date_5d, date_20d = _calculate_momentum_dates(target_date)

    # Get performance for these symbols
    symbols_list = symbols_data["symbol"].to_list()
    performance_data = _fetch_sector_performance(
        storage, symbols_list, sector, target_date, date_5d, date_20d
    )

    if performance_data is None or len(performance_data) == 0:
        logger.warning(
            "get_sector_performance_detail_no_data",
            sector=sector,
            date=str(target_date),
        )
        return None

    logger.info(
        "get_sector_performance_detail_complete",
        sector=sector,
        date=str(target_date),
        num_stocks=len(performance_data),
    )

    return performance_data
