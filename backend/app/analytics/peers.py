"""Peer comparison analysis for trading intelligence.

This module provides functions for comparing a stock's performance against
its sector or industry peers to identify relative strength and positioning.

The implementation uses algorithms from peer_algorithms module for:
- Fetching peer return data
- Calculating statistical metrics
- Validating group membership
"""

from __future__ import annotations

import datetime as dt

import polars as pl

from app.analytics.peer_algorithms import (
    calculate_peer_statistics,
    fetch_peer_returns,
    validate_and_get_group_data,
)
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


def _build_comparison_result(
    symbol: str,
    group_name: str,
    group_by: str,
    symbol_metrics: dict[str, float | None],
    rank_metrics: dict[str, int | float | None],
) -> pl.DataFrame:
    """Build final comparison result DataFrame.

    Args:
        symbol: Stock symbol
        group_name: Sector or industry name
        group_by: Grouping method ("sector" or "industry")
        symbol_metrics: Dictionary with symbol performance metrics
        rank_metrics: Dictionary with ranking metrics

    Returns:
        Polars DataFrame with comparison results
    """
    return pl.DataFrame(
        {
            "symbol": [symbol],
            group_by: [group_name],
            "return_5d": [symbol_metrics["return_5d"]],
            "return_20d": [symbol_metrics["return_20d"]],
            "sector_avg_5d": [symbol_metrics["sector_avg_5d"]],
            "sector_avg_20d": [symbol_metrics["sector_avg_20d"]],
            "relative_perf_5d": [symbol_metrics["relative_perf_5d"]],
            "relative_perf_20d": [symbol_metrics["relative_perf_20d"]],
            "peer_rank": [rank_metrics["peer_rank"]],
            "peer_count": [rank_metrics["peer_count"]],
            "percentile": [rank_metrics["percentile"]],
        }
    )


def get_peer_comparison(
    storage: PortfolioStorage,
    symbol: str,
    date: dt.date | str,
    lookback_days: int = 20,
    group_by: str = "sector",
) -> pl.DataFrame | None:
    """Compare a symbol's performance against its sector or industry peers.

    Calculates relative performance metrics showing how the symbol ranks
    within its peer group over different time periods.

    Args:
        storage: PortfolioStorage instance for database access
        symbol: Stock symbol (e.g., "AAPL")
        date: Date to calculate peer comparison for (YYYY-MM-DD format or date object)
        lookback_days: Lookback period for momentum calculation (default: 20)
        group_by: Grouping method - "sector" or "industry" (default: "sector")

    Returns:
        Polars DataFrame with columns:
            - symbol: Stock symbol
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
        Returns None if symbol not found or insufficient data

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
        symbol=symbol,
        date=str(target_date),
        lookback_days=lookback_days,
        group_by=group_by,
    )

    # Get group data and peer symbols
    group_name, peer_symbols = validate_and_get_group_data(storage, symbol, group_by)
    if group_name is None or peer_symbols is None:
        logger.warning(
            "get_peer_comparison_failed",
            symbol=symbol,
            date=str(target_date),
            group_by=group_by,
        )
        return None

    logger.debug(
        "get_peer_comparison_peers_found",
        symbol=symbol,
        group_name=group_name,
        peer_count=len(peer_symbols),
    )

    # Fetch returns data
    returns_data = fetch_peer_returns(storage, target_date, peer_symbols)
    if returns_data is None:
        logger.warning(
            "get_peer_comparison_no_returns_data",
            symbol=symbol,
            date=str(target_date),
        )
        return None

    # Calculate statistics and rankings
    stats = calculate_peer_statistics(returns_data, symbol)
    if stats is None:
        logger.warning(
            "get_peer_comparison_no_valid_returns",
            symbol=symbol,
            date=str(target_date),
        )
        return None

    symbol_metrics, rank_metrics = stats

    # Build result
    result = _build_comparison_result(symbol, group_name, group_by, symbol_metrics, rank_metrics)

    logger.info(
        "get_peer_comparison_complete",
        symbol=symbol,
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
    symbol: str,
    date: dt.date | str,
    lookback_days: int = 20,
    group_by: str = "sector",
    top_n: int = 10,
) -> pl.DataFrame | None:
    """Get detailed performance data for all peers in a symbol's group.

    Returns ranked list of all stocks in the same sector/industry as the
    target symbol, showing their relative performance.

    Args:
        storage: PortfolioStorage instance for database access
        symbol: Stock symbol to find peers for (e.g., "AAPL")
        date: Date to calculate peer performance for (YYYY-MM-DD format or date object)
        lookback_days: Lookback period for momentum calculation (default: 20)
        group_by: Grouping method - "sector" or "industry" (default: "sector")
        top_n: Number of top/bottom performers to highlight (default: 10)

    Returns:
        Polars DataFrame with columns:
            - symbol: Stock symbol
            - sector: Sector name (or industry if group_by="industry")
            - return_5d: 5-day return (%)
            - return_20d: 20-day return (%)
            - rank: Rank within peer group (1 = best performer)
            - is_target: Boolean indicating if this is the target symbol
        Sorted by return_20d descending (best performers first)
        Returns None if symbol not found or insufficient data

    Example:
        >>> storage = get_storage()
        >>> peers = get_peer_group_detail(storage, "AAPL", "2025-01-15", top_n=5)
        >>> if peers is not None:
        ...     print("Top 5 performers in AAPL's sector:")
        ...     for row in peers.head(5).iter_rows(named=True):
        ...         print(f"{row['symbol']}: {row['return_20d']:.2f}%")
    """
    target_date = _parse_date(date)

    logger.debug(
        "get_peer_group_detail_start",
        symbol=symbol,
        date=str(target_date),
        group_by=group_by,
    )

    # Get group data and peer symbols
    group_name, peer_symbols = validate_and_get_group_data(storage, symbol, group_by)
    if group_name is None or peer_symbols is None:
        logger.warning(
            "get_peer_group_detail_failed",
            symbol=symbol,
            date=str(target_date),
            group_by=group_by,
        )
        return None

    # Fetch returns data
    returns_data = fetch_peer_returns(storage, target_date, peer_symbols)
    if returns_data is None:
        logger.warning(
            "get_peer_group_detail_no_returns_data",
            symbol=symbol,
            date=str(target_date),
        )
        return None

    # Filter, annotate, and rank
    valid_returns = returns_data.filter(pl.col("return_20d").is_not_null()).with_columns(
        [
            pl.lit(group_name).alias(group_by),
            (pl.col("symbol") == symbol).alias("is_target"),
        ]
    )

    ranked = (
        valid_returns.sort("return_20d", descending=True)
        .with_row_index(name="rank", offset=1)
        .select(
            [
                "symbol",
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
        symbol=symbol,
        date=str(target_date),
        group_by=group_by,
        group_name=group_name,
        peer_count=len(ranked),
    )

    return ranked
