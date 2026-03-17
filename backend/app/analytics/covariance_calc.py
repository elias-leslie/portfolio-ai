"""Portfolio covariance calculation functions (GAP-020).

This module provides the core calculation functions for covariance and volatility.
"""

from __future__ import annotations

import math
from datetime import date
from typing import TYPE_CHECKING

from app.constants import TRADING_DAYS_PER_YEAR

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

# Default lookback period (1 trading year)
DEFAULT_LOOKBACK_DAYS = TRADING_DAYS_PER_YEAR
# Minimum observations required for reliable covariance
MIN_OBSERVATIONS = 60


def calculate_daily_returns(
    storage: PortfolioStorage,
    symbols: list[str],
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, list[tuple[date, float]]]:
    """Calculate daily returns for each symbol from day_bars.

    Args:
        storage: Database storage instance
        symbols: List of symbols
        lookback_days: Number of trading days to look back

    Returns:
        Dictionary mapping symbol to list of (date, return) tuples
        Returns are simple returns: (P_t - P_{t-1}) / P_{t-1}
    """
    if not symbols:
        return {}

    # Build query for all symbols — reserve $1 for lookback_days
    placeholders = ", ".join(f"${i + 2}" for i in range(len(symbols)))

    query = f"""
        SELECT
            symbol,
            date,
            close
        FROM day_bars
        WHERE symbol IN ({placeholders})
          AND date >= CURRENT_DATE - make_interval(days => $1)
        ORDER BY symbol, date
    """

    result = storage.query(query, [lookback_days, *symbols])

    if result.is_empty():
        return {}

    # Organize by symbol and calculate returns
    symbol_prices: dict[str, list[tuple[date, float]]] = {}
    for row in result.iter_rows(named=True):
        symbol = row["symbol"]
        price_date = row["date"]
        close = row["close"]

        if symbol not in symbol_prices:
            symbol_prices[symbol] = []
        symbol_prices[symbol].append((price_date, close))

    # Calculate returns for each symbol
    symbol_returns: dict[str, list[tuple[date, float]]] = {}
    for symbol, prices in symbol_prices.items():
        # Sort by date
        prices.sort(key=lambda x: x[0])
        returns = []
        for i in range(1, len(prices)):
            prev_price = prices[i - 1][1]
            curr_price = prices[i][1]
            curr_date = prices[i][0]
            if prev_price > 0:
                daily_return = (curr_price - prev_price) / prev_price
                returns.append((curr_date, daily_return))
        symbol_returns[symbol] = returns

    return symbol_returns


def calculate_pairwise_covariance(
    returns1: list[float],
    returns2: list[float],
) -> tuple[float, float]:
    """Calculate covariance and correlation between two return series.

    Args:
        returns1: First return series
        returns2: Second return series (must be aligned by date)

    Returns:
        Tuple of (covariance, correlation)
    """
    n = len(returns1)
    if n < 2 or len(returns2) != n:
        return 0.0, 0.0

    # Calculate means
    mean1 = sum(returns1) / n
    mean2 = sum(returns2) / n

    # Calculate variances and covariance
    var1 = sum((r - mean1) ** 2 for r in returns1) / n
    var2 = sum((r - mean2) ** 2 for r in returns2) / n
    cov = sum((r1 - mean1) * (r2 - mean2) for r1, r2 in zip(returns1, returns2, strict=True)) / n

    # Calculate standard deviations
    std1 = math.sqrt(var1) if var1 > 0 else 0.0
    std2 = math.sqrt(var2) if var2 > 0 else 0.0

    # Correlation
    correlation = cov / (std1 * std2) if std1 > 0 and std2 > 0 else 0.0

    return cov, correlation


def align_returns(
    returns1: list[tuple[date, float]],
    returns2: list[tuple[date, float]],
) -> tuple[list[float], list[float]]:
    """Align two return series by date, keeping only common dates.

    Args:
        returns1: First return series with dates
        returns2: Second return series with dates

    Returns:
        Tuple of (aligned_returns1, aligned_returns2)
    """
    dates1 = dict(returns1)
    dates2 = dict(returns2)

    common_dates = set(dates1.keys()) & set(dates2.keys())

    if not common_dates:
        return [], []

    sorted_dates = sorted(common_dates)
    aligned1 = [dates1[d] for d in sorted_dates]
    aligned2 = [dates2[d] for d in sorted_dates]

    return aligned1, aligned2


def calculate_volatility(returns: list[float], annualize: bool = True) -> float:
    """Calculate volatility (standard deviation) of returns.

    Args:
        returns: List of return values
        annualize: Whether to annualize (multiply by sqrt(252))

    Returns:
        Volatility as a decimal (0.25 = 25%)
    """
    n = len(returns)
    if n < 2:
        return 0.0

    mean_return = sum(returns) / n
    variance = sum((r - mean_return) ** 2 for r in returns) / n
    std_dev = math.sqrt(variance)

    if annualize:
        std_dev *= math.sqrt(TRADING_DAYS_PER_YEAR)

    return std_dev


def calculate_portfolio_volatility_from_covariance(
    weights: dict[str, float],
    covariance_matrix: dict[tuple[str, str], float],
) -> float:
    """Calculate portfolio volatility using covariance matrix.

    Formula: sigma_portfolio = sqrt(w' * Cov * w)

    Args:
        weights: Dictionary mapping symbol to portfolio weight (must sum to 1)
        covariance_matrix: Dictionary mapping (symbol1, symbol2) to covariance

    Returns:
        Portfolio volatility (annualized, as decimal)
    """
    symbols = list(weights.keys())
    n = len(symbols)

    if n == 0:
        return 0.0

    if n == 1:
        # Single asset: volatility is sqrt of variance
        symbol = symbols[0]
        variance = covariance_matrix.get((symbol, symbol), 0.0)
        return math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR)  # Annualize

    # Calculate w' Σ w
    portfolio_variance = 0.0
    for symbol1 in symbols:
        w1 = weights[symbol1]
        for symbol2 in symbols:
            w2 = weights[symbol2]
            cov = covariance_matrix.get((symbol1, symbol2), 0.0)
            portfolio_variance += w1 * w2 * cov

    if portfolio_variance < 0:
        # This shouldn't happen with valid data, but handle edge case
        portfolio_variance = 0.0

    # Annualize: daily variance * TRADING_DAYS_PER_YEAR = annual variance
    annual_variance = portfolio_variance * TRADING_DAYS_PER_YEAR
    portfolio_volatility = math.sqrt(annual_variance)

    return portfolio_volatility
