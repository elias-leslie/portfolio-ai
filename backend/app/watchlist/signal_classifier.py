"""Signal classification logic for watchlist intelligence.

This module classifies trading signals (BUY/HOLD/AVOID) and trading styles
based on technical indicators, company fundamentals, and market conditions.
"""

from __future__ import annotations

from .models import (
    NormalizedSignalInputsDict,
    SignalClassification,
    SignalInputsDict,
    SignalStrength,
    SignalType,
    TradingStyleDict,
)

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
        symbol: Stock ticker symbol
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


def _extract_signal_inputs(inputs: SignalInputsDict) -> NormalizedSignalInputsDict:
    """Extract and normalize signal classification inputs.

    Args:
        inputs: Raw input dictionary

    Returns:
        Normalized inputs with None values replaced by defaults
    """
    return {
        "price": inputs.get("price", 0.0) or 0.0,
        "ema_20": inputs.get("ema_20", 0.0) or 0.0,
        "sma_5": inputs.get("sma_5", 0.0) or 0.0,
        "sma_5_prev": inputs.get("sma_5_prev", 0.0) or 0.0,
        "rsi_14": inputs.get("rsi_14", 50.0) or 50.0,
        "macd": inputs.get("macd", 0.0) or 0.0,
        "volume": inputs.get("volume", 0.0) or 0.0,
        "volume_avg_20": inputs.get("volume_avg_20", 0.0) or 0.0,
        "company_health": inputs.get("company_health", "") or "",
        "news_sentiment": inputs.get("news_sentiment", 0.0) or 0.0,
        "earnings_days_away": inputs.get("earnings_days_away"),
    }


def _check_avoid_signals(data: NormalizedSignalInputsDict) -> tuple[int, list[str]]:
    """Check for AVOID signals and count negative indicators.

    Args:
        data: Normalized signal inputs

    Returns:
        Tuple of (avoid_flags_count, reasons_list)
    """
    avoid_flags = 0
    reasons = []

    # Check 1: Price < 20-day EMA AND 5-day SMA declining
    if (
        data["price"] < data["ema_20"]
        and data["sma_5_prev"] > 0
        and data["sma_5"] < data["sma_5_prev"]
    ):
        avoid_flags += 1
        reasons.append(
            f"Price ${data['price']:.2f} below 20-day EMA ${data['ema_20']:.2f} (downtrend)"
        )

    # Check 2: News sentiment < -0.3 (significantly negative)
    if data["news_sentiment"] < -0.3:
        avoid_flags += 1
        reasons.append(f"News sentiment {data['news_sentiment']:.2f} (significantly negative)")

    # Check 3: Earnings within 5 days (high volatility risk)
    if data["earnings_days_away"] is not None and data["earnings_days_away"] <= 5:
        avoid_flags += 1
        reasons.append(f"Earnings in {data['earnings_days_away']} days (high volatility risk)")

    # Check 4: Company health = WEAK
    if data["company_health"] == "WEAK":
        avoid_flags += 1
        reasons.append(f"Company health: {data['company_health']}")

    return avoid_flags, reasons


def _check_buy_signals(data: NormalizedSignalInputsDict) -> tuple[int, list[str]]:
    """Check for BUY signals and count positive indicators.

    Args:
        data: Normalized signal inputs

    Returns:
        Tuple of (confirmations_count, reasons_list)
    """
    confirmations = 0
    reasons = []

    # Check 1: Price > 20-day EMA (uptrend)
    if data["price"] > data["ema_20"]:
        confirmations += 1
        reasons.append(f"Price ${data['price']:.2f} > 20-day EMA ${data['ema_20']:.2f} (uptrend)")

    # Check 2: RSI between 30-70 (not extreme)
    if 30 <= data["rsi_14"] <= 70:
        confirmations += 1
        reasons.append(f"RSI at {data['rsi_14']:.0f} (healthy, not extreme)")

    # Check 3: MACD > 0 (positive momentum)
    if data["macd"] > 0:
        confirmations += 1
        reasons.append(f"MACD {data['macd']:.2f} positive (momentum)")

    # Check 4: Volume >= 70% of 20-day average
    if data["volume_avg_20"] > 0 and data["volume"] >= 0.7 * data["volume_avg_20"]:
        confirmations += 1
        volume_pct = (data["volume"] / data["volume_avg_20"]) * 100
        reasons.append(f"Volume {volume_pct:.0f}% of average (strong)")

    # Check 5: Company health = EXCELLENT or GOOD
    if data["company_health"] in ("EXCELLENT", "GOOD"):
        confirmations += 1
        reasons.append(f"Company health: {data['company_health']}")

    # Check 6: News sentiment >= 0.2 (positive)
    if data["news_sentiment"] >= 0.2:
        confirmations += 1
        reasons.append(f"News sentiment {data['news_sentiment']:.2f} (positive)")

    # Check 7: Not overbought (RSI <= 70)
    if data["rsi_14"] <= 70:
        confirmations += 1

    # Check 8: Strong uptrend confirmation (price significantly above EMA)
    if data["ema_20"] > 0 and (data["price"] - data["ema_20"]) / data["ema_20"] >= 0.02:
        confirmations += 1

    return confirmations, reasons


def _calculate_signal_strength(confirmations: int) -> int:
    """Calculate signal strength from confirmation count.

    Args:
        confirmations: Number of positive confirmations (0-8)

    Returns:
        Strength value (0-10 scale)
    """
    if confirmations >= 8:
        return 9
    if confirmations >= 7:
        return 8
    if confirmations >= 6:
        return 7
    if confirmations >= 5:
        return 6
    return min(confirmations, 5)


def classify_signal(inputs: SignalInputsDict) -> SignalClassification:
    """Classify watchlist signal as BUY, HOLD, or AVOID based on multiple indicators.

    Args:
        inputs: Dictionary containing:
            - price: Current stock price
            - ema_20: 20-day exponential moving average
            - sma_5: 5-day simple moving average
            - sma_5_prev: Previous 5-day SMA (for trend detection)
            - rsi_14: 14-day RSI indicator
            - macd: MACD indicator value
            - volume: Current volume
            - volume_avg_20: 20-day average volume
            - company_health: Company health rating (EXCELLENT, GOOD, WEAK)
            - news_sentiment: News sentiment score (-1.0 to +1.0)
            - earnings_days_away: Days until next earnings (optional)

    Returns:
        SignalClassification with type, strength, and reasons
    """
    # Extract and normalize inputs
    data = _extract_signal_inputs(inputs)

    # Check for AVOID signals first
    avoid_flags, avoid_reasons = _check_avoid_signals(data)

    # AVOID: 2 or more negative flags (lowered from 3 for better detection)
    if avoid_flags >= 2:
        # More avoid flags = lower strength (inverted)
        # 2 flags → 4, 3 flags → 3, 4 flags → 2, 5 flags → 1, 6+ flags → 0
        strength_value = max(0, 6 - avoid_flags)
        return SignalClassification(
            signal_type=SignalType.AVOID,
            strength=SignalStrength(value=strength_value),
            reasons=avoid_reasons,
        )

    # Check for BUY signals (positive indicators)
    confirmations, buy_reasons = _check_buy_signals(data)

    # Calculate signal strength
    strength_value = _calculate_signal_strength(confirmations)

    # Determine signal type based on confirmations
    signal_type = SignalType.BUY if confirmations >= 6 else SignalType.HOLD

    return SignalClassification(
        signal_type=signal_type,
        strength=SignalStrength(value=strength_value),
        reasons=buy_reasons,
    )
