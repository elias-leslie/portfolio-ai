"""Advanced risk metrics for GAP-026 and GAP-028.

GAP-026: Marginal VaR - Risk contribution per position
GAP-028: Exposure Budgets - Position/sector/factor limits

Uses covariance matrix for proper risk decomposition.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.analytics.covariance import get_covariance_matrix, update_covariance_matrix
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


# Default exposure limits
DEFAULT_POSITION_LIMIT = 0.10  # 10% max per position
DEFAULT_SECTOR_LIMIT = 0.30  # 30% max per sector


@dataclass
class MarginalVaR:
    """Marginal VaR result for a position."""

    symbol: str
    weight: float
    marginal_var: float  # Change in VaR per 1% increase in position
    component_var: float  # Total VaR contribution (weight * marginal_var)
    pct_contribution: float  # % of total portfolio VaR


@dataclass
class PortfolioMarginalVaR:
    """Portfolio-level marginal VaR analysis."""

    portfolio_var: float
    positions: list[MarginalVaR]
    largest_contributor: str
    total_component_var: float
    error: str | None = None


@dataclass
class ExposureBudget:
    """Exposure budget tracking for a category."""

    category: str
    current_exposure: float
    limit: float
    utilization: float  # current / limit
    available: float  # limit - current
    status: str  # "OK", "WARNING", "BREACH"
    positions: list[str] = field(default_factory=list)


@dataclass
class ExposureBudgetReport:
    """Full exposure budget report."""

    position_budgets: list[ExposureBudget]
    sector_budgets: list[ExposureBudget]
    breach_count: int
    warning_count: int
    overall_status: str  # "COMPLIANT", "WARNING", "BREACH"


def calculate_marginal_var(
    storage: PortfolioStorage,
    weights: dict[str, float],
    portfolio_var: float | None = None,
) -> PortfolioMarginalVaR:
    """Calculate marginal VaR for each position.

    Marginal VaR = Change in portfolio VaR from 1% increase in position
    Component VaR = weight * Marginal VaR

    For a single-asset change, using delta-normal approximation:
    Marginal VaR_i = (Cov(i, portfolio) / sigma_portfolio) * z_alpha

    Args:
        storage: Database storage instance
        weights: Dict mapping symbol to weight
        portfolio_var: Pre-calculated portfolio VaR (if None, calculated)

    Returns:
        PortfolioMarginalVaR with breakdown by position
    """
    if not weights:
        return PortfolioMarginalVaR(
            portfolio_var=0.0,
            positions=[],
            largest_contributor="",
            total_component_var=0.0,
            error="No positions",
        )

    tickers = list(weights.keys())

    # Get covariance matrix
    cov_matrix = get_covariance_matrix(storage, tickers)
    if cov_matrix is None:
        update_covariance_matrix(storage, tickers)
        cov_matrix = get_covariance_matrix(storage, tickers, max_age_hours=1)

    if cov_matrix is None:
        return PortfolioMarginalVaR(
            portfolio_var=0.0,
            positions=[],
            largest_contributor="",
            total_component_var=0.0,
            error="Could not calculate covariance matrix",
        )

    # Calculate portfolio variance (daily)
    port_variance = 0.0
    for t1 in tickers:
        for t2 in tickers:
            cov = cov_matrix.get((t1, t2), 0.0)
            port_variance += weights[t1] * weights[t2] * cov

    port_std = math.sqrt(port_variance) if port_variance > 0 else 0.0

    # Calculate portfolio VaR if not provided
    if portfolio_var is None:
        # Estimate VaR using normal distribution (95% confidence)
        z_alpha = 1.645  # 95% VaR
        portfolio_var = port_std * z_alpha

    if port_std == 0:
        return PortfolioMarginalVaR(
            portfolio_var=portfolio_var,
            positions=[],
            largest_contributor="",
            total_component_var=0.0,
            error="Zero portfolio volatility",
        )

    # Calculate marginal VaR for each position
    positions: list[MarginalVaR] = []
    total_component_var = 0.0
    z_alpha = 1.645  # 95% confidence

    for symbol in tickers:
        weight = weights[symbol]

        # Cov(asset_i, portfolio) = sum_j(w_j * Cov(i,j))
        cov_with_portfolio = sum(
            weights.get(t2, 0) * cov_matrix.get((symbol, t2), 0.0) for t2 in tickers
        )

        # Marginal VaR = (Cov(i, P) / sigma_P) * z
        marginal_var = (cov_with_portfolio / port_std) * z_alpha if port_std > 0 else 0.0

        # Component VaR = w_i * Marginal VaR_i
        component_var = weight * marginal_var

        total_component_var += component_var

        positions.append(
            MarginalVaR(
                symbol=symbol,
                weight=weight,
                marginal_var=marginal_var,
                component_var=component_var,
                pct_contribution=0.0,  # Will calculate after totaling
            )
        )

    # Compute percentage contribution for each position
    for pos in positions:
        if total_component_var > 0:
            pos.pct_contribution = pos.component_var / total_component_var

    # Sort by contribution (largest first)
    positions.sort(key=lambda x: abs(x.component_var), reverse=True)

    largest = positions[0].symbol if positions else ""

    logger.info(
        "marginal_var_calculated",
        positions=len(positions),
        portfolio_var=f"{portfolio_var:.4f}",
        largest_contributor=largest,
    )

    return PortfolioMarginalVaR(
        portfolio_var=portfolio_var,
        positions=positions,
        largest_contributor=largest,
        total_component_var=total_component_var,
    )


def check_exposure_budgets(
    positions: list[dict[str, str | float]],
    position_limit: float = DEFAULT_POSITION_LIMIT,
    sector_limit: float = DEFAULT_SECTOR_LIMIT,
) -> ExposureBudgetReport:
    """Check position and sector exposure against budget limits.

    Args:
        positions: List of dicts with keys:
            - symbol: str
            - weight: float (portfolio weight, should sum to 1)
            - sector: str (GICS sector name)
        position_limit: Max weight per position (default 10%)
        sector_limit: Max weight per sector (default 30%)

    Returns:
        ExposureBudgetReport with breach analysis
    """
    position_budgets: list[ExposureBudget] = []
    sector_exposures: dict[str, dict[str, float | list[str]]] = {}
    breach_count = 0
    warning_count = 0

    # Check individual positions
    for pos in positions:
        symbol_val = pos.get("symbol", "UNKNOWN")
        symbol = str(symbol_val) if symbol_val is not None else "UNKNOWN"
        weight_val = pos.get("weight", 0.0)
        weight = float(weight_val) if weight_val is not None else 0.0
        sector_val = pos.get("sector", "Unknown")
        sector = str(sector_val) if sector_val is not None else "Unknown"

        # Track sector exposure
        if sector not in sector_exposures:
            sector_exposures[sector] = {"weight": 0.0, "positions": []}
        weight_in_sector = sector_exposures[sector]["weight"]
        current_weight = float(weight_in_sector) if isinstance(weight_in_sector, (int, float)) else 0.0
        sector_exposures[sector]["weight"] = current_weight + weight
        pos_list = sector_exposures[sector]["positions"]
        if isinstance(pos_list, list):
            pos_list.append(symbol)

        # Check position limit
        utilization = weight / position_limit if position_limit > 0 else 0
        available = max(0, position_limit - weight)

        if weight > position_limit:
            status = "BREACH"
            breach_count += 1
        elif weight > position_limit * 0.8:
            status = "WARNING"
            warning_count += 1
        else:
            status = "OK"

        position_budgets.append(
            ExposureBudget(
                category=symbol,
                current_exposure=weight,
                limit=position_limit,
                utilization=utilization,
                available=available,
                status=status,
            )
        )

    # Check sector limits
    sector_budgets: list[ExposureBudget] = []
    for sector, data in sector_exposures.items():
        weight_data = data["weight"]
        weight = float(weight_data) if isinstance(weight_data, (int, float)) else 0.0
        utilization = weight / sector_limit if sector_limit > 0 else 0.0
        available = max(0.0, sector_limit - weight)

        if weight > sector_limit:
            status = "BREACH"
            breach_count += 1
        elif weight > sector_limit * 0.8:
            status = "WARNING"
            warning_count += 1
        else:
            status = "OK"

        positions_list = data["positions"]
        if not isinstance(positions_list, list):
            positions_list = []

        sector_budgets.append(
            ExposureBudget(
                category=sector,
                current_exposure=weight,
                limit=sector_limit,
                utilization=utilization,
                available=available,
                status=status,
                positions=[str(p) for p in positions_list],
            )
        )

    # Sort by utilization (highest first)
    position_budgets.sort(key=lambda x: x.utilization, reverse=True)
    sector_budgets.sort(key=lambda x: x.utilization, reverse=True)

    # Determine overall status
    if breach_count > 0:
        overall_status = "BREACH"
    elif warning_count > 0:
        overall_status = "WARNING"
    else:
        overall_status = "COMPLIANT"

    logger.info(
        "exposure_budget_check",
        positions=len(position_budgets),
        sectors=len(sector_budgets),
        breaches=breach_count,
        warnings=warning_count,
        overall=overall_status,
    )

    return ExposureBudgetReport(
        position_budgets=position_budgets,
        sector_budgets=sector_budgets,
        breach_count=breach_count,
        warning_count=warning_count,
        overall_status=overall_status,
    )


def get_rebalancing_suggestions(
    exposure_report: ExposureBudgetReport,
) -> list[dict[str, object]]:
    """Generate rebalancing suggestions to fix exposure breaches.

    Args:
        exposure_report: Current exposure budget report

    Returns:
        List of suggested trades to achieve compliance
    """
    suggestions: list[dict[str, object]] = []

    # Handle position breaches
    for budget in exposure_report.position_budgets:
        if budget.status == "BREACH":
            excess = budget.current_exposure - budget.limit
            suggestions.append(
                {
                    "type": "position",
                    "symbol": budget.category,
                    "action": "REDUCE",
                    "current_weight": budget.current_exposure,
                    "target_weight": budget.limit,
                    "reduction_needed": excess,
                    "reason": f"Exceeds {budget.limit:.0%} position limit",
                }
            )

    # Handle sector breaches
    for budget in exposure_report.sector_budgets:
        if budget.status == "BREACH":
            excess = budget.current_exposure - budget.limit
            suggestions.append(
                {
                    "type": "sector",
                    "sector": budget.category,
                    "positions": budget.positions,
                    "action": "REDUCE",
                    "current_weight": budget.current_exposure,
                    "target_weight": budget.limit,
                    "reduction_needed": excess,
                    "reason": f"Exceeds {budget.limit:.0%} sector limit",
                }
            )

    return suggestions
