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
from typing import Any, Literal

from app.analytics.indicators import calculate_indicators_for_symbol
from app.storage import PortfolioStorage


def classify_trend_strength(
    price: float, sma_20: float, sma_50: float, sma_200: float
) -> Literal["strong_up", "weak_up", "neutral", "weak_down", "strong_down"]:
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
    macd_data: dict[str, Any] | float,
) -> Literal["accelerating", "steady", "decelerating"]:
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


def classify_rsi_zone(rsi_14: float) -> Literal["oversold", "healthy", "overbought"]:
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
    trend_duration_days = 0
    if trend_rows:
        for i, row in enumerate(trend_rows):
            if trend_strength in ["strong_up", "weak_up"]:
                if row["close"] > sma_20:
                    trend_duration_days = i + 1
                else:
                    break
            elif trend_strength in ["strong_down", "weak_down"]:
                if row["close"] < sma_20:
                    trend_duration_days = i + 1
                else:
                    break
            else:
                break
    return trend_duration_days


def analyze_volume_profile(
    storage: PortfolioStorage, symbol: str
) -> Literal["increasing", "stable", "decreasing"]:
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
    if volume_rows and len(volume_rows) >= 20:
        recent_5d_avg = sum(row["volume"] for row in volume_rows[:5]) / 5
        recent_20d_avg = sum(row["volume"] for row in volume_rows) / 20
        if recent_5d_avg > recent_20d_avg * 1.2:
            return "increasing"
        if recent_5d_avg < recent_20d_avg * 0.8:
            return "decreasing"
    return "stable"


def aggregate_technical_analysis(
    storage: PortfolioStorage, symbol: str, as_of_date: date
) -> dict[str, Any]:
    """Aggregate technical indicators and trends.

    Args:
        storage: Portfolio storage instance
        symbol: Stock symbol
        as_of_date: Date to analyze

    Returns:
        Dict with technical analysis fields
    """
    # Calculate indicators using existing function
    indicators = calculate_indicators_for_symbol(
        symbol, indicators=["rsi", "macd", "sma_20", "sma_50", "sma_200", "ema_20", "atr"]
    )

    if not indicators:
        # No technical data available
        return {
            "trend_strength": "neutral",
            "trend_duration_days": 0,
            "momentum_rating": "steady",
            "volume_profile": "stable",
            "rsi_zone": "healthy",
            "price_vs_ma": {"20d": 1.0, "50d": 1.0, "200d": 1.0},
            "confidence": 0.0,
        }

    # Get current price
    current_price = storage.get_current_price(symbol)
    if current_price is None:
        current_price = 100.0

    # Extract indicators
    rsi_14 = indicators.get("rsi_14", 50.0)
    sma_20 = indicators.get("sma_20", current_price)
    sma_50 = indicators.get("sma_50", current_price)
    sma_200 = indicators.get("sma_200", current_price)

    # Classify trend strength
    trend_strength = classify_trend_strength(current_price, sma_20, sma_50, sma_200)

    # Calculate trend duration (days above/below key moving average)
    trend_duration_days = calculate_trend_duration(storage, symbol, trend_strength, sma_20)

    # Classify momentum
    macd_data = indicators.get("macd_12_26_9", {})
    momentum_rating = analyze_momentum(macd_data)

    # Volume profile (requires recent volume data)
    volume_profile = analyze_volume_profile(storage, symbol)

    # RSI zone classification
    rsi_zone = classify_rsi_zone(rsi_14)

    # Price vs moving averages
    price_vs_ma = {
        "20d": round(current_price / sma_20, 4) if sma_20 > 0 else 1.0,
        "50d": round(current_price / sma_50, 4) if sma_50 > 0 else 1.0,
        "200d": round(current_price / sma_200, 4) if sma_200 > 0 else 1.0,
    }

    # Confidence (1.0 if we have 252 days of data)
    bar_count_val = storage.get_bar_count(symbol)
    confidence = 1.0 if bar_count_val >= 252 else (bar_count_val / 252.0)

    return {
        "trend_strength": trend_strength,
        "trend_duration_days": trend_duration_days,
        "momentum_rating": momentum_rating,
        "volume_profile": volume_profile,
        "rsi_zone": rsi_zone,
        "price_vs_ma": price_vs_ma,
        "confidence": confidence,
    }
