"""Portfolio return and performance calculations.

This module handles calculations related to portfolio value, gains,
and position performance metrics.

GAP-020 FIX: Portfolio volatility now uses proper covariance matrix calculation
instead of incorrect weighted-average approach that assumed rho=1.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .models import PortfolioValue, Position, PositionPerformance, PriceData

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


def calculate_portfolio_value(
    positions: list[Position],
    price_data: dict[str, PriceData],
) -> PortfolioValue:
    """Calculate total portfolio value and P&L.

    Args:
        positions: List of portfolio positions
        price_data: Dictionary mapping symbol to PriceData

    Returns:
        PortfolioValue with total value, cost basis, and gains
    """
    total_value = 0.0
    total_cost_basis = 0.0

    for position in positions:
        price = price_data.get(position.symbol)
        if not price:
            logger.warning(f"No price data for {position.symbol}, skipping from value calculation")
            continue

        # Skip positions with price errors
        if price.error:
            logger.warning(
                f"Price error for {position.symbol}: {price.error}, skipping from value calculation"
            )
            continue

        # Calculate position value
        position_value = position.shares * price.price
        position_cost = position.shares * position.cost_basis

        # Handle long/short positions
        if position.position_type == "short":
            position_value = -position_value
            position_cost = -position_cost

        total_value += position_value
        total_cost_basis += position_cost

    total_gain = total_value - total_cost_basis
    total_gain_pct = (total_gain / total_cost_basis * 100) if total_cost_basis != 0 else 0.0

    return PortfolioValue(
        total_value=total_value,
        total_cost_basis=total_cost_basis,
        total_gain=total_gain,
        total_gain_pct=total_gain_pct,
    )


def calculate_portfolio_beta(
    positions: list[Position],
    price_data: dict[str, PriceData],
) -> float | None:
    """Calculate portfolio beta (weighted average of position betas).

    Args:
        positions: List of portfolio positions
        price_data: Dictionary mapping symbol to PriceData

    Returns:
        Portfolio beta, or None if insufficient data
    """
    total_value = 0.0
    weighted_beta_sum = 0.0

    for position in positions:
        price = price_data.get(position.symbol)
        if not price or price.beta is None or price.error:
            continue

        position_value = position.shares * price.price
        total_value += position_value
        weighted_beta_sum += position_value * price.beta

    if total_value == 0:
        return None

    return weighted_beta_sum / total_value


def calculate_portfolio_volatility(
    positions: list[Position],
    price_data: dict[str, PriceData],
    storage: PortfolioStorage | None = None,
) -> float | None:
    """Calculate portfolio volatility using covariance matrix (GAP-020 fix).

    Uses proper formula: sigma_portfolio = sqrt(w' * Cov * w)
    Falls back to weighted average if storage unavailable or covariance fails.

    Args:
        positions: List of portfolio positions
        price_data: Dictionary mapping symbol to PriceData
        storage: Optional storage for covariance matrix lookup

    Returns:
        Portfolio volatility (annualized), or None if insufficient data
    """
    # Calculate position weights
    total_value = 0.0
    position_values: dict[str, float] = {}

    for position in positions:
        price = price_data.get(position.symbol)
        if not price or price.error:
            continue

        position_value = position.shares * price.price
        position_values[position.symbol] = position_value
        total_value += position_value

    if total_value == 0:
        return None

    # Calculate weights
    weights = {symbol: value / total_value for symbol, value in position_values.items()}

    # Try covariance-based calculation if storage available
    if storage is not None and len(weights) >= 2:
        try:
            from ..analytics.covariance import get_portfolio_volatility  # noqa: PLC0415

            portfolio_vol, weighted_avg_vol, div_benefit = get_portfolio_volatility(
                storage,
                weights,
                portfolio_id="portfolio",
            )

            if portfolio_vol is not None:
                logger.debug(
                    "portfolio_volatility_covariance",
                    portfolio_vol=f"{portfolio_vol:.4f}",
                    weighted_avg=f"{weighted_avg_vol:.4f}" if weighted_avg_vol else "N/A",
                    div_benefit=f"{div_benefit:.2%}" if div_benefit else "N/A",
                )
                return portfolio_vol
        except Exception as e:
            logger.warning("portfolio_volatility_covariance_failed", error=str(e))

    # Fallback to weighted average (incorrect but better than nothing)
    return _calculate_weighted_avg_volatility(positions, price_data)


def _calculate_weighted_avg_volatility(
    positions: list[Position],
    price_data: dict[str, PriceData],
) -> float | None:
    """Calculate portfolio volatility using simple weighted average (DEPRECATED).

    WARNING: This assumes perfect correlation (rho=1) between all assets,
    which overstates portfolio risk by 30-60%. Use covariance-based
    calculation when possible.

    Args:
        positions: List of portfolio positions
        price_data: Dictionary mapping symbol to PriceData

    Returns:
        Portfolio volatility, or None if insufficient data
    """
    total_value = 0.0
    weighted_vol_sum = 0.0

    for position in positions:
        price = price_data.get(position.symbol)
        if not price or price.volatility is None or price.error:
            continue

        position_value = position.shares * price.price
        total_value += position_value
        weighted_vol_sum += position_value * price.volatility

    if total_value == 0:
        return None

    logger.debug("portfolio_volatility_fallback_weighted_avg")
    return weighted_vol_sum / total_value


def calculate_top_performers(
    positions: list[Position],
    price_data: dict[str, PriceData],
    top_n: int = 3,
) -> tuple[list[PositionPerformance], list[PositionPerformance]]:
    """Calculate top and bottom performing positions.

    Args:
        positions: List of portfolio positions
        price_data: Dictionary mapping symbol to PriceData
        top_n: Number of top/bottom performers to return

    Returns:
        Tuple of (top_performers, bottom_performers)
    """
    performances: list[PositionPerformance] = []
    total_value = 0.0

    # Calculate performance for each position
    for position in positions:
        price = price_data.get(position.symbol)
        if not price or price.error:
            continue

        current_value = position.shares * price.price
        cost = position.shares * position.cost_basis
        gain_amount = current_value - cost
        gain_pct = (gain_amount / cost * 100) if cost != 0 else 0.0

        total_value += current_value

        performances.append(
            PositionPerformance(
                symbol=position.symbol,
                gain_pct=gain_pct,
                gain_amount=gain_amount,
                current_value=current_value,
                weight_pct=0.0,  # Will be calculated after
            )
        )

    # Calculate weight percentages
    if total_value > 0:
        for perf in performances:
            perf.weight_pct = (perf.current_value / total_value) * 100

    # Sort by gain percentage
    performances.sort(key=lambda x: x.gain_pct, reverse=True)

    top_performers = performances[:top_n]
    bottom_performers = performances[-top_n:][::-1]  # Reverse to show worst first

    return top_performers, bottom_performers
