"""Portfolio covariance matrix calculations (GAP-020).

This module provides correct portfolio risk calculation using covariance matrix,
replacing the incorrect weighted-average approach that assumed rho=1.

Correct formula: sigma_portfolio = sqrt(w' * Cov * w)
where w = weight vector, Cov = covariance matrix

References:
- Markowitz, H. (1952). Portfolio Selection. Journal of Finance.
- Modern Portfolio Theory fundamentals

This is the main module that re-exports all covariance functionality from submodules.
"""

from __future__ import annotations

# Re-export calculation functions
from app.analytics.covariance_calc import (
    DEFAULT_LOOKBACK_DAYS,
    MIN_OBSERVATIONS,
    align_returns,
    calculate_daily_returns,
    calculate_pairwise_covariance,
    calculate_portfolio_volatility_from_covariance,
    calculate_volatility,
)

# Re-export storage functions
from app.analytics.covariance_storage import (
    calculate_weight_hash,
    get_covariance_matrix,
    get_portfolio_volatility,
    update_covariance_matrix,
)

__all__ = [
    # Constants
    "DEFAULT_LOOKBACK_DAYS",
    "MIN_OBSERVATIONS",
    # Calculation functions
    "align_returns",
    "calculate_daily_returns",
    "calculate_pairwise_covariance",
    "calculate_portfolio_volatility_from_covariance",
    "calculate_volatility",
    # Storage functions
    "calculate_weight_hash",
    "get_covariance_matrix",
    "get_portfolio_volatility",
    "update_covariance_matrix",
]
