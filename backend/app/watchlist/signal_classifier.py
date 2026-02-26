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
    """Extract and normalize signal classification inputs."""
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


def _accumulate_buy_scores(
    data: NormalizedSignalInputsDict,
) -> tuple[int, list[str]]:
    """Accumulate all buy-side component scores and reasons.

    Scoring System (Task 0074 + GAP-031 + GAP-003):
    - Technical signals: 0-6 points
    - Fundamental component: -3 to +5 points
    - Analyst component: 0-5 points
    - News sentiment: 0-5 points
    - Options flow: 0-4 points [GAP-031]
    - Earnings surprise: -1 to +4 points [GAP-003]
    """
    confirmations, reasons = check_buy_signals(data)

    fundamental_score, fundamental_reasons = calculate_fundamental_component_score(
        profit_margin=data["profit_margin"],
        revenue_growth=data["revenue_growth"],
        debt_to_equity=data["debt_to_equity"],
    )
    confirmations += fundamental_score
    reasons.extend(fundamental_reasons)

    analyst_score, analyst_reasons = calculate_analyst_component_score(
        recommendation_mean=data["recommendation_mean"],
        analyst_buy_pct=data["analyst_buy_pct"],
    )
    confirmations += analyst_score
    reasons.extend(analyst_reasons)

    news_score, news_reasons = calculate_news_sentiment_score(data["news_sentiment"])
    confirmations += news_score
    reasons.extend(news_reasons)

    options_score, options_reasons = calculate_options_flow_score(
        options_call_pct=data["options_call_pct"],
        symbol_in_active_sector=data["symbol_in_active_sector"],
    )
    confirmations += options_score
    reasons.extend(options_reasons)

    # Earnings surprise score is pre-computed (requires database access) [GAP-003]
    earnings_surprise_score = data.get("earnings_surprise_score")
    earnings_surprise_reasons = data.get("earnings_surprise_reasons")
    if earnings_surprise_score is not None:
        confirmations += earnings_surprise_score
        if earnings_surprise_reasons:
            reasons.extend(earnings_surprise_reasons)

    return confirmations, reasons


def classify_signal(inputs: SignalInputsDict) -> SignalClassification:
    """Classify watchlist signal as BUY, HOLD, or AVOID based on multiple indicators.

    Total confirmations range: -4 to +29 → mapped to 0-10 strength.
    Threshold: 10+ confirmations for BUY, otherwise HOLD.

    Returns:
        SignalClassification with type, strength, and reasons
    """
    data = _extract_signal_inputs(inputs)

    # Check for AVOID signals first
    avoid_flags, avoid_reasons = check_avoid_signals(data)
    # AVOID: 2 or more negative flags (lowered from 3 for better detection)
    if avoid_flags >= 2:
        # More avoid flags = lower strength (inverted): 2→4, 3→3, 4→2, 5→1, 6+→0
        strength_value = max(0, 6 - avoid_flags)
        return SignalClassification(
            signal_type=SignalType.AVOID,
            strength=SignalStrength(value=strength_value),
            reasons=avoid_reasons,
        )

    confirmations, buy_reasons = _accumulate_buy_scores(data)
    strength_value = calculate_signal_strength(confirmations)
    # Adjusted threshold: 10+ confirmations for BUY (accounts for expanded range)
    signal_type = SignalType.BUY if confirmations >= 10 else SignalType.HOLD

    return SignalClassification(
        signal_type=signal_type,
        strength=SignalStrength(value=strength_value),
        reasons=buy_reasons,
    )
