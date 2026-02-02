"""Pure calculation functions for drawdown analysis.

This module contains calculation functions that have no database dependencies.
These are pure functions that can be tested and used independently.
"""

from __future__ import annotations

from .drawdown_models import PositionDrawdown


def calculate_drawdown(peak: float, current: float) -> float:
    """Calculate drawdown percentage from peak.

    Args:
        peak: Peak equity value
        current: Current equity value

    Returns:
        Drawdown as positive percentage (10.0 means -10% from peak)
    """
    if peak <= 0:
        return 0.0
    return ((peak - current) / peak) * 100.0


def calculate_position_drawdown(
    entry_price: float,
    current_price: float,
    peak_price: float,
) -> PositionDrawdown:
    """Calculate drawdown metrics for a single position.

    Args:
        entry_price: Entry price of position
        current_price: Current market price
        peak_price: Highest price since entry

    Returns:
        PositionDrawdown with excursion metrics
    """
    if entry_price <= 0:
        return PositionDrawdown(
            symbol="",
            entry_price=0.0,
            current_price=0.0,
            peak_price=0.0,
            max_adverse_excursion=0.0,
            max_favorable_excursion=0.0,
            current_pnl_pct=0.0,
        )

    current_pnl_pct = ((current_price - entry_price) / entry_price) * 100.0
    max_favorable = ((peak_price - entry_price) / entry_price) * 100.0
    max_adverse = min(0.0, current_pnl_pct)  # Worst loss from entry

    return PositionDrawdown(
        symbol="",  # Caller should set
        entry_price=entry_price,
        current_price=current_price,
        peak_price=peak_price,
        max_adverse_excursion=abs(max_adverse),
        max_favorable_excursion=max(0.0, max_favorable),
        current_pnl_pct=current_pnl_pct,
    )


def get_recovery_estimate(
    current_drawdown_pct: float,
    historical_avg_daily_return: float = 0.05,  # Assume 0.05% avg daily
) -> int | None:
    """Estimate days to recover from current drawdown.

    Args:
        current_drawdown_pct: Current drawdown percentage
        historical_avg_daily_return: Average daily return percentage

    Returns:
        Estimated days to recovery, or None if not calculable
    """
    if current_drawdown_pct <= 0 or historical_avg_daily_return <= 0:
        return 0

    # Need to gain back (drawdown / (1 - drawdown)) to break even
    # E.g., -10% needs +11.11% to recover
    recovery_needed = (current_drawdown_pct / (100 - current_drawdown_pct)) * 100

    days_estimate = int(recovery_needed / historical_avg_daily_return)
    return days_estimate
