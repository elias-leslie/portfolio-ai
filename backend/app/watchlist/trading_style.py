"""Descriptive setup heuristics, without unsupported risk or return precision."""

from __future__ import annotations

from .models import TradingStyleDict

INDEX_ETFS = {"SPY", "VOO", "VTI", "QQQ", "IWM", "DIA", "AGG", "BND"}


def classify_trading_style(
    symbol: str,
    signal_strength: int,
    signal_type: str,
    rsi_14: float,
    earnings_days_away: int | None,
) -> TradingStyleDict:
    """Name an observed setup pattern, not a worked investment thesis.

    No pattern is evidence of value, a calibrated success probability, a
    suitable holding period, or an investor's risk level. Those remain unknown.
    """
    style = None
    if symbol.upper() in INDEX_ETFS:
        style = "Index"
    elif earnings_days_away is not None and 0 <= earnings_days_away < 7:
        style = "Event"
    elif 30 <= rsi_14 <= 40 or 60 <= rsi_14 <= 70:
        style = "Swing"
    elif signal_strength >= 8 and signal_type == "BUY":
        style = "Trend"
    return {"style": style, "confidence": None, "holding_period": None, "risk_level": None}
