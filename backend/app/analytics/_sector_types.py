"""Dataclasses and constants for sector strength analysis (GAP-013)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ..constants import BENCHMARK_SPY

# Benchmark for relative strength
BENCHMARK = BENCHMARK_SPY

# Lookback periods for relative strength
RS_HORIZONS = [20, 60, 252]  # 20-day, 60-day, 252-day

# Number of top sectors to consider "strong"
TOP_SECTORS = 3


@dataclass
class SectorStrength:
    """Relative strength metrics for a sector."""

    etf: str
    sector_name: str
    rs_20d: float | None  # Relative strength 20-day (sector return - SPY return)
    rs_60d: float | None  # Relative strength 60-day
    rs_252d: float | None  # Relative strength 252-day
    rank: int  # Rank 1 = strongest, 11 = weakest
    is_leader: bool  # True if in top 3


@dataclass
class SectorRotationSignals:
    """Sector rotation signals for trading."""

    as_of_date: date
    sectors: list[SectorStrength]
    leaders: list[str]  # ETF symbols of top 3 sectors
    laggards: list[str]  # ETF symbols of bottom 3 sectors
