"""Business logic for trade recommendations.

Position sizing, risk calculations, and signal status evaluation.
"""

from __future__ import annotations

from typing import Literal

# Default portfolio size for position sizing
DEFAULT_PORTFOLIO_SIZE = 100_000.0

# Default position size as percentage of portfolio
DEFAULT_POSITION_PCT = 0.05  # 5%

def calculate_position_size(
    entry_price: float,
    portfolio_size: float = DEFAULT_PORTFOLIO_SIZE,
    position_pct: float = DEFAULT_POSITION_PCT,
) -> tuple[float, int]:
    """Calculate position size in dollars and shares.

    Args:
        entry_price: Current price per share
        portfolio_size: Total portfolio value
        position_pct: Percentage of portfolio per position

    Returns:
        Tuple of (dollars, shares)
    """
    dollars = portfolio_size * position_pct
    shares = int(dollars / entry_price) if entry_price > 0 else 0
    return dollars, shares
def calculate_risk_reward(entry: float, stop: float, target: float) -> float:
    """Calculate risk/reward ratio."""
    risk = entry - stop
    reward = target - entry
    if risk <= 0:
        return 0.0
    return round(reward / risk, 2)


def calculate_signal_status(  # noqa: PLR0911
    signal_type: str, entry_price: float, current_price: float
) -> tuple[float, Literal["valid", "better_entry", "caution", "invalidated"]]:
    """Calculate signal status based on price movement since signal.

    For BUY signals:
    - Price dropped 0-5%: "better_entry" (more attractive)
    - Price within ±5%: "valid"
    - Price rose >5%: "caution" (may have missed entry)
    - Price dropped >15% or rose >15%: "invalidated" (something changed)

    For SELL signals: Opposite logic.

    Returns:
        Tuple of (price_change_pct, status)
    """
    if entry_price <= 0:
        return 0.0, "valid"

    price_change_pct = ((current_price - entry_price) / entry_price) * 100

    if signal_type == "BUY":
        if price_change_pct < -15 or price_change_pct > 15:
            return price_change_pct, "invalidated"
        if price_change_pct < -5:
            return price_change_pct, "better_entry"  # Significant drop = better buy
        if price_change_pct > 5:
            return price_change_pct, "caution"  # Rose too much, may have missed
        if price_change_pct < 0:
            return price_change_pct, "better_entry"  # Small drop = slightly better
        return price_change_pct, "valid"
    if price_change_pct < -15 or price_change_pct > 15:
        return price_change_pct, "invalidated"
    if price_change_pct > 5:
        return price_change_pct, "better_entry"  # Rose = better sell price
    if price_change_pct < -5:
        return price_change_pct, "caution"  # Dropped, may have missed
    if price_change_pct > 0:
        return price_change_pct, "better_entry"
    return price_change_pct, "valid"
