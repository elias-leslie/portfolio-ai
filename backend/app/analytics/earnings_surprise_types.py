"""Shared types and constants for earnings surprise (internal helper)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# Score thresholds
LARGE_BEAT_PCT = 10.0  # >10% beat = very bullish
SMALL_BEAT_PCT = 2.0  # >2% beat = bullish
SMALL_MISS_PCT = -2.0  # <-2% miss = bearish
LARGE_MISS_PCT = -10.0  # <-10% miss = very bearish


@dataclass
class EarningsSurprise:
    """Single earnings surprise record."""

    symbol: str
    earnings_date: date
    fiscal_quarter: str | None
    eps_estimate: Decimal | None
    eps_actual: Decimal | None
    surprise_pct: Decimal | None
    surprise_direction: str  # 'beat', 'miss', 'inline'
    revenue_estimate: Decimal | None = None
    revenue_actual: Decimal | None = None
