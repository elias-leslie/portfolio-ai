"""Signal classification logic for watchlist intelligence.

This module classifies trading signals (BUY/HOLD/AVOID) and trading styles
based on technical indicators, company fundamentals, and market conditions.
"""

from __future__ import annotations

from typing import Any

from .models import SignalClassification, SignalStrength, SignalType

# Common index ETFs (used for trading style classification)
INDEX_ETFS = {"SPY", "VOO", "VTI", "QQQ", "IWM", "DIA", "AGG", "BND"}


def classify_trading_style(
    symbol: str,
    signal_strength: int,
    signal_type: str,
    rsi_14: float,
    earnings_days_away: int | None,
) -> dict[str, Any]:
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


def classify_signal(inputs: dict[str, Any]) -> SignalClassification:
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
    reasons: list[str] = []
    confirmations = 0
    avoid_flags = 0  # Count of negative indicators

    # Extract inputs (handle None values with or operator)
    price = inputs.get("price", 0.0) or 0.0
    ema_20 = inputs.get("ema_20", 0.0) or 0.0
    sma_5 = inputs.get("sma_5", 0.0) or 0.0
    sma_5_prev = inputs.get("sma_5_prev", 0.0) or 0.0
    rsi_14 = inputs.get("rsi_14", 50.0) or 50.0
    macd = inputs.get("macd", 0.0) or 0.0
    volume = inputs.get("volume", 0.0) or 0.0
    volume_avg_20 = inputs.get("volume_avg_20", 0.0) or 0.0
    company_health = inputs.get("company_health", "") or ""
    news_sentiment = inputs.get("news_sentiment", 0.0) or 0.0
    earnings_days_away = inputs.get("earnings_days_away")

    # Check for AVOID signals (negative indicators)
    # AVOID Check 1: Price < 20-day EMA AND 5-day SMA declining
    if price < ema_20 and sma_5_prev > 0 and sma_5 < sma_5_prev:
        avoid_flags += 1
        reasons.append(f"Price ${price:.2f} below 20-day EMA ${ema_20:.2f} (downtrend)")

    # AVOID Check 2: News sentiment < -0.3 (significantly negative)
    if news_sentiment < -0.3:
        avoid_flags += 1
        reasons.append(f"News sentiment {news_sentiment:.2f} (significantly negative)")

    # AVOID Check 3: Earnings within 5 days (high volatility risk)
    if earnings_days_away is not None and earnings_days_away <= 5:
        avoid_flags += 1
        reasons.append(f"Earnings in {earnings_days_away} days (high volatility risk)")

    # AVOID Check 4: Company health = WEAK
    if company_health == "WEAK":
        avoid_flags += 1
        reasons.append(f"Company health: {company_health}")

    # AVOID: 2 or more negative flags (lowered from 3 for better detection)
    if avoid_flags >= 2:
        # More avoid flags = lower strength (inverted)
        # 2 flags → 4, 3 flags → 3, 4 flags → 2, 5 flags → 1, 6+ flags → 0
        strength_value = max(0, 6 - avoid_flags)
        return SignalClassification(
            signal_type=SignalType.AVOID,
            strength=SignalStrength(value=strength_value),
            reasons=reasons,
        )

    # Check for BUY signals (positive indicators)
    # Check 1: Price > 20-day EMA (uptrend)
    if price > ema_20:
        confirmations += 1
        reasons.append(f"Price ${price:.2f} > 20-day EMA ${ema_20:.2f} (uptrend)")

    # Check 2: RSI between 30-70 (not extreme)
    if 30 <= rsi_14 <= 70:
        confirmations += 1
        reasons.append(f"RSI at {rsi_14:.0f} (healthy, not extreme)")

    # Check 3: MACD > 0 (positive momentum)
    if macd > 0:
        confirmations += 1
        reasons.append(f"MACD {macd:.2f} positive (momentum)")

    # Check 4: Volume >= 70% of 20-day average
    if volume_avg_20 > 0 and volume >= 0.7 * volume_avg_20:
        confirmations += 1
        volume_pct = (volume / volume_avg_20) * 100
        reasons.append(f"Volume {volume_pct:.0f}% of average (strong)")

    # Check 5: Company health = EXCELLENT or GOOD
    if company_health in ("EXCELLENT", "GOOD"):
        confirmations += 1
        reasons.append(f"Company health: {company_health}")

    # Check 6: News sentiment >= 0.2 (positive)
    if news_sentiment >= 0.2:
        confirmations += 1
        reasons.append(f"News sentiment {news_sentiment:.2f} (positive)")

    # Check 7: Not overbought (RSI <= 70)
    if rsi_14 <= 70:
        confirmations += 1

    # Check 8: Strong uptrend confirmation (price significantly above EMA)
    if ema_20 > 0 and (price - ema_20) / ema_20 >= 0.02:  # At least 2% above EMA
        confirmations += 1

    # Calculate signal strength (0-10 scale)
    # 8+ confirmations → 9/10, 5-7 → 6-8/10, 0-4 → 0-5/10
    if confirmations >= 8:
        strength_value = 9
    elif confirmations >= 7:
        strength_value = 8
    elif confirmations >= 6:
        strength_value = 7
    elif confirmations >= 5:
        strength_value = 6
    else:
        strength_value = min(confirmations, 5)

    # Determine signal type based on confirmations and specific criteria
    if confirmations >= 6:
        signal_type = SignalType.BUY
    else:
        signal_type = SignalType.HOLD

    return SignalClassification(
        signal_type=signal_type,
        strength=SignalStrength(value=strength_value),
        reasons=reasons,
    )
