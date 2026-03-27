"""Technical analysis aggregation for research insights.

Handles:
- Trend strength classification (strong_up, weak_up, neutral, weak_down, strong_down)
- Trend duration calculation
- Momentum rating (accelerating, steady, decelerating)
- Volume profile analysis
- RSI zone classification (oversold, healthy, overbought)
"""

from __future__ import annotations

from datetime import date
from typing import Literal, TypedDict

from app.analytics.indicators import calculate_indicators_for_symbol
from app.constants import TRADING_DAYS_PER_YEAR
from app.storage import PortfolioStorage

TrendStrength = Literal["strong_up", "weak_up", "neutral", "weak_down", "strong_down"]
MomentumRating = Literal["accelerating", "steady", "decelerating"]
VolumeProfile = Literal["increasing", "stable", "decreasing"]
RsiZone = Literal["oversold", "healthy", "overbought"]


class PriceVsMa(TypedDict):
    """Price vs moving average ratios."""

    _20d: float
    _50d: float
    _200d: float


class TechnicalAnalysisResult(TypedDict):
    """Result of technical analysis aggregation."""

    trend_strength: TrendStrength
    trend_duration_days: int
    momentum_rating: MomentumRating
    volume_profile: VolumeProfile
    rsi_zone: RsiZone
    price_vs_ma: dict[str, float]
    confidence: float


_EMPTY_RESULT: TechnicalAnalysisResult = {
    "trend_strength": "neutral",
    "trend_duration_days": 0,
    "momentum_rating": "steady",
    "volume_profile": "stable",
    "rsi_zone": "healthy",
    "price_vs_ma": {"20d": 1.0, "50d": 1.0, "200d": 1.0},
    "confidence": 0.0,
}


def classify_trend_strength(
    price: float, sma_20: float, sma_50: float, sma_200: float
) -> TrendStrength:
    """Classify trend strength based on price vs moving averages.

    Args:
        price: Current stock price
        sma_20: 20-day simple moving average
        sma_50: 50-day simple moving average
        sma_200: 200-day simple moving average

    Returns:
        Trend strength classification
    """
    if price > sma_20 and price > sma_50 and price > sma_200:
        if sma_200 > 0 and price / sma_200 > 1.10:
            return "strong_up"
        return "weak_up"
    if price < sma_20 and price < sma_50 and price < sma_200:
        if sma_200 > 0 and price / sma_200 < 0.90:
            return "strong_down"
        return "weak_down"
    return "neutral"


def analyze_momentum(
    macd_data: dict[str, float] | float,
) -> MomentumRating:
    """Classify momentum using MACD histogram.

    Args:
        macd_data: MACD data dict with 'histogram' key, or float

    Returns:
        Momentum classification
    """
    macd_hist = macd_data.get("histogram", 0.0) if isinstance(macd_data, dict) else 0.0
    if macd_hist > 1.0:
        return "accelerating"
    if macd_hist < -1.0:
        return "decelerating"
    return "steady"


def classify_rsi_zone(rsi_14: float) -> RsiZone:
    """Classify RSI zone.

    Args:
        rsi_14: 14-period RSI value

    Returns:
        RSI zone classification
    """
    if rsi_14 < 30:
        return "oversold"
    if rsi_14 > 70:
        return "overbought"
    return "healthy"


def _is_uptrend(trend_strength: str) -> bool:
    return trend_strength in ("strong_up", "weak_up")


def _is_downtrend(trend_strength: str) -> bool:
    return trend_strength in ("strong_down", "weak_down")


def _row_matches_trend(row: dict[str, float], trend_strength: str, sma_20: float) -> bool:
    if _is_uptrend(trend_strength):
        return row["close"] > sma_20
    if _is_downtrend(trend_strength):
        return row["close"] < sma_20
    return False


