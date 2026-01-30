"""Trading style classification for watchlist intelligence.

This module classifies recommended trading styles (Index, Trend, Value, Swing, Event)
based on stock characteristics and market conditions.
"""

from __future__ import annotations

from .models import TradingStyleDict

# Common index ETFs (used for trading style classification)
INDEX_ETFS = {"SPY", "VOO", "VTI", "QQQ", "IWM", "DIA", "AGG", "BND"}


def classify_trading_style(
    symbol: str,
    signal_strength: int,
    signal_type: str,
    rsi_14: float,
    earnings_days_away: int | None,
) -> TradingStyleDict:
    """Classify recommended trading style using simplified heuristics.

    Classification hierarchy (checked in order):
    1. Index: Symbol in hardcoded ETF list
    2. Event: Earnings within 7 days
    3. Swing: RSI in reversal zones [30-40] or [60-70]
    4. Trend: Strong BUY signal (strength >= 8)
    5. Value: Default fallback

    Args:
        symbol: Stock symbol
        signal_strength: Signal strength (0-10)
        signal_type: Signal type (BUY, HOLD, AVOID)
        rsi_14: 14-day RSI indicator
        earnings_days_away: Days until next earnings (None if unknown)

    Returns:
        Dictionary with:
        - style: Trading style (Index/Trend/Value/Swing/Event)
        - confidence: Confidence level (0-10)
        - holding_period: Recommended holding timeframe
        - risk_level: Risk profile (Low/Medium-Low/Medium/High)
    """
    # Index: Hardcoded ETF list (highest priority)
    if symbol.upper() in INDEX_ETFS:
        return {
            "style": "Index",
            "confidence": 10,
            "holding_period": "Hold indefinitely",
            "risk_level": "Low",
        }

    # Event: Earnings within 7 days (catalyst-driven)
    if earnings_days_away is not None and earnings_days_away < 7:
        return {
            "style": "Event",
            "confidence": 8,
            "holding_period": "Days to weeks",
            "risk_level": "High",
        }

    # Swing: RSI in reversal zones (oversold 30-40 or overbought 60-70)
    if (30 <= rsi_14 <= 40) or (60 <= rsi_14 <= 70):
        return {
            "style": "Swing",
            "confidence": 7,
            "holding_period": "1-3 weeks",
            "risk_level": "Medium",
        }

    # Trend: Strong BUY signal (strength >= 8)
    if signal_strength >= 8 and signal_type == "BUY":
        return {
            "style": "Trend",
            "confidence": 9,
            "holding_period": "2-3 months",
            "risk_level": "Medium",
        }

    # Value: Default fallback (patient hold)
    return {
        "style": "Value",
        "confidence": 6,
        "holding_period": "6-12 months",
        "risk_level": "Medium-Low",
    }
