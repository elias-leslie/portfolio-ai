"""Narrative generation and signal classification for watchlist intelligence."""

from __future__ import annotations

from typing import Any

from .models import SignalClassification, SignalStrength, SignalType


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

    # Extract inputs
    price = inputs.get("price", 0.0)
    ema_20 = inputs.get("ema_20", 0.0)
    sma_5 = inputs.get("sma_5", 0.0)
    sma_5_prev = inputs.get("sma_5_prev", 0.0)
    rsi_14 = inputs.get("rsi_14", 50.0)
    macd = inputs.get("macd", 0.0)
    volume = inputs.get("volume", 0.0)
    volume_avg_20 = inputs.get("volume_avg_20", 0.0)
    company_health = inputs.get("company_health", "")
    news_sentiment = inputs.get("news_sentiment", 0.0)
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

    # If multiple AVOID flags, classify as AVOID with low strength
    if avoid_flags >= 3:
        # More avoid flags = lower strength (inverted)
        # 3 flags → 3, 4 flags → 2, 5 flags → 1, 6+ flags → 0
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
