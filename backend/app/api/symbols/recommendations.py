"""Recommendation generation for symbol intelligence.

Generates personalized recommendations based on position status and market context.
"""

from __future__ import annotations

from typing import Any

from app.portfolio.current_facts import calculate_current_position_fact

# Fear & Greed thresholds for recommendations
FEAR_GREED_FEAR_THRESHOLD = 30
FEAR_GREED_GREED_THRESHOLD = 70
FEAR_GREED_DEFAULT = 50
GAIN_PCT_TRIM_THRESHOLD = 20.0
CONCENTRATION_TRIM_THRESHOLD = 15.0


def _effective_concentration_weight(position: dict[str, Any]) -> float | None:
    raw_value = position.get("concentration_weight_pct")
    if raw_value is None:
        raw_value = position.get("weight_pct")
    try:
        return float(raw_value) if raw_value is not None else None
    except (TypeError, ValueError):
        return None


def _lookthrough_reason(position: dict[str, Any], concentration_weight_pct: float | None) -> str | None:
    if str(position.get("concentration_method") or "") != "lookthrough":
        return None
    if concentration_weight_pct is None:
        return None
    top_exposure_name = str(position.get("top_exposure_name") or "").strip() or "top holding"
    vehicle_weight_pct = position.get("weight_pct")
    try:
        vehicle_weight = float(vehicle_weight_pct) if vehicle_weight_pct is not None else None
    except (TypeError, ValueError):
        vehicle_weight = None

    if vehicle_weight is None:
        return (
            f"Largest look-through exposure is {top_exposure_name} at "
            f"{concentration_weight_pct:.1f}% of invested assets."
        )

    return (
        f"Fund weight is {vehicle_weight:.1f}% of invested assets, but largest "
        f"look-through exposure is {top_exposure_name} at {concentration_weight_pct:.1f}%."
    )


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

    current_fact = calculate_current_position_fact(
        symbol=str(position.get("symbol") or ""),
        shares=position.get("shares", 0),
        cost_basis=position.get("cost_basis", 0),
        position_type=position.get("position_type") or "long",
        current_price=position.get("current_price"),
    )
    gain_pct = current_fact.gain_pct
    concentration_weight_pct = _effective_concentration_weight(position)
    lookthrough_reason = _lookthrough_reason(position, concentration_weight_pct)

    # Determine action based on signal and position state
    if signal == "BUY" and strength >= 7:
        action = "BUY_MORE"
        reasoning.append(f"Strong BUY signal ({strength}/10)")
    elif signal == "AVOID":
        action = "CONSIDER_SELLING"
        reasoning.append("Signal turned to AVOID")
    elif (
        gain_pct is not None
        and gain_pct > GAIN_PCT_TRIM_THRESHOLD
        and concentration_weight_pct is not None
        and concentration_weight_pct >= CONCENTRATION_TRIM_THRESHOLD
    ):
        action = "CONSIDER_TRIMMING"
        if lookthrough_reason is not None:
            reasoning.append(lookthrough_reason)
        reasoning.append(f"Position up {gain_pct:.1f}% - consider taking profits")
    else:
        action = "HOLD_POSITION"
        if gain_pct is None:
            reasoning.append("Live gain/loss unavailable because current price is missing")
        else:
            reasoning.append(f"Current gain: {gain_pct:.1f}%")
            if lookthrough_reason is not None:
                reasoning.append(lookthrough_reason)

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
