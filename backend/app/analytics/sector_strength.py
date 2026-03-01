"""Sector relative strength calculations (GAP-013).

Implements sector rotation analysis based on relative strength vs SPY:
- Calculates sector ETF performance relative to S&P 500
- Ranks sectors by relative strength
- Identifies sector leaders and laggards
- Provides sector filtering for trade entry

Research basis: Sector rotation drives 30-40% of returns (Faber 2007).
Relative strength > absolute strength for sector allocation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ._sector_calculations import (
    _calculate_returns,
    _safe_subtract,
    calculate_sector_relative_strength,
)
from ._sector_ticker_map import TICKER_SECTOR_MAP
from ._sector_types import (
    BENCHMARK,
    RS_HORIZONS,
    TOP_SECTORS,
    SectorRotationSignals,
    SectorStrength,
)

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

__all__ = [
    "BENCHMARK",
    "RS_HORIZONS",
    "TICKER_SECTOR_MAP",
    "TOP_SECTORS",
    "SectorRotationSignals",
    "SectorStrength",
    "_calculate_returns",
    "_safe_subtract",
    "calculate_sector_relative_strength",
    "calculate_sector_strength_score",
    "get_sector_strength_inputs",
    "get_symbol_sector_etf",
    "is_symbol_in_leading_sector",
]


def get_symbol_sector_etf(symbol: str) -> str | None:
    """Get sector ETF for a stock symbol.

    Args:
        symbol: Stock symbol

    Returns:
        Sector ETF symbol or None if unknown
    """
    return TICKER_SECTOR_MAP.get(symbol.upper())


def is_symbol_in_leading_sector(
    storage: PortfolioStorage,
    symbol: str,
) -> tuple[bool, str | None]:
    """Check if symbol's sector is among the leaders.

    Args:
        storage: Database storage
        symbol: Stock symbol

    Returns:
        (is_leader, sector_etf) tuple
    """
    sector_etf = get_symbol_sector_etf(symbol)
    if sector_etf is None:
        return False, None

    signals = calculate_sector_relative_strength(storage)
    if signals is None:
        return False, sector_etf

    return sector_etf in signals.leaders, sector_etf


def calculate_sector_strength_score(
    storage: PortfolioStorage,
    symbol: str,
) -> tuple[int, list[str]]:
    """Calculate 0-4 point sector strength score for signal classification.

    Scoring:
    - +2 if symbol's sector is #1 rank
    - +1 if symbol's sector is top 3 (leader)
    - +0 if middle sector (rank 4-8)
    - -1 if bottom 3 sector (laggard)

    Args:
        storage: Database storage
        symbol: Stock symbol

    Returns:
        (score, reasons) where score is -1 to +2
    """
    sector_etf = get_symbol_sector_etf(symbol)
    if sector_etf is None:
        return 0, []

    signals = calculate_sector_relative_strength(storage)
    if signals is None:
        return 0, []

    sector = next((s for s in signals.sectors if s.etf == sector_etf), None)
    if sector is None:
        return 0, []

    score, reasons = _score_by_rank(sector, signals)
    _append_rs_context(sector, reasons)
    return score, reasons


def _score_by_rank(
    sector: SectorStrength,
    signals: SectorRotationSignals,
) -> tuple[int, list[str]]:
    """Compute score and primary reason based on sector rank."""
    reasons: list[str] = []
    if sector.rank == 1:
        return 2, [f"Sector leader: {sector.sector_name} (#{sector.rank})"]
    if sector.is_leader:
        return 1, [f"Strong sector: {sector.sector_name} (#{sector.rank})"]
    if sector.rank >= len(signals.sectors) - 2:
        return -1, [f"Weak sector: {sector.sector_name} (#{sector.rank})"]
    return 0, reasons


def _append_rs_context(sector: SectorStrength, reasons: list[str]) -> None:
    """Append relative-strength context sentence to reasons list."""
    if sector.rs_60d is None:
        return
    if sector.rs_60d > 5.0:
        reasons.append(f"Sector outperforming SPY by {sector.rs_60d:.1f}%")
    elif sector.rs_60d < -5.0:
        reasons.append(f"Sector underperforming SPY by {abs(sector.rs_60d):.1f}%")


def get_sector_strength_inputs(
    storage: PortfolioStorage,
    symbol: str,
) -> dict[str, int | bool | str | None]:
    """Get sector strength inputs for signal classification.

    Args:
        storage: Database storage
        symbol: Stock symbol

    Returns:
        Dict with sector_rank, sector_is_leader, sector_etf
    """
    sector_etf = get_symbol_sector_etf(symbol)
    if sector_etf is None:
        return {"sector_rank": None, "sector_is_leader": None, "sector_etf": None}

    signals = calculate_sector_relative_strength(storage)
    if signals is None:
        return {"sector_rank": None, "sector_is_leader": None, "sector_etf": sector_etf}

    sector = next((s for s in signals.sectors if s.etf == sector_etf), None)
    if sector is None:
        return {"sector_rank": None, "sector_is_leader": None, "sector_etf": sector_etf}

    return {
        "sector_rank": sector.rank,
        "sector_is_leader": sector.is_leader,
        "sector_etf": sector_etf,
    }
