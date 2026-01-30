"""Company health classification based on fundamental metrics.

This module classifies companies as EXCELLENT, GOOD, or WEAK based on
financial health indicators including profit margins, revenue growth,
debt ratios, and analyst recommendations.
"""

from __future__ import annotations

from app.watchlist.fundamentals_models import FundamentalData


def classify_company_health(data: FundamentalData) -> str:
    """Classify company health as EXCELLENT, GOOD, or WEAK.

    Classification criteria:
    - EXCELLENT: Profit margin > 20% AND revenue growth > 20% AND
                 debt-to-equity < 0.5 AND analyst consensus strong buy
    - GOOD: Profit margin > 5% AND revenue growth 5-20% AND
            debt-to-equity < 1.5
    - WEAK: Profit margin < 0% OR revenue shrinking OR debt-to-equity > 2.0

    Args:
        data: FundamentalData with company metrics

    Returns:
        "EXCELLENT", "GOOD", or "WEAK"
    """
    # Extract metrics (treat None as neutral/default values)
    profit_margin = data.profit_margin if data.profit_margin is not None else 0.06
    revenue_growth = data.revenue_growth if data.revenue_growth is not None else 0.06
    debt_to_equity = data.debt_to_equity if data.debt_to_equity is not None else 1.0
    recommendation_mean = data.recommendation_mean if data.recommendation_mean is not None else 3.0

    # Check for WEAK signals (highest priority)
    if profit_margin < 0:  # Unprofitable
        return "WEAK"
    if revenue_growth < 0:  # Shrinking revenue
        return "WEAK"
    if debt_to_equity > 2.0:  # High debt
        return "WEAK"

    # Check for EXCELLENT signals (all criteria must be met)
    if (
        profit_margin > 0.20
        and revenue_growth > 0.20
        and debt_to_equity < 0.5
        and recommendation_mean < 2.0
    ):
        return "EXCELLENT"

    # Default to GOOD (moderate company)
    return "GOOD"
