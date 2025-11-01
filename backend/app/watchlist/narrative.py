"""Narrative generation and signal classification for watchlist intelligence."""

from __future__ import annotations

from typing import Any

from .models import SignalClassification, SignalStrength, SignalType

# Narrative templates: Translate technical indicators to plain language (zero jargon)
NARRATIVE_TEMPLATES: dict[str, str] = {
    # Trend templates
    "uptrend": "Stock is in an uptrend (rising steadily)",
    "downtrend": "Stock is in a downtrend (falling steadily)",
    "sideways": "Stock is moving sideways (range-bound)",
    # Entry templates
    "pullback": "Just pulled back to a good entry point",
    "breakout": "Breaking out to new highs",
    "support": "Bouncing off support level",
    # Momentum templates
    "momentum_positive": "Momentum is positive (buyers are in control)",
    "momentum_negative": "Momentum is negative (sellers are in control)",
    "momentum_neutral": "Momentum is neutral (waiting for direction)",
    # Volume templates
    "volume_high": "Excellent volume - strong conviction",
    "volume_low": "Low volume - weak participation",
    "volume_average": "Normal volume - steady activity",
    # Condition templates
    "overbought": "Already extended - just hit new high",
    "oversold": "Oversold - potential bounce opportunity",
    "healthy": "Healthy pullback - normal profit-taking",
    # Company health templates
    "excellent_company": "Top-tier company with strong fundamentals",
    "good_company": "Solid company with decent fundamentals",
    "weak_company": "Struggling company with weak fundamentals",
    # News templates
    "positive_news": "Recent positive news driving interest",
    "negative_news": "Recent negative news causing concern",
    "neutral_news": "News flow is neutral",
}


def generate_headline(classification: SignalClassification) -> str:
    """Generate a plain-language headline for the signal classification.

    Args:
        classification: Signal classification with type, strength, and reasons

    Returns:
        Headline string in format: "{SIGNAL_TYPE} - {primary_reason}"
    """
    signal_str = classification.signal_type.value  # BUY, HOLD, or AVOID

    # Add strength descriptor for BUY signals
    if classification.signal_type == SignalType.BUY:
        if classification.strength.value >= 8:
            signal_str = "STRONG BUY"
        elif classification.strength.value >= 6:
            signal_str = "BUY"

    # Extract primary reason (first reason is usually most important)
    if classification.reasons:
        # Take first reason and simplify it
        primary_reason = classification.reasons[0]
        # Remove technical details in parentheses if present
        if "(" in primary_reason:
            primary_reason = primary_reason.split("(")[0].strip()
    # Fallback reason based on signal type
    elif classification.signal_type == SignalType.BUY:
        primary_reason = "Good setup"
    elif classification.signal_type == SignalType.AVOID:
        primary_reason = "Risk factors present"
    else:
        primary_reason = "Mixed signals"

    return f"{signal_str} - {primary_reason}"


def generate_technical_bullets(inputs: dict[str, Any]) -> list[str]:
    """Generate plain-language technical setup bullets (zero jargon).

    Args:
        inputs: Dictionary containing technical indicator values

    Returns:
        List of 3-5 plain-language bullet points
    """
    bullets: list[str] = []

    # Extract inputs
    price = inputs.get("price", 0.0)
    ema_20 = inputs.get("ema_20", 0.0)
    rsi_14 = inputs.get("rsi_14", 50.0)
    macd = inputs.get("macd", 0.0)
    volume = inputs.get("volume", 0.0)
    volume_avg_20 = inputs.get("volume_avg_20", 0.0)

    # Translate price vs EMA (trend)
    if price > 0 and ema_20 > 0:
        if price > ema_20:
            pct_above = ((price - ema_20) / ema_20) * 100
            if pct_above >= 5:
                bullets.append("Strong uptrend - making higher highs")
            else:
                bullets.append("In uptrend - rising steadily")
        else:
            pct_below = ((ema_20 - price) / ema_20) * 100
            if pct_below >= 5:
                bullets.append("In downtrend - falling steadily")
            else:
                bullets.append("Below recent average - weak trend")

    # Translate RSI (momentum condition)
    if rsi_14 > 70:
        bullets.append("Already extended - just hit new high")
    elif rsi_14 < 30:
        bullets.append("Oversold - potential bounce opportunity")
    elif 40 <= rsi_14 <= 60:
        bullets.append("Healthy momentum - normal trading")
    elif rsi_14 < 40:
        bullets.append("Some weakness showing - sellers active")

    # Translate MACD (momentum direction)
    if macd > 0:
        bullets.append("Buyers active - momentum positive")
    elif macd < 0:
        bullets.append("Sellers active - momentum negative")

    # Translate volume
    if volume_avg_20 > 0 and volume > 0:
        volume_ratio = volume / volume_avg_20
        if volume_ratio >= 1.5:
            bullets.append("Excellent volume - strong conviction")
        elif volume_ratio >= 0.7:
            bullets.append("Normal volume - steady activity")
        else:
            bullets.append("Low volume - weak participation")

    # Ensure we have at least 3 bullets
    if len(bullets) < 3:
        bullets.append("Limited technical data available")

    return bullets[:5]  # Cap at 5 bullets


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
