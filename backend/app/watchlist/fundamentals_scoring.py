"""Fundamental scoring calculations using 4-pillar system.

This module implements the 4-pillar scoring system:
- Valuation (25%): P/E, P/B, profit margin
- Growth (35%): Revenue and earnings growth
- Health (25%): Debt ratios and profitability
- Sentiment (15%): Analyst ratings and news sentiment

Each pillar is scored 0-100, then weighted to produce the overall fundamental score.
"""

from __future__ import annotations

from app.watchlist.fundamentals_models import FundamentalData


def _interpolate_score(
    value: float,
    thresholds: list[float],
    scores: list[float],
) -> float:
    """Linearly interpolate a score between threshold/score pairs.

    Values below the first threshold get the first score.
    Values above the last threshold get the last score.
    """
    if value <= thresholds[0]:
        return scores[0]
    for i in range(1, len(thresholds)):
        if value <= thresholds[i]:
            ratio = (value - thresholds[i - 1]) / (thresholds[i] - thresholds[i - 1])
            return scores[i - 1] + ratio * (scores[i] - scores[i - 1])
    return scores[-1]


def calculate_valuation_score(data: FundamentalData) -> float:
    """Calculate valuation score (0-100) based on profit margin.

    Weight: 25% of fundamental score

    Uses linear interpolation between thresholds for smoother scoring:
    - margin <= 0%  → 20
    - margin  5%    → 50
    - margin 10%    → 70
    - margin 20%    → 90
    - margin >= 30% → 95

    When P/E, P/B, PEG ratios are added to FundamentalData, this function
    should incorporate them as a weighted blend alongside profit margin.

    Args:
        data: FundamentalData with company metrics

    Returns:
        Valuation score 0-100 (higher = better value)
    """
    profit_margin = data.profit_margin if data.profit_margin is not None else 0.06
    return _interpolate_score(
        profit_margin,
        thresholds=[0.0, 0.05, 0.10, 0.20, 0.30],
        scores=[20.0, 50.0, 70.0, 90.0, 95.0],
    )


def calculate_growth_score(data: FundamentalData) -> float:
    """Calculate growth score (0-100) based on revenue growth.

    Weight: 35% of fundamental score

    Uses linear interpolation:
    - growth <= 0%  → 10
    - growth  5%    → 40
    - growth 10%    → 60
    - growth 20%    → 80
    - growth >= 30% → 100

    Args:
        data: FundamentalData with company metrics

    Returns:
        Growth score 0-100 (higher = faster growth)
    """
    revenue_growth = data.revenue_growth if data.revenue_growth is not None else 0.06
    return _interpolate_score(
        revenue_growth,
        thresholds=[0.0, 0.05, 0.10, 0.20, 0.30],
        scores=[10.0, 40.0, 60.0, 80.0, 100.0],
    )


def calculate_health_score(data: FundamentalData) -> float:
    """Calculate financial health score (0-100) based on debt and profitability.

    Weight: 25% of fundamental score

    Scoring:
    - Debt/Equity: <0.3 = 100, <0.7 = 80, <1.5 = 60, <2.5 = 40, else 20
    - Profit margin: >20% = 100, >10% = 80, >5% = 60, >0% = 40, else 0
    - Average the 2 scores

    Args:
        data: FundamentalData with company metrics

    Returns:
        Health score 0-100 (higher = healthier)
    """
    debt_to_equity = data.debt_to_equity or 1.0
    profit_margin = data.profit_margin or 0.06

    # Debt scoring
    if debt_to_equity < 0.3:
        debt_score = 100.0
    elif debt_to_equity < 0.7:
        debt_score = 80.0
    elif debt_to_equity < 1.5:
        debt_score = 60.0
    elif debt_to_equity < 2.5:
        debt_score = 40.0
    else:
        debt_score = 20.0

    # Profit margin scoring
    if profit_margin > 0.20:
        margin_score = 100.0
    elif profit_margin > 0.10:
        margin_score = 80.0
    elif profit_margin > 0.05:
        margin_score = 60.0
    elif profit_margin > 0:
        margin_score = 40.0
    else:
        margin_score = 0.0

    return (debt_score + margin_score) / 2.0


def _calculate_analyst_sentiment(rec_mean: float) -> float:
    """Calculate analyst sentiment score (0-100) from recommendation mean.

    Scoring based on recommendation_mean (1=strong buy, 5=sell):
    - 1.0-1.5 = 100, 1.5-2.0 = 80, 2.0-2.5 = 60, 2.5-3.5 = 40, 3.5-4.5 = 20, >4.5 = 0
    """
    if rec_mean < 1.5:
        return 100.0
    if rec_mean < 2.0:
        return 80.0
    if rec_mean < 2.5:
        return 60.0
    if rec_mean < 3.5:
        return 40.0
    if rec_mean < 4.5:
        return 20.0
    return 0.0


def calculate_sentiment_score(data: FundamentalData) -> float:
    """Calculate blended sentiment score (0-100) combining analyst + news sentiment.

    GAP-015: News sentiment as a dedicated pillar component.

    Blending (when both available):
    - Analyst sentiment: 50% weight (institutional view)
    - News sentiment: 50% weight (market narrative)

    If only one is available, use 100% of that source.

    Weight: 15% of fundamental score (increased from 10%)

    Args:
        data: FundamentalData with company metrics

    Returns:
        Sentiment score 0-100 (higher = more bullish)
    """
    # Analyst sentiment
    rec_mean = data.recommendation_mean or 3.0
    analyst_score = _calculate_analyst_sentiment(rec_mean)

    # News sentiment (GAP-015)
    news_score = data.news_sentiment_score

    # Blend if both available
    if news_score is not None:
        # 50/50 blend of analyst and news sentiment
        return analyst_score * 0.5 + news_score * 0.5

    # Fallback to analyst only
    return analyst_score


def calculate_fundamental_score(data: FundamentalData) -> float:
    """Calculate overall fundamental score (0-100) using 4-pillar system.

    Pillars (GAP-015 update: increased sentiment weight):
    - Valuation: 25% (P/E, P/B, profit margin)
    - Growth: 35% (revenue, earnings)
    - Health: 25% (debt, margins)
    - Sentiment: 15% (analyst + news, blended)

    Args:
        data: FundamentalData with company metrics

    Returns:
        Overall fundamental score (0-100)
    """
    valuation = calculate_valuation_score(data)
    growth = calculate_growth_score(data)
    health = calculate_health_score(data)
    sentiment = calculate_sentiment_score(data)

    # Weighted average (25/35/25/15) - sentiment increased for GAP-015
    overall = valuation * 0.25 + growth * 0.35 + health * 0.25 + sentiment * 0.15

    return overall
