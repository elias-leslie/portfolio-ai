"""Portfolio covariance database storage operations (GAP-020).

This module handles database storage and retrieval for covariance matrices
and portfolio volatility calculations.
"""

from __future__ import annotations

import hashlib
import math
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.analytics.covariance_calc import (
    DEFAULT_LOOKBACK_DAYS,
    MIN_OBSERVATIONS,
    align_returns,
    calculate_daily_returns,
    calculate_pairwise_covariance,
    calculate_portfolio_volatility_from_covariance,
    calculate_volatility,
)
from app.constants import TRADING_DAYS_PER_YEAR
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


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

    symbol1_placeholders = ", ".join(f"${i + 1}" for i in range(len(symbols)))
    symbol2_placeholders = ", ".join(
        f"${len(symbols) + i + 1}" for i in range(len(symbols))
    )
    cutoff_param = len(symbols) * 2 + 1
    cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)

    query = f"""
        SELECT symbol1, symbol2, covariance
        FROM portfolio_covariance
        WHERE symbol1 IN ({symbol1_placeholders})
          AND symbol2 IN ({symbol2_placeholders})
          AND calculated_at >= ${cutoff_param}
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
        vol = math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR)  # Annualize
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
