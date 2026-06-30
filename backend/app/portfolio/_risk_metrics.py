"""Local risk metric computation (beta and volatility) from historical day bars."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import sqrt

import numpy as np
import polars as pl

from ..constants import TRADING_DAYS_PER_YEAR
from ..logging_config import get_logger
from ..storage import PortfolioStorage

logger = get_logger(__name__)

_DEFAULT_MARKET_BENCHMARK = "SPY"
_DEFAULT_LOOKBACK_DAYS = 90


def _build_return_series(df: pl.DataFrame, symbol_value: str, return_col_name: str) -> pl.DataFrame:
    """Filter, sort, and compute percent-change returns for a single symbol.

    Args:
        df: Raw DataFrame containing symbol, date, and close columns
        symbol_value: Ticker symbol to filter on
        return_col_name: Name to assign to the percent-change column

    Returns:
        DataFrame with date and the named return column, nulls dropped
    """
    return (
        df.filter(pl.col("symbol") == symbol_value)
        .sort("date")
        .with_columns(pl.col("close").pct_change().alias(return_col_name))
        .drop_nulls([return_col_name])
        .select(["date", return_col_name])
    )


def compute_local_risk_metrics(
    symbol: str,
    storage: PortfolioStorage,
    market_benchmark: str = _DEFAULT_MARKET_BENCHMARK,
    volatility_lookback_days: int = _DEFAULT_LOOKBACK_DAYS,
) -> tuple[float | None, float | None]:
    """Compute beta and volatility from local historical data.

    Args:
        symbol: Stock ticker symbol
        storage: PortfolioStorage instance to query day_bars
        market_benchmark: Benchmark ticker (default SPY)
        volatility_lookback_days: Number of days to look back

    Returns:
        Tuple of (beta, volatility) — either value may be None if insufficient data
    """
    start_date = datetime.now(UTC).date() - timedelta(days=volatility_lookback_days * 2)
    df = storage.query(
        """
        SELECT symbol, date, close
        FROM day_bars
        WHERE symbol IN (?, ?)
          AND date >= ?
        ORDER BY date ASC
        """,
        [symbol, market_benchmark, start_date.isoformat()],
    )

    if df.is_empty():
        logger.debug("no_day_bars_data", symbol=symbol, benchmark=market_benchmark)
        return (None, None)

    try:
        symbol_df = _build_return_series(df, symbol, "symbol_return")
        market_df = _build_return_series(df, market_benchmark, "market_return")
    except pl.exceptions.ComputeError:
        logger.warning("return_series_compute_error", symbol=symbol, exc_info=True)
        return (None, None)

    if symbol_df.is_empty() or market_df.is_empty():
        logger.debug(
            "empty_return_series",
            symbol_empty=symbol_df.is_empty(),
            market_empty=market_df.is_empty(),
        )
        return (None, None)

    joined = symbol_df.join(market_df, on="date", how="inner")
    if joined.height < 5:
        logger.debug(
            "Insufficient overlapping rows (%d < 5) for symbol=%s", joined.height, symbol
        )
        return (None, None)

    symbol_returns = joined["symbol_return"].to_numpy()
    market_returns = joined["market_return"].to_numpy()

    # Filter non-finite values
    mask = np.isfinite(symbol_returns) & np.isfinite(market_returns)
    symbol_returns = symbol_returns[mask]
    market_returns = market_returns[mask]

    if symbol_returns.size < 5 or market_returns.size < 5:
        logger.debug(
            "Insufficient finite return values (%d) for symbol=%s", symbol_returns.size, symbol
        )
        return (None, None)

    # Volatility: annualized standard deviation of daily returns
    symbol_std = np.std(symbol_returns, ddof=1)
    volatility = float(symbol_std * sqrt(TRADING_DAYS_PER_YEAR))
    if not np.isfinite(volatility):
        volatility = None

    market_variance = float(np.var(market_returns, ddof=1))
    if market_variance <= 1e-10 or np.isnan(market_variance):  # use tolerance instead of == 0
        beta = None
    else:
        covariance = float(np.cov(symbol_returns, market_returns, ddof=1)[0][1])
        beta = covariance / market_variance

    return (beta, volatility)
