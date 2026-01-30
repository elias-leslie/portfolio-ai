"""Macro context aggregation for research insights.

Handles:
- Fear & Greed Index classification
- Market regime detection (bull, bear, range, volatile)
- Sector rotation phase (early_cycle, mid_cycle, late_cycle, recession)
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.analytics.indicators import calculate_indicators_for_symbol
from app.storage import PortfolioStorage


def aggregate_macro_context(storage: PortfolioStorage, as_of_date: date) -> dict[str, Any]:
    """Aggregate macro indicators (Fear & Greed, market regime).

    Args:
        storage: Portfolio storage instance
        as_of_date: Date to analyze

    Returns:
        Dict with macro context fields
    """
    # Query Fear & Greed from database
    fg_data = storage.get_fear_greed_latest()
    fear_greed_score = fg_data["score"]

    # Classify Fear & Greed
    if fear_greed_score <= 25:
        fear_greed_classification = "extreme_fear"
    elif fear_greed_score <= 45:
        fear_greed_classification = "fear"
    elif fear_greed_score <= 55:
        fear_greed_classification = "neutral"
    elif fear_greed_score <= 75:
        fear_greed_classification = "greed"
    else:
        fear_greed_classification = "extreme_greed"

    # Determine market regime (simplified logic)
    # Query SPY trend and VIX
    spy_indicators = calculate_indicators_for_symbol("SPY", indicators=["sma_200"])
    market_data = storage.get_spy_and_vix_data()
    spy_price = market_data["spy_close"]
    spy_sma_200 = spy_indicators.get("sma_200", spy_price)
    vix_close = market_data["vix_close"]

    # Market regime classification
    if vix_close > 30:
        market_regime = "volatile"
    elif fear_greed_score > 60 and spy_price > spy_sma_200:
        market_regime = "bull"
    elif fear_greed_score < 40 and spy_price < spy_sma_200:
        market_regime = "bear"
    else:
        market_regime = "range"

    # Sector rotation phase (simplified, based on VIX + Fear & Greed)
    if vix_close > 25:
        sector_rotation_phase = "recession"
    elif fear_greed_score > 70:
        sector_rotation_phase = "late_cycle"
    elif fear_greed_score > 55:
        sector_rotation_phase = "mid_cycle"
    else:
        sector_rotation_phase = "early_cycle"

    return {
        "market_regime": market_regime,
        "fear_greed_score": fear_greed_score,
        "fear_greed_classification": fear_greed_classification,
        "sector_rotation_phase": sector_rotation_phase,
    }
