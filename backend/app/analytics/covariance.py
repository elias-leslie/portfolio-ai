"""Portfolio covariance matrix calculations (GAP-020).

This module provides correct portfolio risk calculation using covariance matrix,
replacing the incorrect weighted-average approach that assumed rho=1.

Correct formula: sigma_portfolio = sqrt(w' * Cov * w)
where w = weight vector, Cov = covariance matrix

References:
- Markowitz, H. (1952). Portfolio Selection. Journal of Finance.
- Modern Portfolio Theory fundamentals
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

# Default lookback period (1 trading year)
DEFAULT_LOOKBACK_DAYS = 252
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

    # Build query for all symbols
    placeholders = ", ".join(f"${i + 1}" for i in range(len(symbols)))
    query = f"""
        WITH ordered_prices AS (
            SELECT
                symbol,
                date,
                close,
                LAG(close) OVER (PARTITION BY symbol ORDER BY date) as prev_close
            FROM day_bars
            WHERE symbol IN ({placeholders})
            ORDER BY symbol, date DESC
            LIMIT ${len(symbols) + 1}
        )
        SELECT
            symbol,
            date,
            (close - prev_close) / NULLIF(prev_close, 0) as daily_return
        FROM ordered_prices
        WHERE prev_close IS NOT NULL
        ORDER BY symbol, date
    """

    # Use a simpler query that works correctly
    query = f"""
        SELECT
            symbol,
            date,
            close
        FROM day_bars
        WHERE symbol IN ({placeholders})
          AND date >= CURRENT_DATE - INTERVAL '{lookback_days} days'
        ORDER BY symbol, date
    """

    result = storage.query(query, list(symbols))

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
        std_dev *= math.sqrt(252)

    return std_dev


def update_covariance_matrix(
    storage: PortfolioStorage,
    symbols: list[str],
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> int:
    """Calculate and store covariance matrix for given symbols.

    Args:
        storage: Database storage instance
        symbols: List of symbols
        lookback_days: Number of trading days for calculation

    Returns:
        Number of pairs updated
    """
    if len(symbols) < 2:
        logger.warning("covariance_matrix_skip", reason="need at least 2 symbols")
        return 0

    # Get daily returns for all symbols
    all_returns = calculate_daily_returns(storage, symbols, lookback_days)

    if len(all_returns) < 2:
        logger.warning(
            "covariance_matrix_insufficient_data",
            symbols=symbols,
            available=list(all_returns.keys()),
        )
        return 0

    # Calculate pairwise covariances
    pairs_updated = 0
    now = datetime.now(UTC)

    for i, symbol1 in enumerate(symbols):
        if symbol1 not in all_returns:
            continue

        for symbol2 in symbols[i:]:  # Include self-covariance (variance)
            if symbol2 not in all_returns:
                continue

            # Align returns by date
            aligned1, aligned2 = align_returns(all_returns[symbol1], all_returns[symbol2])

            if len(aligned1) < MIN_OBSERVATIONS:
                logger.debug(
                    "covariance_skip_pair",
                    symbol1=symbol1,
                    symbol2=symbol2,
                    observations=len(aligned1),
                    min_required=MIN_OBSERVATIONS,
                )
                continue

            # Calculate covariance and correlation
            cov, corr = calculate_pairwise_covariance(aligned1, aligned2)

            # Calculate individual volatilities
            vol1 = calculate_volatility(aligned1)
            vol2 = calculate_volatility(aligned2)

            # Store in database (both directions for easy lookup)
            upsert_query = """
                INSERT INTO portfolio_covariance
                    (symbol1, symbol2, covariance, correlation, volatility1, volatility2,
                     observation_count, lookback_days, calculated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (symbol1, symbol2)
                DO UPDATE SET
                    covariance = EXCLUDED.covariance,
                    correlation = EXCLUDED.correlation,
                    volatility1 = EXCLUDED.volatility1,
                    volatility2 = EXCLUDED.volatility2,
                    observation_count = EXCLUDED.observation_count,
                    lookback_days = EXCLUDED.lookback_days,
                    calculated_at = EXCLUDED.calculated_at
            """

            storage.execute(
                upsert_query,
                [symbol1, symbol2, cov, corr, vol1, vol2, len(aligned1), lookback_days, now],
            )
            pairs_updated += 1

            # Store reverse direction (symbol2, symbol1) if different
            if symbol1 != symbol2:
                storage.execute(
                    upsert_query,
                    [symbol2, symbol1, cov, corr, vol2, vol1, len(aligned1), lookback_days, now],
                )
                pairs_updated += 1

    logger.info(
        "covariance_matrix_updated",
        symbols_count=len(symbols),
        pairs_updated=pairs_updated,
        lookback_days=lookback_days,
    )

    return pairs_updated


def get_covariance_matrix(
    storage: PortfolioStorage,
    symbols: list[str],
    max_age_hours: int = 24,
) -> dict[tuple[str, str], float] | None:
    """Retrieve covariance matrix from database.

    Args:
        storage: Database storage instance
        symbols: List of symbols
        max_age_hours: Maximum age of cached data in hours

    Returns:
        Dictionary mapping (symbol1, symbol2) to covariance, or None if stale/missing
    """
    if len(symbols) < 2:
        return None

    placeholders = ", ".join(f"${i + 1}" for i in range(len(symbols)))
    cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)

    query = f"""
        SELECT symbol1, symbol2, covariance
        FROM portfolio_covariance
        WHERE symbol1 IN ({placeholders})
          AND symbol2 IN ({placeholders})
          AND calculated_at >= ${len(symbols) + 1}
    """

    result = storage.query(query, symbols + symbols + [cutoff_time])

    if result.is_empty():
        return None

    matrix: dict[tuple[str, str], float] = {}
    for row in result.iter_rows(named=True):
        matrix[(row["symbol1"], row["symbol2"])] = row["covariance"]

    # Check if we have all pairs
    expected_pairs = len(symbols) * len(symbols)
    if len(matrix) < expected_pairs:
        logger.debug(
            "covariance_matrix_incomplete",
            expected=expected_pairs,
            found=len(matrix),
        )
        return None

    return matrix


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
        return math.sqrt(variance) * math.sqrt(252)  # Annualize

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
        logger.warning("portfolio_variance_negative", variance=portfolio_variance)
        portfolio_variance = 0.0

    # Annualize: daily variance * 252 = annual variance
    annual_variance = portfolio_variance * 252
    portfolio_volatility = math.sqrt(annual_variance)

    return portfolio_volatility


def calculate_weight_hash(weights: dict[str, float]) -> str:
    """Create a hash of portfolio weights for cache key.

    Args:
        weights: Dictionary mapping symbol to weight

    Returns:
        MD5 hash of sorted weight string
    """
    # Sort by symbol for consistent hashing
    sorted_items = sorted(weights.items())
    weight_str = "|".join(f"{s}:{w:.6f}" for s, w in sorted_items)
    return hashlib.md5(weight_str.encode()).hexdigest()[:16]


def get_portfolio_volatility(
    storage: PortfolioStorage,
    weights: dict[str, float],
    portfolio_id: str = "default",
    force_recalculate: bool = False,
) -> tuple[float | None, float | None, float | None]:
    """Get portfolio volatility, using cache if available.

    Args:
        storage: Database storage instance
        weights: Dictionary mapping symbol to weight (should sum to ~1)
        portfolio_id: Identifier for the portfolio
        force_recalculate: Skip cache and recalculate

    Returns:
        Tuple of (portfolio_volatility, weighted_avg_volatility, diversification_benefit)
        Returns (None, None, None) if calculation fails
    """
    if not weights:
        return None, None, None

    symbols = list(weights.keys())
    weight_hash = calculate_weight_hash(weights)

    # Check cache first
    if not force_recalculate:
        cache_query = """
            SELECT portfolio_volatility, weighted_avg_volatility, diversification_benefit
            FROM portfolio_volatility_cache
            WHERE portfolio_id = $1 AND weight_hash = $2
              AND calculated_at >= NOW() - INTERVAL '24 hours'
        """
        cache_result = storage.query(cache_query, [portfolio_id, weight_hash])
        if not cache_result.is_empty():
            row = cache_result.to_dicts()[0]
            return (
                row["portfolio_volatility"],
                row["weighted_avg_volatility"],
                row["diversification_benefit"],
            )

    # Get or update covariance matrix
    cov_matrix = get_covariance_matrix(storage, symbols)
    if cov_matrix is None:
        # Update covariance matrix
        logger.info("portfolio_volatility_updating_covariance", symbols=symbols)
        update_covariance_matrix(storage, symbols)
        cov_matrix = get_covariance_matrix(storage, symbols, max_age_hours=1)

    if cov_matrix is None:
        logger.warning("portfolio_volatility_no_covariance", symbols=symbols)
        return None, None, None

    # Calculate portfolio volatility
    portfolio_vol = calculate_portfolio_volatility_from_covariance(weights, cov_matrix)

    # Calculate weighted average volatility (the incorrect old method)
    weighted_avg_vol = 0.0
    for symbol, weight in weights.items():
        # Get individual volatility from diagonal of covariance matrix
        variance = cov_matrix.get((symbol, symbol), 0.0)
        vol = math.sqrt(variance) * math.sqrt(252)  # Annualize
        weighted_avg_vol += weight * vol

    # Calculate diversification benefit
    div_benefit = 0.0
    if weighted_avg_vol > 0:
        div_benefit = 1.0 - (portfolio_vol / weighted_avg_vol)

    # Cache the result
    cache_insert = """
        INSERT INTO portfolio_volatility_cache
            (portfolio_id, weight_hash, portfolio_volatility, weighted_avg_volatility,
             diversification_benefit, calculated_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
        ON CONFLICT (portfolio_id, weight_hash)
        DO UPDATE SET
            portfolio_volatility = EXCLUDED.portfolio_volatility,
            weighted_avg_volatility = EXCLUDED.weighted_avg_volatility,
            diversification_benefit = EXCLUDED.diversification_benefit,
            calculated_at = EXCLUDED.calculated_at
    """
    storage.execute(
        cache_insert,
        [portfolio_id, weight_hash, portfolio_vol, weighted_avg_vol, div_benefit],
    )

    logger.info(
        "portfolio_volatility_calculated",
        portfolio_id=portfolio_id,
        portfolio_vol=f"{portfolio_vol:.4f}",
        weighted_avg_vol=f"{weighted_avg_vol:.4f}",
        diversification_benefit=f"{div_benefit:.2%}",
    )

    return portfolio_vol, weighted_avg_vol, div_benefit