def calculate_trend_duration(
    storage: PortfolioStorage, symbol: str, trend_strength: str, sma_20: float
) -> int:
    """Calculate trend duration in days above/below key moving average.

    Args:
        storage: Portfolio storage instance
        symbol: Stock symbol
        trend_strength: Current trend classification
        sma_20: 20-day simple moving average

    Returns:
        Number of days in current trend
    """
    df = storage.get_ohlcv_data(symbol, limit=60)
    if df.is_empty():
        return 0

    trend_rows = df.to_dicts()
    if not trend_rows or trend_strength == "neutral":
        return 0

    trend_duration_days = 0
    for i, row in enumerate(trend_rows):
        if not _row_matches_trend(row, trend_strength, sma_20):
            break
        trend_duration_days = i + 1
    return trend_duration_days


def analyze_volume_profile(
    storage: PortfolioStorage, symbol: str
) -> VolumeProfile:
    """Analyze volume profile by comparing recent to average volume.

    Args:
        storage: Portfolio storage instance
        symbol: Stock symbol

    Returns:
        Volume profile classification
    """
    df = storage.get_ohlcv_data(symbol, limit=20)
    if df.is_empty():
        return "stable"

    volume_rows = df.to_dicts()
    if not volume_rows or len(volume_rows) < 20:
        return "stable"

    recent_5d_avg = sum(row["volume"] for row in volume_rows[:5]) / 5
    recent_20d_avg = sum(row["volume"] for row in volume_rows) / 20
    if recent_5d_avg > recent_20d_avg * 1.2:
        return "increasing"
    if recent_5d_avg < recent_20d_avg * 0.8:
        return "decreasing"
    return "stable"


def _extract_moving_averages(
    indicators: dict[str, float], current_price: float
) -> tuple[float, float, float]:
    sma_20 = indicators.get("sma_20", current_price)
    sma_50 = indicators.get("sma_50", current_price)
    sma_200 = indicators.get("sma_200", current_price)
    return sma_20, sma_50, sma_200


def _build_price_vs_ma(
    current_price: float, sma_20: float, sma_50: float, sma_200: float
) -> dict[str, float]:
    return {
        "20d": round(current_price / sma_20, 4) if sma_20 > 0 else 1.0,
        "50d": round(current_price / sma_50, 4) if sma_50 > 0 else 1.0,
        "200d": round(current_price / sma_200, 4) if sma_200 > 0 else 1.0,
    }


def _calculate_confidence(storage: PortfolioStorage, symbol: str) -> float:
    bar_count_val = storage.get_bar_count(symbol)
    return min(1.0, bar_count_val / TRADING_DAYS_PER_YEAR)


def aggregate_technical_analysis(
    storage: PortfolioStorage, symbol: str, as_of_date: date
) -> TechnicalAnalysisResult:
    """Aggregate technical indicators and trends.

    Args:
        storage: Portfolio storage instance
        symbol: Stock symbol
        as_of_date: Date to analyze

    Returns:
        Dict with technical analysis fields
    """
    indicators = calculate_indicators_for_symbol(
        symbol, indicators=["rsi", "macd", "sma_20", "sma_50", "sma_200", "ema_20", "atr"]
    )
    if not indicators:
        return _EMPTY_RESULT

    current_price = storage.get_current_price(symbol) or 100.0
    rsi_14 = indicators.get("rsi_14", 50.0)
    sma_20, sma_50, sma_200 = _extract_moving_averages(indicators, current_price)

    trend_strength = classify_trend_strength(current_price, sma_20, sma_50, sma_200)
    trend_duration_days = calculate_trend_duration(storage, symbol, trend_strength, sma_20)
    momentum_rating = analyze_momentum(indicators.get("macd_12_26_9", {}))
    volume_profile = analyze_volume_profile(storage, symbol)
    rsi_zone = classify_rsi_zone(rsi_14)
    price_vs_ma = _build_price_vs_ma(current_price, sma_20, sma_50, sma_200)
    confidence = _calculate_confidence(storage, symbol)

    return {
        "trend_strength": trend_strength,
        "trend_duration_days": trend_duration_days,
        "momentum_rating": momentum_rating,
        "volume_profile": volume_profile,
        "rsi_zone": rsi_zone,
        "price_vs_ma": price_vs_ma,
        "confidence": confidence,
    }
