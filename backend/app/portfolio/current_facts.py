"""Canonical current portfolio fact calculations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CurrentPositionFact:
    """Current position facts derived from live price data."""

    symbol: str
    shares: float
    cost_basis: float
    position_type: str
    current_price: float | None
    current_value: float | None
    cost_total: float
    gain: float | None
    gain_pct: float | None
    weight_pct: float | None


def _finite_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) else None


def calculate_current_position_fact(
    *,
    symbol: str,
    shares: Any,
    cost_basis: Any,
    position_type: str | None = "long",
    current_price: Any = None,
    invested_total_value: Any = None,
) -> CurrentPositionFact:
    """Calculate current position facts without inventing unavailable live prices."""
    normalized_symbol = symbol.upper()
    share_count = _finite_float(shares) or 0.0
    basis = _finite_float(cost_basis) or 0.0
    normalized_type = (position_type or "long").lower()
    sign = -1.0 if normalized_type == "short" else 1.0
    cost_total = share_count * basis * sign

    live_price = _finite_float(current_price)
    if live_price is None:
        return CurrentPositionFact(
            symbol=normalized_symbol,
            shares=share_count,
            cost_basis=basis,
            position_type=normalized_type,
            current_price=None,
            current_value=None,
            cost_total=cost_total,
            gain=None,
            gain_pct=None,
            weight_pct=None,
        )

    current_value = share_count * live_price * sign
    gain = current_value - cost_total
    gain_denominator = abs(cost_total)
    gain_pct = (gain / gain_denominator * 100) if gain_denominator else None

    invested_value = _finite_float(invested_total_value)
    weight_pct = (
        current_value / invested_value * 100
        if invested_value is not None and invested_value != 0
        else None
    )

    return CurrentPositionFact(
        symbol=normalized_symbol,
        shares=share_count,
        cost_basis=basis,
        position_type=normalized_type,
        current_price=live_price,
        current_value=current_value,
        cost_total=cost_total,
        gain=gain,
        gain_pct=gain_pct,
        weight_pct=weight_pct,
    )
