"""Fundamental analysis aggregation for research insights.

Handles:
- Company health classification (STRONG/MODERATE/WEAK)
- Fundamental scoring (4-pillar system matching watchlist UI)
- Valuation, growth, profitability, and debt tier classification
- Analyst consensus integration
"""

from __future__ import annotations

from typing import TypedDict

from app.watchlist.fundamentals import (
    FundamentalData,
    calculate_fundamental_score,
    classify_company_health,
    fetch_fundamentals,
)


class FundamentalAnalysis(TypedDict):
    """Result of fundamental analysis aggregation."""

    company_health: str
    fundamental_score: int
    valuation_tier: str
    growth_tier: str
    profitability_tier: str
    debt_tier: str
    analyst_consensus: float
    confidence: float


_DEFAULT_RESULT: FundamentalAnalysis = {
    "company_health": "WEAK",
    "fundamental_score": 0,
    "valuation_tier": "fair",
    "growth_tier": "stable",
    "profitability_tier": "weak",
    "debt_tier": "moderate",
    "analyst_consensus": 3.0,
    "confidence": 0.0,
}


def _classify_valuation_tier(profit_margin: float) -> str:
    if profit_margin > 0.20:
        return "undervalued"
    if profit_margin < 0.05:
        return "overvalued"
    return "fair"


def _classify_growth_tier(revenue_growth: float) -> str:
    if revenue_growth > 0.30:
        return "accelerating"
    if revenue_growth < 0.0:
        return "slowing"
    return "stable"


def _classify_profitability_tier(profit_margin: float) -> str:
    if profit_margin > 0.20:
        return "excellent"
    if profit_margin > 0.10:
        return "good"
    return "weak"


def _classify_debt_tier(debt_to_equity: float) -> str:
    if debt_to_equity < 0.3:
        return "low"
    if debt_to_equity > 2.0:
        return "high"
    return "moderate"


def _calculate_confidence(fund_data: FundamentalData) -> float:
    fields_present = sum(
        [
            fund_data.profit_margin is not None,
            fund_data.revenue_growth is not None,
            fund_data.debt_to_equity is not None,
            fund_data.recommendation_mean is not None,
        ]
    )
    return fields_present / 4.0


def aggregate_fundamental_analysis(symbol: str) -> FundamentalAnalysis:
    """Aggregate fundamental metrics and company health.

    Args:
        symbol: Stock symbol

    Returns:
        FundamentalAnalysis with fundamental analysis fields
    """
    fund_data: FundamentalData | None = fetch_fundamentals(symbol)

    if not fund_data:
        return _DEFAULT_RESULT

    profit_margin = fund_data.profit_margin or 0.0
    revenue_growth = fund_data.revenue_growth or 0.0
    debt_to_equity = fund_data.debt_to_equity or 0.5

    return {
        "company_health": classify_company_health(fund_data),
        "fundamental_score": int(calculate_fundamental_score(fund_data)),
        "valuation_tier": _classify_valuation_tier(profit_margin),
        "growth_tier": _classify_growth_tier(revenue_growth),
        "profitability_tier": _classify_profitability_tier(profit_margin),
        "debt_tier": _classify_debt_tier(debt_to_equity),
        "analyst_consensus": fund_data.recommendation_mean or 3.0,
        "confidence": _calculate_confidence(fund_data),
    }
