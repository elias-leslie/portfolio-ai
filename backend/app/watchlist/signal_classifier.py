"""Signal classification logic for watchlist intelligence.

This module orchestrates signal classification (BUY/HOLD/AVOID) by coordinating
technical indicators, company fundamentals, and market conditions.

Component modules:
- signal_scoring: Individual scoring functions for each signal component
- trading_style: Trading style classification logic
"""

from __future__ import annotations

from .models import (
    NormalizedSignalInputsDict,
    SignalClassification,
    SignalInputsDict,
    SignalStrength,
    SignalType,
)
from .signal_scoring import (
    calculate_analyst_component_score,
    calculate_fundamental_component_score,
    calculate_news_sentiment_score,
    calculate_options_flow_score,
    calculate_signal_strength,
    check_avoid_signals,
    check_buy_signals,
)


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
        # Options flow fields (GAP-031)
        "options_call_pct": inputs.get("options_call_pct"),
        "options_near_term_pct": inputs.get("options_near_term_pct"),
        "symbol_in_active_sector": inputs.get("symbol_in_active_sector"),
        # Earnings surprise fields (GAP-003)
        "earnings_surprise_score": inputs.get("earnings_surprise_score"),
        "earnings_surprise_reasons": inputs.get("earnings_surprise_reasons"),
    }


def classify_signal(inputs: SignalInputsDict) -> SignalClassification:
    """Classify watchlist signal as BUY, HOLD, or AVOID based on multiple indicators.

    Scoring System (Task 0074 + GAP-031 + GAP-003):
    - Technical signals: 0-6 points (from check_buy_signals)
    - Fundamental component: -3 to +5 points (profit margin, revenue growth, debt)
    - Analyst component: 0-5 points (recommendation mean, buy %)
    - News sentiment: 0-5 points (scaled from -1..+1)
    - Options flow: 0-4 points (call %, sector activity) [GAP-031]
    - Earnings surprise: -1 to +4 points (beat/miss history) [GAP-003]

    Total range: -4 to +29 confirmations → 0-10 strength

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
    avoid_flags, avoid_reasons = check_avoid_signals(data)

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
    confirmations, buy_reasons = check_buy_signals(data)

    # Add fundamental component score (Task 0074)
    fundamental_score, fundamental_reasons = calculate_fundamental_component_score(
        profit_margin=data["profit_margin"],
        revenue_growth=data["revenue_growth"],
        debt_to_equity=data["debt_to_equity"],
    )
    confirmations += fundamental_score
    buy_reasons.extend(fundamental_reasons)

    # Add analyst component score (Task 0074)
    analyst_score, analyst_reasons = calculate_analyst_component_score(
        recommendation_mean=data["recommendation_mean"],
        analyst_buy_pct=data["analyst_buy_pct"],
    )
    confirmations += analyst_score
    buy_reasons.extend(analyst_reasons)

    # Add continuous news sentiment score (Task 0074)
    news_score, news_reasons = calculate_news_sentiment_score(data["news_sentiment"])
    confirmations += news_score
    buy_reasons.extend(news_reasons)

    # Add options flow component score (GAP-031)
    options_score, options_reasons = calculate_options_flow_score(
        options_call_pct=data["options_call_pct"],
        symbol_in_active_sector=data["symbol_in_active_sector"],
    )
    confirmations += options_score
    buy_reasons.extend(options_reasons)

    # Add earnings surprise component score (GAP-003)
    # Score is pre-computed and passed in (requires database access)
    earnings_surprise_score = data.get("earnings_surprise_score")
    earnings_surprise_reasons = data.get("earnings_surprise_reasons")
    if earnings_surprise_score is not None:
        confirmations += earnings_surprise_score
        if earnings_surprise_reasons:
            buy_reasons.extend(earnings_surprise_reasons)

    # Calculate signal strength using expanded range
    strength_value = calculate_signal_strength(confirmations)

    # Determine signal type based on confirmations
    # Adjusted threshold: 10+ confirmations for BUY (was 6, now accounts for expanded range)
    # 10 confirmations ≈ 50% of max (21), similar to old 6/12 (8 technical + 4 from components)
    signal_type = SignalType.BUY if confirmations >= 10 else SignalType.HOLD

    return SignalClassification(
        signal_type=signal_type,
        strength=SignalStrength(value=strength_value),
        reasons=buy_reasons,
    )
