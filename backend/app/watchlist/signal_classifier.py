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
        # Fundamental component fields (Task 0074)
        "profit_margin": inputs.get("profit_margin"),
        "revenue_growth": inputs.get("revenue_growth"),
        "debt_to_equity": inputs.get("debt_to_equity"),
        # Analyst component fields (Task 0074)
        "recommendation_mean": inputs.get("recommendation_mean"),
        "analyst_buy_pct": inputs.get("analyst_buy_pct"),
    }


def _calculate_fundamental_component_score(
    profit_margin: float | None,
    revenue_growth: float | None,
    debt_to_equity: float | None,
) -> tuple[int, list[str]]:
    """Calculate 0-5 point fundamental component score (Task 0074).

    Returns:
        (score, reasons) where score ranges -3 to +5 based on:
        - Profit margin: +2 if >20%, +1 if 5-20%, 0 if <5%, -1 if negative
        - Revenue growth: +2 if >20%, +1 if 5-20%, 0 if <5%, -1 if negative
        - Debt health: +1 if <0.5, +0 if 0.5-1.5, -1 if >1.5
    """
    score = 0
    reasons: list[str] = []

    # Profit margin scoring (None = 0 contribution)
    if profit_margin is not None:
        margin_pct = profit_margin * 100
        if profit_margin > 0.20:
            score += 2
            reasons.append(f"Very profitable - {margin_pct:.1f}% margin")
        elif profit_margin > 0.05:
            score += 1
            reasons.append(f"Profitable - {margin_pct:.1f}% margin")
        elif profit_margin < 0:
            score -= 1
            reasons.append(f"Unprofitable - {margin_pct:.1f}% margin")
        # 0-5% = 0 points, no reason added

    # Revenue growth scoring (None = 0 contribution)
    if revenue_growth is not None:
        growth_pct = revenue_growth * 100
        if revenue_growth > 0.20:
            score += 2
            reasons.append(f"Strong growth - {growth_pct:.1f}%")
        elif revenue_growth > 0.05:
            score += 1
            reasons.append(f"Growing - {growth_pct:.1f}%")
        elif revenue_growth < 0:
            score -= 1
            reasons.append("Revenue declining")
        # 0-5% = 0 points, no reason added

    # Debt health scoring (None = 0 contribution)
    if debt_to_equity is not None:
        if debt_to_equity < 0.5:
            score += 1
            reasons.append("Low debt - strong balance sheet")
        elif debt_to_equity > 1.5:
            score -= 1
            reasons.append("High debt - balance sheet concern")
        # 0.5-1.5 = 0 points, moderate debt is neutral

    return score, reasons


def _calculate_analyst_component_score(
    recommendation_mean: float | None,
    analyst_buy_pct: float | None,
) -> tuple[int, list[str]]:
    """Calculate 0-5 point analyst component score (Task 0074).

    Analyst recommendation scale: 1.0=strong buy, 5.0=sell

    Returns:
        (score, reasons) where score ranges 0-5 based on:
        - Recommendation mean: +3 if <2.0, +2 if 2.0-2.5, +1 if 2.5-3.0, 0 if >3.0
        - Analyst buy %: +2 if >70%, +1 if 50-70%, 0 if <50%
    """
    score = 0
    reasons: list[str] = []

    # Recommendation mean scoring (None = 0 contribution)
    if recommendation_mean is not None:
        if recommendation_mean < 2.0:
            score += 3
            reasons.append(f"Analyst strong buy - {recommendation_mean:.1f}/5.0")
        elif recommendation_mean < 2.5:
            score += 2
            reasons.append(f"Analyst buy - {recommendation_mean:.1f}/5.0")
        elif recommendation_mean < 3.0:
            score += 1
            reasons.append(f"Analyst hold - {recommendation_mean:.1f}/5.0")
        # >3.0 = sell consensus, 0 points

    # Analyst buy percentage scoring (None = 0 contribution)
    if analyst_buy_pct is not None:
        buy_pct = analyst_buy_pct * 100
        if analyst_buy_pct > 0.70:
            score += 2
            reasons.append(f"{buy_pct:.0f}% analysts recommend buy")
        elif analyst_buy_pct > 0.50:
            score += 1
            reasons.append(f"{buy_pct:.0f}% analysts recommend buy")
        # <50% = 0 points

    return score, reasons


