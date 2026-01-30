"""Confidence tier mapping and position sizing utilities.

Section 1.2: Confidence → Leverage enforcement.
"""

from __future__ import annotations

# Confidence tier → position size multiplier mapping (Section 1.2)
# Higher confidence = larger positions, lower confidence = smaller positions
CONFIDENCE_LEVERAGE_MAP = {
    "very_low": {"min": 0.0, "max": 0.2, "multiplier": 0.25, "max_position_pct": 0.0125},
    "low": {"min": 0.2, "max": 0.4, "multiplier": 0.5, "max_position_pct": 0.025},
    "medium": {"min": 0.4, "max": 0.6, "multiplier": 1.0, "max_position_pct": 0.05},
    "high": {"min": 0.6, "max": 0.8, "multiplier": 1.5, "max_position_pct": 0.075},
    "very_high": {"min": 0.8, "max": 1.0, "multiplier": 2.0, "max_position_pct": 0.10},
}


def get_confidence_tier(confidence: float) -> str:
    """Get confidence tier from confidence score.

    Args:
        confidence: Confidence score (0.0-1.0)

    Returns:
        Tier name: very_low, low, medium, high, very_high
    """
    if confidence >= 0.8:
        return "very_high"
    if confidence >= 0.6:
        return "high"
    if confidence >= 0.4:
        return "medium"
    if confidence >= 0.2:
        return "low"
    return "very_low"


def calculate_confidence_adjusted_position(confidence: float) -> float:
    """Calculate position size adjusted for confidence level.

    Args:
        confidence: Confidence score (0.0-1.0)

    Returns:
        Adjusted max_position_pct
    """
    tier = get_confidence_tier(confidence)
    tier_config = CONFIDENCE_LEVERAGE_MAP[tier]
    return tier_config["max_position_pct"]


__all__ = [
    "CONFIDENCE_LEVERAGE_MAP",
    "calculate_confidence_adjusted_position",
    "get_confidence_tier",
]
