"""Recommendation generation for symbol intelligence.

Generates personalized recommendations based on position status and market context.
"""

from __future__ import annotations

from typing import Any

# Fear & Greed thresholds for recommendations
FEAR_GREED_FEAR_THRESHOLD = 30
FEAR_GREED_GREED_THRESHOLD = 70
FEAR_GREED_DEFAULT = 50
GAIN_PCT_TRIM_THRESHOLD = 20.0


def generate_held_recommendation(
    position: dict[str, Any],
    signal: str | None,
    strength: int,
    fear_greed: int,
) -> tuple[str, list[str]]:
    """Generate recommendation for when user holds a position.

    Returns (action, reasoning) tuple.
    """
    reasoning: list[str] = []
    action = "HOLD_POSITION"

    # Calculate position gain
    gain_pct = 0.0
    if position.get("current_price") and position.get("cost_basis"):
        gain_pct = (
            (position["current_price"] - position["cost_basis"]) / position["cost_basis"]
        ) * 100

    # Determine action based on signal and position state
    if signal == "BUY" and strength >= 7:
        action = "BUY_MORE"
        reasoning.append(f"Strong BUY signal ({strength}/10)")
    elif signal == "AVOID":
        action = "CONSIDER_SELLING"
        reasoning.append("Signal turned to AVOID")
    elif gain_pct > GAIN_PCT_TRIM_THRESHOLD:
        action = "CONSIDER_TRIMMING"
        reasoning.append(f"Position up {gain_pct:.1f}% - consider taking profits")
    else:
        action = "HOLD_POSITION"
        reasoning.append(f"Current gain: {gain_pct:.1f}%")

    if strength < 6:
        reasoning.append(f"Signal strength only {strength}/10 - wait for stronger confirmation")

    # Add market context
    if fear_greed < FEAR_GREED_FEAR_THRESHOLD:
        reasoning.append(f"Market in Fear ({fear_greed}) - consider smaller positions")
    elif fear_greed > FEAR_GREED_GREED_THRESHOLD:
        reasoning.append(f"Market in Greed ({fear_greed}) - be cautious")

    return action, reasoning


def generate_new_position_recommendation(
    signal: str | None,
    strength: int,
    fear_greed: int,
) -> tuple[str, list[str]]:
    """Generate recommendation for potential new position.

    Returns (action, reasoning) tuple.
    """
    reasoning: list[str] = []

    if signal == "BUY":
        if strength >= 7:
            action = "INITIATE_POSITION"
            reasoning.append(f"Strong BUY signal ({strength}/10)")
        else:
            action = "SMALL_POSITION"
            reasoning.append(f"BUY signal but moderate strength ({strength}/10)")
    elif signal == "HOLD":
        action = "WATCH"
        reasoning.append("HOLD signal - wait for better entry")
    else:
        action = "AVOID"
        reasoning.append("AVOID signal - do not initiate")

    # Add market context
    if fear_greed < FEAR_GREED_FEAR_THRESHOLD:
        reasoning.append(f"Market in Fear ({fear_greed}) - consider smaller positions")
    elif fear_greed > FEAR_GREED_GREED_THRESHOLD:
        reasoning.append(f"Market in Greed ({fear_greed}) - be cautious")

    return action, reasoning


def generate_recommendation(
    watchlist: dict[str, Any] | None,
    portfolio: dict[str, Any] | None,
    market: dict[str, Any] | None,
) -> dict[str, Any]:
    """Generate personalized recommendation based on all data."""
    portfolio = portfolio or {}
    market = market or {}

    position = portfolio.get("position")
    held = position is not None
    signal = watchlist.get("signal_type") if watchlist else None
    strength = (watchlist.get("signal_strength") if watchlist else None) or 0
    fear_greed_data = market.get("fear_greed") or {}
    fear_greed = (
        fear_greed_data.get("score", FEAR_GREED_DEFAULT) if fear_greed_data else FEAR_GREED_DEFAULT
    )

    # Route to appropriate helper based on position status
    if held:
        assert position is not None  # Type narrowing
        action, reasoning = generate_held_recommendation(position, signal, strength, fear_greed)
    else:
        action, reasoning = generate_new_position_recommendation(signal, strength, fear_greed)

    return {
        "action": action,
        "reasoning": reasoning,
        "if_not_held": {
            "action": "SMALL_POSITION" if signal == "BUY" else "AVOID",
            "size_pct": 2.0 if strength >= 7 else 1.0,
            "reasoning": f"Signal: {signal}, Strength: {strength}/10",
        }
        if held
        else None,
    }