def _calculate_news_sentiment_score(news_sentiment: float) -> tuple[int, list[str]]:
    """Calculate 0-5 point continuous news sentiment score (Task 0074).

    Scales -1..+1 sentiment to 0..5 points.

    Returns:
        (score, reasons) where score is continuous based on sentiment value.
    """
    # Scale -1..+1 to 0..5 (linear mapping)
    scaled_score = int((news_sentiment + 1.0) / 2.0 * 5.0)
    # Clamp to valid range
    scaled_score = max(0, min(5, scaled_score))

    reasons: list[str] = []
    if news_sentiment >= 0.2:
        reasons.append(f"News sentiment {news_sentiment:.2f} (positive)")
    elif news_sentiment <= -0.3:
        reasons.append(f"News sentiment {news_sentiment:.2f} (negative)")

    return scaled_score, reasons


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
    """Check for BUY signals and count positive indicators (technical only).

    Note: Company health and news sentiment are now handled by component scoring
    in classify_signal() (Task 0074).

    Args:
        data: Normalized signal inputs

    Returns:
        Tuple of (confirmations_count, reasons_list)
    """
    confirmations = 0
    reasons: list[str] = []

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

    # Check 5: Not overbought (RSI <= 70)
    if data["rsi_14"] <= 70:
        confirmations += 1

    # Check 6: Strong uptrend confirmation (price significantly above EMA)
    if data["ema_20"] > 0 and (data["price"] - data["ema_20"]) / data["ema_20"] >= 0.02:
        confirmations += 1

    # Note: Company health (Check 5) and news sentiment (Check 6) are now handled
    # by _calculate_fundamental_component_score and _calculate_news_sentiment_score
    # respectively, with graded rather than binary scoring.

    return confirmations, reasons


def _calculate_signal_strength(confirmations: int) -> int:
    """Calculate signal strength from confirmation count (Task 0074 updated).

    NEW Scoring System (Task 0074):
    - 6 technical confirmations (from _check_buy_signals)
    - 5 fundamental points (from _calculate_fundamental_component_score): -3 to +5
    - 5 analyst points (from _calculate_analyst_component_score): 0 to +5
    - 5 news points (from _calculate_news_sentiment_score): 0 to +5

    Total range: -3 to +21 confirmations
    Maps to 0-10 strength using: (confirmations + 3) / 2.4

    Args:
        confirmations: Number of positive confirmations (-3 to +21 range)

    Returns:
        Strength value (0-10 scale)
    """
    # Map expanded range to 0-10 scale
    # Formula: (confirmations + 3) / 2.4 gives us 0-10 for -3 to +21 range
    strength = int((confirmations + 3) / 2.4)
    return max(0, min(10, strength))


def classify_signal(inputs: SignalInputsDict) -> SignalClassification:
    """Classify watchlist signal as BUY, HOLD, or AVOID based on multiple indicators.

    NEW Scoring System (Task 0074):
    - Technical signals: 0-6 points (from _check_buy_signals)
    - Fundamental component: -3 to +5 points (profit margin, revenue growth, debt)
    - Analyst component: 0-5 points (recommendation mean, buy %)
    - News sentiment: 0-5 points (scaled from -1..+1)

    Total range: -3 to +21 confirmations → 0-10 strength

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
            - profit_margin: Profit margin as decimal (0.20 = 20%)
            - revenue_growth: Revenue growth as decimal (0.25 = 25%)
            - debt_to_equity: Debt-to-equity ratio (0.5 = 50%)
            - recommendation_mean: Analyst recommendation (1.0-5.0)
            - analyst_buy_pct: Analyst buy percentage (0.0-1.0)

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

    # Check for BUY signals (technical indicators only)
    confirmations, buy_reasons = _check_buy_signals(data)

    # Add fundamental component score (Task 0074)
    fundamental_score, fundamental_reasons = _calculate_fundamental_component_score(
        profit_margin=data["profit_margin"],
        revenue_growth=data["revenue_growth"],
        debt_to_equity=data["debt_to_equity"],
    )
    confirmations += fundamental_score
    buy_reasons.extend(fundamental_reasons)

    # Add analyst component score (Task 0074)
    analyst_score, analyst_reasons = _calculate_analyst_component_score(
        recommendation_mean=data["recommendation_mean"],
        analyst_buy_pct=data["analyst_buy_pct"],
    )
    confirmations += analyst_score
    buy_reasons.extend(analyst_reasons)

    # Add continuous news sentiment score (Task 0074)
    news_score, news_reasons = _calculate_news_sentiment_score(data["news_sentiment"])
    confirmations += news_score
    buy_reasons.extend(news_reasons)

    # Calculate signal strength using expanded range
    strength_value = _calculate_signal_strength(confirmations)

    # Determine signal type based on confirmations
    # Adjusted threshold: 10+ confirmations for BUY (was 6, now accounts for expanded range)
    # 10 confirmations ≈ 50% of max (21), similar to old 6/12 (8 technical + 4 from components)
    signal_type = SignalType.BUY if confirmations >= 10 else SignalType.HOLD

    return SignalClassification(
        signal_type=signal_type,
        strength=SignalStrength(value=strength_value),
        reasons=buy_reasons,
    )
