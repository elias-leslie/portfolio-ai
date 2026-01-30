"""Fundamental analysis aggregation for research insights.

Handles:
- Company health classification (STRONG/MODERATE/WEAK)
- Fundamental scoring (4-pillar system matching watchlist UI)
- Valuation, growth, profitability, and debt tier classification
- Analyst consensus integration
"""

from __future__ import annotations

from typing import Any

from app.watchlist.fundamentals import (
    FundamentalData,
    calculate_fundamental_score,
    classify_company_health,
    fetch_fundamentals,
)


def aggregate_fundamental_analysis(symbol: str) -> dict[str, Any]:
    """Aggregate fundamental metrics and company health.

    Args:
        symbol: Stock symbol

    Returns:
        Dict with fundamental analysis fields
    """
    # Fetch fundamentals using existing multi-source failover
    fund_data: FundamentalData | None = fetch_fundamentals(symbol)

    if not fund_data:
        # No fundamental data available
        return {
            "company_health": "WEAK",
            "fundamental_score": 0,
            "valuation_tier": "fair",
            "growth_tier": "stable",
            "profitability_tier": "weak",
            "debt_tier": "moderate",
            "analyst_consensus": 3.0,
            "confidence": 0.0,
        }

    # Classify company health using existing logic
    company_health = classify_company_health(fund_data)

    # Calculate fundamental score using the same 4-pillar system as watchlist
    # This ensures consistency: research aggregator matches watchlist UI
    fundamental_score = int(calculate_fundamental_score(fund_data))

    # Classify valuation tier
    profit_margin = fund_data.profit_margin or 0.0
    if profit_margin > 0.20:
        valuation_tier = "undervalued"
    elif profit_margin < 0.05:
        valuation_tier = "overvalued"
    else:
        valuation_tier = "fair"

    # Classify growth tier
    revenue_growth = fund_data.revenue_growth or 0.0
    if revenue_growth > 0.30:
        growth_tier = "accelerating"
    elif revenue_growth < 0.0:
        growth_tier = "slowing"
    else:
        growth_tier = "stable"

    # Classify profitability tier
    if profit_margin > 0.20:
        profitability_tier = "excellent"
    elif profit_margin > 0.10:
        profitability_tier = "good"
    else:
        profitability_tier = "weak"

    # Classify debt tier
    debt_to_equity = fund_data.debt_to_equity or 0.5
    if debt_to_equity < 0.3:
        debt_tier = "low"
    elif debt_to_equity > 2.0:
        debt_tier = "high"
    else:
        debt_tier = "moderate"

    # Analyst consensus (1=strong buy, 5=sell)
    analyst_consensus = fund_data.recommendation_mean or 3.0

    # Confidence based on data completeness
    fields_present = sum(
        [
            fund_data.profit_margin is not None,
            fund_data.revenue_growth is not None,
            fund_data.debt_to_equity is not None,
            fund_data.recommendation_mean is not None,
        ]
    )
    confidence = fields_present / 4.0

    return {
        "company_health": company_health,
        "fundamental_score": fundamental_score,
        "valuation_tier": valuation_tier,
        "growth_tier": growth_tier,
        "profitability_tier": profitability_tier,
        "debt_tier": debt_tier,
        "analyst_consensus": analyst_consensus,
        "confidence": confidence,
    }
