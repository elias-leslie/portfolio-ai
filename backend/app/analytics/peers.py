"""Peer comparison analysis for trading intelligence.

This module provides functions for comparing a stock's performance against
its sector or industry peers to identify relative strength and positioning.
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def _parse_date(date: dt.date | str) -> dt.date:
    """Convert string date to date object if needed.

    Args:
        date: Date as YYYY-MM-DD string or date object

    Returns:
        Date object
    """
    if isinstance(date, str):
        return dt.datetime.strptime(date, "%Y-%m-%d").date()
    return date


def _calculate_date_ranges(target_date: dt.date) -> tuple[dt.date, dt.date]:
    """Calculate lookback date ranges for 5-day and 20-day periods.

    Args:
        target_date: The target date for comparison

    Returns:
        Tuple of (date_5d, date_20d) - Start dates for lookback periods
    """
    date_5d = target_date - dt.timedelta(days=7)
    date_20d = target_date - dt.timedelta(days=28)
    return date_5d, date_20d


def _fetch_peer_returns(
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
    date_5d, date_20d = _calculate_date_ranges(target_date)

    returns_query = """
        WITH price_now AS (
            SELECT ticker, close as close_now
            FROM day_bars
            WHERE date = ?
                AND ticker IN (SELECT UNNEST(?))
        ),
        price_5d AS (
            SELECT ticker, close as close_5d
            FROM day_bars
            WHERE date >= ?
                AND date < ?
                AND ticker IN (SELECT UNNEST(?))
            QUALIFY ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date ASC) = 1
        ),
        price_20d AS (
            SELECT ticker, close as close_20d
            FROM day_bars
            WHERE date >= ?
                AND date < ?
                AND ticker IN (SELECT UNNEST(?))
            QUALIFY ROW_NUMBER() OVER (PARTITION BY ticker ORDER BY date ASC) = 1
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
        LEFT JOIN price_5d p5 ON p.ticker = p5.ticker
        LEFT JOIN price_20d p20 ON p.ticker = p20.ticker
    """

    returns_data = storage.query(
        returns_query,
        [
            target_date,
            peer_tickers,
            date_5d,
            target_date,
            peer_tickers,
            date_20d,
            target_date,
            peer_tickers,
        ],
    )

    if returns_data is None or len(returns_data) == 0:
        return None

    return returns_data


def _calculate_peer_statistics(
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


def _build_comparison_result(
    ticker: str,
    group_name: str,
    group_by: str,
    ticker_metrics: dict[str, float | None],
    rank_metrics: dict[str, int | float | None],
) -> pl.DataFrame:
    """Build final comparison result DataFrame.

    Args:
        ticker: Stock ticker symbol
        group_name: Sector or industry name
        group_by: Grouping method ("sector" or "industry")
        ticker_metrics: Dictionary with ticker performance metrics
        rank_metrics: Dictionary with ranking metrics

    Returns:
        Polars DataFrame with comparison results
    """
    return pl.DataFrame(
        {
            "ticker": [ticker],
            group_by: [group_name],
            "return_5d": [ticker_metrics["return_5d"]],
            "return_20d": [ticker_metrics["return_20d"]],
            "sector_avg_5d": [ticker_metrics["sector_avg_5d"]],
            "sector_avg_20d": [ticker_metrics["sector_avg_20d"]],
            "relative_perf_5d": [ticker_metrics["relative_perf_5d"]],
            "relative_perf_20d": [ticker_metrics["relative_perf_20d"]],
            "peer_rank": [rank_metrics["peer_rank"]],
            "peer_count": [rank_metrics["peer_count"]],
            "percentile": [rank_metrics["percentile"]],
        }
    )


def _validate_and_get_group_data(
    storage: PortfolioStorage,
    ticker: str,
    group_by: str,
) -> tuple[str | None, list[str] | None]:
    """Helper function to validate group_by and get group data for a ticker.

    Returns:
        Tuple of (group_name, peer_tickers) or (None, None) if validation fails
    """
    # Validate group_by parameter
    if group_by not in ["sector", "industry"]:
        logger.error(
            "invalid_group_by",
            group_by=group_by,
            allowed_values=["sector", "industry"],
        )
        return None, None

    # Get the ticker's sector/industry from price_cache
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


def get_peer_comparison(
    storage: PortfolioStorage,
    ticker: str,
    date: dt.date | str,
    lookback_days: int = 20,
    group_by: str = "sector",
) -> pl.DataFrame | None:
    """Compare a ticker's performance against its sector or industry peers.

    Calculates relative performance metrics showing how the ticker ranks
    within its peer group over different time periods.

    Args:
        storage: PortfolioStorage instance for database access
        ticker: Stock ticker symbol (e.g., "AAPL")
        date: Date to calculate peer comparison for (YYYY-MM-DD format or date object)
        lookback_days: Lookback period for momentum calculation (default: 20)
        group_by: Grouping method - "sector" or "industry" (default: "sector")

    Returns:
        Polars DataFrame with columns:
            - ticker: Stock ticker symbol
            - sector: Sector name (or industry if group_by="industry")
            - return_5d: 5-day return (%)
            - return_20d: 20-day return (%)
            - sector_avg_5d: Average 5-day return for peer group (%)
            - sector_avg_20d: Average 20-day return for peer group (%)
            - relative_perf_5d: Relative performance vs peers over 5 days (%)
            - relative_perf_20d: Relative performance vs peers over 20 days (%)
            - peer_rank: Rank within peer group (1 = best performer)
            - peer_count: Total number of peers in group
            - percentile: Percentile rank (0-100, higher is better)
        Returns None if ticker not found or insufficient data

    Example:
        >>> storage = get_storage()
        >>> comparison = get_peer_comparison(storage, "AAPL", "2025-01-15")
        >>> if comparison is not None:
        ...     row = comparison[0]
        ...     print(f"AAPL ranks #{row['peer_rank']} out of {row['peer_count']} peers")
    """
    target_date = _parse_date(date)

    logger.debug(
        "get_peer_comparison_start",
        ticker=ticker,
        date=str(target_date),
        lookback_days=lookback_days,
        group_by=group_by,
    )

    # Get group data and peer tickers
    group_name, peer_tickers = _validate_and_get_group_data(storage, ticker, group_by)
    if group_name is None or peer_tickers is None:
        logger.warning(
            "get_peer_comparison_failed",
            ticker=ticker,
            date=str(target_date),
            group_by=group_by,
        )
        return None

    logger.debug(
        "get_peer_comparison_peers_found",
        ticker=ticker,
        group_name=group_name,
        peer_count=len(peer_tickers),
    )

    # Fetch returns data
    returns_data = _fetch_peer_returns(storage, target_date, peer_tickers)
    if returns_data is None:
        logger.warning(
            "get_peer_comparison_no_returns_data",
            ticker=ticker,
            date=str(target_date),
        )
        return None

    # Calculate statistics and rankings
    stats = _calculate_peer_statistics(returns_data, ticker)
    if stats is None:
        logger.warning(
            "get_peer_comparison_no_valid_returns",
            ticker=ticker,
            date=str(target_date),
        )
        return None

    ticker_metrics, rank_metrics = stats

    # Build result
    result = _build_comparison_result(ticker, group_name, group_by, ticker_metrics, rank_metrics)

    logger.info(
        "get_peer_comparison_complete",
        ticker=ticker,
        date=str(target_date),
        group_by=group_by,
        group_name=group_name,
        peer_rank=rank_metrics["peer_rank"],
        peer_count=rank_metrics["peer_count"],
        percentile=rank_metrics["percentile"],
    )

    return result


def get_peer_group_detail(
    storage: PortfolioStorage,
    ticker: str,
    date: dt.date | str,
    lookback_days: int = 20,
    group_by: str = "sector",
    top_n: int = 10,
) -> pl.DataFrame | None:
    """Get detailed performance data for all peers in a ticker's group.

    Returns ranked list of all stocks in the same sector/industry as the
    target ticker, showing their relative performance.

    Args:
        storage: PortfolioStorage instance for database access
        ticker: Stock ticker symbol to find peers for (e.g., "AAPL")
        date: Date to calculate peer performance for (YYYY-MM-DD format or date object)
        lookback_days: Lookback period for momentum calculation (default: 20)
        group_by: Grouping method - "sector" or "industry" (default: "sector")
        top_n: Number of top/bottom performers to highlight (default: 10)

    Returns:
        Polars DataFrame with columns:
            - ticker: Stock ticker symbol
            - sector: Sector name (or industry if group_by="industry")
            - return_5d: 5-day return (%)
            - return_20d: 20-day return (%)
            - rank: Rank within peer group (1 = best performer)
            - is_target: Boolean indicating if this is the target ticker
        Sorted by return_20d descending (best performers first)
        Returns None if ticker not found or insufficient data

    Example:
        >>> storage = get_storage()
        >>> peers = get_peer_group_detail(storage, "AAPL", "2025-01-15", top_n=5)
        >>> if peers is not None:
        ...     print("Top 5 performers in AAPL's sector:")
        ...     for row in peers.head(5).iter_rows(named=True):
        ...         print(f"{row['ticker']}: {row['return_20d']:.2f}%")
    """
    target_date = _parse_date(date)

    logger.debug(
        "get_peer_group_detail_start",
        ticker=ticker,
        date=str(target_date),
        group_by=group_by,
    )

    # Get group data and peer tickers
    group_name, peer_tickers = _validate_and_get_group_data(storage, ticker, group_by)
    if group_name is None or peer_tickers is None:
        logger.warning(
            "get_peer_group_detail_failed",
            ticker=ticker,
            date=str(target_date),
            group_by=group_by,
        )
        return None

    # Fetch returns data
    returns_data = _fetch_peer_returns(storage, target_date, peer_tickers)
    if returns_data is None:
        logger.warning(
            "get_peer_group_detail_no_returns_data",
            ticker=ticker,
            date=str(target_date),
        )
        return None

    # Filter, annotate, and rank
    valid_returns = returns_data.filter(pl.col("return_20d").is_not_null()).with_columns(
        [
            pl.lit(group_name).alias(group_by),
            (pl.col("ticker") == ticker).alias("is_target"),
        ]
    )

    ranked = (
        valid_returns.sort("return_20d", descending=True)
        .with_row_index(name="rank", offset=1)
        .select(
            [
                "ticker",
                group_by,
                "return_5d",
                "return_20d",
                "rank",
                "is_target",
            ]
        )
    )

    logger.info(
        "get_peer_group_detail_complete",
        ticker=ticker,
        date=str(target_date),
        group_by=group_by,
        group_name=group_name,
        peer_count=len(ranked),
    )

    return ranked
