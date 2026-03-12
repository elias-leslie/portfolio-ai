"""Business logic for trade recommendations.

Signal status evaluation and endpoint defaults.
"""

from __future__ import annotations

from typing import Literal

# Default portfolio size for position sizing
DEFAULT_PORTFOLIO_SIZE = 100_000.0

# Default position size as percentage of portfolio
DEFAULT_POSITION_PCT = 0.05  # 5%

SignalStatus = Literal["valid", "better_entry", "caution", "invalidated"]


def _is_extreme_move(price_change_pct: float) -> bool:
    """Return True when price moved beyond the ±15% invalidation threshold."""
    return price_change_pct < -15 or price_change_pct > 15


def _buy_signal_status(price_change_pct: float) -> SignalStatus:
    """Classify status for a BUY signal given the price-change percentage.

    - Extreme move (>±15 %): invalidated
    - Dropped (< 0 %): better_entry  (cheaper than signal price)
    - Rose > 5 %: caution  (may have missed the entry)
    - Otherwise: valid
    """
    if _is_extreme_move(price_change_pct):
        return "invalidated"
    if price_change_pct < 0:
        return "better_entry"
    if price_change_pct > 5:
        return "caution"
    return "valid"


def _sell_signal_status(price_change_pct: float) -> SignalStatus:
    """Classify status for a SELL signal given the price-change percentage.

    - Extreme move (>±15 %): invalidated
    - Rose (> 0 %): better_entry  (higher sell price)
    - Dropped < -5 %: caution  (may have missed the exit)
    - Otherwise: valid
    """
    if _is_extreme_move(price_change_pct):
        return "invalidated"
    if price_change_pct > 0:
        return "better_entry"
    if price_change_pct < -5:
        return "caution"
    return "valid"


def calculate_signal_status(
    signal_type: str, entry_price: float, current_price: float
) -> tuple[float, SignalStatus]:
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
        return price_change_pct, _buy_signal_status(price_change_pct)
    return price_change_pct, _sell_signal_status(price_change_pct)
