"""Portfolio return and performance calculations.

This module handles calculations related to portfolio value, gains,
and position performance metrics.

GAP-020 FIX: Portfolio volatility now uses proper covariance matrix calculation
instead of incorrect weighted-average approach that assumed rho=1.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..logging_config import get_logger
from .current_facts import calculate_current_position_fact
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
            logger.warning("no_price_data_skipping", symbol=position.symbol)
            continue

        # Skip positions with price errors
        if price.error:
            logger.warning(
                "price_error_skipping_value_calculation",
                symbol=position.symbol,
                error=price.error,
            )
            continue

        current_fact = calculate_current_position_fact(
            symbol=position.symbol,
            shares=position.shares,
            cost_basis=position.cost_basis,
            position_type=position.position_type,
            current_price=price.price,
        )
        if current_fact.current_value is None:
            continue

        total_value += current_fact.current_value
        total_cost_basis += current_fact.cost_total

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
        if (
            not price
            or price.beta is None
            or not math.isfinite(price.beta)
            or price.error
        ):
            continue

        current_fact = calculate_current_position_fact(
            symbol=position.symbol,
            shares=position.shares,
            cost_basis=position.cost_basis,
            position_type=position.position_type,
            current_price=price.price,
        )
        if current_fact.current_value is None:
            continue

        total_value += abs(current_fact.current_value)
        weighted_beta_sum += current_fact.current_value * price.beta

    if total_value == 0:
        return None

    return weighted_beta_sum / total_value


def calculate_portfolio_volatility(
    positions: list[Position],
    price_data: dict[str, PriceData],
    storage: PortfolioStorage | None = None,
    account_ids: list[str] | None = None,
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

        current_fact = calculate_current_position_fact(
            symbol=position.symbol,
            shares=position.shares,
            cost_basis=position.cost_basis,
            position_type=position.position_type,
            current_price=price.price,
        )
        if current_fact.current_value is None:
            continue

        position_value = current_fact.current_value
        position_values[position.symbol] = (
            position_values.get(position.symbol, 0.0) + position_value
        )
        total_value += abs(position_value)

    if total_value == 0:
        return None

    # Calculate weights
    weights = {symbol: value / total_value for symbol, value in position_values.items()}

    # Try covariance-based calculation if storage available
    if storage is not None and len(weights) >= 2:
        try:
            from ..analytics.covariance import get_portfolio_volatility  # noqa: PLC0415

            portfolio_id = _get_covariance_portfolio_id(positions, account_ids)
            portfolio_vol, weighted_avg_vol, div_benefit = get_portfolio_volatility(
                storage,
                weights,
                portfolio_id=portfolio_id,
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

    # Fallback to weighted average.
    # NOTE: assumes perfect correlation (rho=1), overstating risk by 30-60%.
    weighted_vol_sum = 0.0
    for position in positions:
        price = price_data.get(position.symbol)
        if not price or price.volatility is None or price.error:
            continue
        current_fact = calculate_current_position_fact(
            symbol=position.symbol,
            shares=position.shares,
            cost_basis=position.cost_basis,
            position_type=position.position_type,
            current_price=price.price,
        )
        if current_fact.current_value is None:
            continue
        weighted_vol_sum += abs(current_fact.current_value) * price.volatility

    if total_value == 0:
        return None

    logger.debug("portfolio_volatility_fallback_weighted_avg")
    return weighted_vol_sum / total_value


def _get_covariance_portfolio_id(
    positions: list[Position],
    account_ids: list[str] | None = None,
) -> str:
    """Pick a real account-backed cache namespace for covariance lookups."""
    candidate_ids = sorted(set(account_ids or [position.account_id for position in positions]))
    return candidate_ids[0] if candidate_ids else "default"


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
    performances = calculate_position_performances(positions, price_data)

    top_performers = performances[:top_n]
    bottom_performers = performances[-top_n:][::-1]  # Reverse to show worst first

    return top_performers, bottom_performers


def calculate_position_performances(
    positions: list[Position],
    price_data: dict[str, PriceData],
) -> list[PositionPerformance]:
    """Return reusable performance metrics for every priced position."""
    symbol_values: dict[str, dict[str, float]] = {}

    for position in positions:
        price = price_data.get(position.symbol)
        if not price or price.error:
            continue

        symbol = position.symbol.upper()
        current_fact = calculate_current_position_fact(
            symbol=position.symbol,
            shares=position.shares,
            cost_basis=position.cost_basis,
            position_type=position.position_type,
            current_price=price.price,
        )
        if current_fact.current_value is None:
            continue

        values = symbol_values.setdefault(symbol, {"current_value": 0.0, "cost": 0.0})
        values["current_value"] += current_fact.current_value
        values["cost"] += current_fact.cost_total

    total_value = sum(abs(values["current_value"]) for values in symbol_values.values())
    performances = [
        (
            symbol,
            values["current_value"],
            values["cost"],
            values["current_value"] - values["cost"],
        )
        for symbol, values in symbol_values.items()
    ]
    result = [
        PositionPerformance(
            symbol=symbol,
            gain_pct=(gain_amount / abs(cost) * 100) if cost != 0 else 0.0,
            gain_amount=gain_amount,
            current_value=current_value,
            weight_pct=(current_value / total_value * 100) if total_value > 0 else 0.0,
        )
        for symbol, current_value, cost, gain_amount in performances
    ]

    result.sort(key=lambda performance: performance.gain_pct, reverse=True)
    return result
