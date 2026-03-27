"""Macro context aggregation for research insights.

Handles:
- Fear & Greed Index classification
- Market regime detection (bull, bear, range, volatile)
- Sector rotation phase (early_cycle, mid_cycle, late_cycle, recession)
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict

from app.analytics.indicators import calculate_indicators_for_symbol
from app.storage import PortfolioStorage


class MacroContext(TypedDict):
    """Aggregated macro context fields."""

    market_regime: str
    fear_greed_score: float
    fear_greed_classification: str
    sector_rotation_phase: str


def _classify_fear_greed(score: float) -> str:
    """Return a Fear & Greed label for the given score."""
    if score <= 25:
        return "extreme_fear"
    if score <= 45:
        return "fear"
    if score <= 55:
        return "neutral"
    if score <= 75:
        return "greed"
    return "extreme_greed"


def _classify_market_regime(
    fear_greed_score: float,
    spy_price: float,
    spy_sma_200: float,
    vix_close: float,
) -> str:
    """Return a market regime label."""
    if vix_close > 30:
        return "volatile"
    if fear_greed_score > 60 and spy_price > spy_sma_200:
        return "bull"
    if fear_greed_score < 40 and spy_price < spy_sma_200:
        return "bear"
    return "range"


def _classify_sector_rotation(fear_greed_score: float, vix_close: float) -> str:
    """Return a sector rotation phase label."""
    if vix_close > 25:
        return "recession"
    if fear_greed_score > 70:
        return "late_cycle"
    if fear_greed_score > 55:
        return "mid_cycle"
    return "early_cycle"


def aggregate_macro_context(storage: PortfolioStorage, as_of_date: date) -> MacroContext:
    """Aggregate macro indicators (Fear & Greed, market regime).

    Args:
        storage: Portfolio storage instance
        as_of_date: Date to analyze

    Returns:
        Dict with macro context fields
    """
    fg_data = storage.get_fear_greed_latest()
    fear_greed_score: float = fg_data["score"]
    fear_greed_classification = _classify_fear_greed(fear_greed_score)

    spy_indicators = calculate_indicators_for_symbol("SPY", indicators=["sma_200"])
    market_data = storage.get_spy_and_vix_data()
    spy_price: float = market_data["spy_close"]
    spy_sma_200: float = spy_indicators.get("sma_200", spy_price)
    vix_close: float = market_data["vix_close"]

    market_regime = _classify_market_regime(
        fear_greed_score, spy_price, spy_sma_200, vix_close
    )
    sector_rotation_phase = _classify_sector_rotation(fear_greed_score, vix_close)

    return {
        "market_regime": market_regime,
        "fear_greed_score": fear_greed_score,
        "fear_greed_classification": fear_greed_classification,
        "sector_rotation_phase": sector_rotation_phase,
    }
