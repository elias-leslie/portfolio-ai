"""Signal scoring component functions for watchlist intelligence.

This module contains scoring logic for different signal components:
- Fundamental scoring (profit margin, revenue growth, debt)
- Analyst scoring (recommendations, buy percentage)
- News sentiment scoring
- Options flow scoring
- Technical signal checks (buy/avoid indicators)
"""

from __future__ import annotations

from .models import NormalizedSignalInputsDict


def calculate_fundamental_component_score(
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


def calculate_analyst_component_score(
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


def calculate_news_sentiment_score(news_sentiment: float) -> tuple[int, list[str]]:
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


def calculate_options_flow_score(
    options_call_pct: float | None,
    symbol_in_active_sector: bool | None,
) -> tuple[int, list[str]]:
    """Calculate 0-4 point options flow sentiment score (GAP-031).

    Options flow provides insight into institutional positioning:
    - Call % > 55%: Bullish sentiment (institutions buying upside)
    - Call % < 45%: Bearish sentiment (put buying for protection/bet)

    Args:
        options_call_pct: Percentage of call volume (0.0-1.0)
        symbol_in_active_sector: True if symbol's sector has high options volume

    Returns:
        (score, reasons) where score is 0-4 based on options sentiment
    """
    if options_call_pct is None:
        return 0, []

    score = 0
    reasons: list[str] = []

    # Call/put ratio component (0-3 points)
    # >58%: Strong bullish (institutional upside bets)
    # 55-58%: Moderate bullish
    # 45-55%: Neutral (no signal)
    # <45%: Bearish (put buying)
    if options_call_pct >= 0.58:
        score += 3
        reasons.append(f"Options flow bullish: {options_call_pct:.0%} calls")
    elif options_call_pct >= 0.55:
        score += 2
        reasons.append(f"Options flow moderately bullish: {options_call_pct:.0%} calls")
    elif options_call_pct >= 0.52:
        score += 1
        reasons.append(f"Options flow slightly bullish: {options_call_pct:.0%} calls")
    elif options_call_pct < 0.45:
        # Bearish signal - don't add points, could subtract in AVOID logic
        reasons.append(f"Options flow bearish: {options_call_pct:.0%} calls")

    # Sector activity bonus (0-1 point)
    # Ticker in active sector gets a conviction boost
    if symbol_in_active_sector:
        score += 1
        reasons.append("Sector has high options activity")

    return score, reasons


def check_avoid_signals(data: NormalizedSignalInputsDict) -> tuple[int, list[str]]:
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


def check_buy_signals(data: NormalizedSignalInputsDict) -> tuple[int, list[str]]:
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
    # by calculate_fundamental_component_score and calculate_news_sentiment_score
    # respectively, with graded rather than binary scoring.

    return confirmations, reasons


def calculate_signal_strength(confirmations: int) -> int:
    """Calculate signal strength from confirmation count (Task 0074 updated).

    NEW Scoring System (Task 0074):
    - 6 technical confirmations (from check_buy_signals)
    - 5 fundamental points (from calculate_fundamental_component_score): -3 to +5
    - 5 analyst points (from calculate_analyst_component_score): 0 to +5
    - 5 news points (from calculate_news_sentiment_score): 0 to +5

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
