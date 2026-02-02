"""Data models for portfolio drawdown tracking.

This module contains the data structures used throughout the drawdown
tracking system.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class DrawdownMetrics:
    """Portfolio drawdown metrics."""

    current_drawdown_pct: float  # Current drawdown from peak (positive = down)
    max_drawdown_pct: float  # Maximum drawdown ever recorded
    peak_equity: float  # Highest equity value recorded
    peak_date: date | None  # Date when peak was reached
    current_equity: float  # Current equity value
    underwater_days: int  # Days since last peak
    is_halted: bool  # True if trading should be halted
    halt_reason: str | None  # Reason for halt if halted


@dataclass
class PositionDrawdown:
    """Position-level drawdown tracking."""

    symbol: str
    entry_price: float
    current_price: float
    peak_price: float  # Highest price since entry
    max_adverse_excursion: float  # Worst % loss from entry
    max_favorable_excursion: float  # Best % gain from entry
    current_pnl_pct: float  # Current P&L %
