"""Peer comparison calculation algorithms.

This module contains the core algorithms for peer analysis:
- Fetching peer return data from database
- Calculating statistical metrics and rankings
- Validating and retrieving peer group membership
"""

from __future__ import annotations

import datetime as dt
from typing import cast

import polars as pl

from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def calculate_date_ranges(target_date: dt.date) -> tuple[dt.date, dt.date]:
    """Calculate lookback date ranges for 5-day and 20-day periods.

    Args:
        target_date: The target date for comparison

    Returns:
        Tuple of (date_5d, date_20d) - Start dates for lookback periods
    """
    date_5d = target_date - dt.timedelta(days=7)
    date_20d = target_date - dt.timedelta(days=28)
    return date_5d, date_20d


def fetch_peer_returns(
    storage: PortfolioStorage,
    target_date: dt.date,
    peer_tickers: list[str],
) -> pl.DataFrame | None:
    """Fetch returns data for peer tickers over multiple time periods.

    Args:
        storage: PortfolioStorage instance for database access
        target_date: Date to calculate returns for
        peer_tickers: List of peer ticker symbols

    Returns:
        Polars DataFrame with ticker, return_5d, return_20d columns
        Returns None if no data available
    """
    date_5d, date_20d = calculate_date_ranges(target_date)

    returns_query = """
        WITH price_now AS (
            SELECT symbol, close as close_now
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
            p.ticker,
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
    # Cast list[str] to expected parameter type for UNNEST compatibility
    params: list[
        str | int | float | bool | dt.datetime | list[str | int | float | bool | None] | None
    ] = [
        target_date.isoformat(),
        cast(list[str | int | float | bool | None], peer_tickers),
        date_5d.isoformat(),
        target_date.isoformat(),
        cast(list[str | int | float | bool | None], peer_tickers),
        date_20d.isoformat(),
        target_date.isoformat(),
        cast(list[str | int | float | bool | None], peer_tickers),
    ]

    returns_data = storage.query(returns_query, params)

    if returns_data is None or len(returns_data) == 0:
        return None

    return returns_data


def calculate_peer_statistics(
    returns_data: pl.DataFrame,
    ticker: str,
) -> tuple[dict[str, float | None], dict[str, int | float | None]] | None:
    """Calculate peer comparison statistics and rankings.

    Args:
        returns_data: DataFrame with ticker returns
        ticker: Target ticker symbol

    Returns:
        Tuple of (ticker_metrics, rank_metrics) or None if insufficient data
        ticker_metrics: Dict with return_5d, return_20d, sector_avg_5d, sector_avg_20d,
                       relative_perf_5d, relative_perf_20d
        rank_metrics: Dict with peer_rank, peer_count, percentile
    """
    # Calculate sector averages
    sector_stats = returns_data.select(
        [
            pl.col("return_5d").mean().alias("sector_avg_5d"),
            pl.col("return_20d").mean().alias("sector_avg_20d"),
        ]
    )

    sector_avg_5d = sector_stats["sector_avg_5d"][0]
    sector_avg_20d = sector_stats["sector_avg_20d"][0]

    # Get target ticker's returns
    target_ticker_data = returns_data.filter(pl.col("ticker") == ticker)
    if len(target_ticker_data) == 0:
        return None

    ticker_return_5d = target_ticker_data["return_5d"][0]
    ticker_return_20d = target_ticker_data["return_20d"][0]

    # Calculate relative performance
    relative_perf_5d = None
    relative_perf_20d = None

    if ticker_return_5d is not None and sector_avg_5d is not None:
        relative_perf_5d = ticker_return_5d - sector_avg_5d

    if ticker_return_20d is not None and sector_avg_20d is not None:
        relative_perf_20d = ticker_return_20d - sector_avg_20d

    # Calculate rank based on 20-day return
    valid_returns = returns_data.filter(pl.col("return_20d").is_not_null())

    if len(valid_returns) == 0:
        return None

    ranked = valid_returns.sort("return_20d", descending=True).with_row_index(name="rank", offset=1)

    ticker_rank_data = ranked.filter(pl.col("ticker") == ticker)

    if len(ticker_rank_data) == 0:
        peer_rank = None
        percentile = None
    else:
        peer_rank = int(ticker_rank_data["rank"][0])
        percentile = round((1 - (peer_rank - 1) / len(valid_returns)) * 100, 1)

    ticker_metrics = {
        "return_5d": ticker_return_5d,
        "return_20d": ticker_return_20d,
        "sector_avg_5d": sector_avg_5d,
        "sector_avg_20d": sector_avg_20d,
        "relative_perf_5d": relative_perf_5d,
        "relative_perf_20d": relative_perf_20d,
    }

    rank_metrics = {
        "peer_rank": peer_rank,
        "peer_count": len(valid_returns),
        "percentile": percentile,
    }

    return ticker_metrics, rank_metrics


def validate_and_get_group_data(
    storage: PortfolioStorage,
    ticker: str,
    group_by: str,
) -> tuple[str | None, list[str] | None]:
    """Validate group_by parameter and get group data for a ticker.

    Args:
        storage: PortfolioStorage instance
        ticker: Stock ticker symbol
        group_by: Grouping method ("sector" or "industry")

    Returns:
        Tuple of (group_name, peer_tickers) or (None, None) if validation fails
    """
    # Validate group_by parameter to prevent SQL injection
    if group_by not in ["sector", "industry"]:
        logger.error(
            "invalid_group_by",
            group_by=group_by,
            allowed_values=["sector", "industry"],
        )
        return None, None

    # Get the ticker's sector/industry from price_cache
    # validated: group_by from whitelist above
    ticker_group_query = f"""
        SELECT DISTINCT ON (symbol)
            symbol as ticker,
            {group_by}
        FROM price_cache
        WHERE symbol = ?
            AND {group_by} IS NOT NULL
            AND {group_by} != ''
        ORDER BY symbol, cached_at DESC
        LIMIT 1
    """

    ticker_group_data = storage.query(ticker_group_query, [ticker])

    if ticker_group_data is None or len(ticker_group_data) == 0:
        logger.warning("no_group_data_for_ticker", ticker=ticker, group_by=group_by)
        return None, None

    group_name = ticker_group_data[group_by][0]

    # Get all tickers in the same sector/industry
    # validated: group_by from whitelist above
    peers_query = f"""
        SELECT DISTINCT ON (symbol)
            symbol as ticker
        FROM price_cache
        WHERE {group_by} = ?
        ORDER BY symbol, cached_at DESC
    """

    peers_data = storage.query(peers_query, [group_name])

    if peers_data is None or len(peers_data) == 0:
        logger.warning("no_peers_found", ticker=ticker, group_name=group_name)
        return None, None

    peer_tickers = peers_data["ticker"].to_list()
    return group_name, peer_tickers
