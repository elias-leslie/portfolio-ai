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

from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from ..constants import BENCHMARK_SPY, SECTOR_ETFS
from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)

# Import from centralized constants (DRY principle)
# SECTOR_ETFS and BENCHMARK_SPY now imported from app.constants

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


# Ticker -> Sector mapping for individual stocks
TICKER_SECTOR_MAP: dict[str, str] = {
    # Technology
    "AAPL": "XLK",
    "MSFT": "XLK",
    "GOOGL": "XLK",
    "GOOG": "XLK",
    "META": "XLC",  # Communication Services
    "NVDA": "XLK",
    "AMD": "XLK",
    "INTC": "XLK",
    "CRM": "XLK",
    "ORCL": "XLK",
    "ADBE": "XLK",
    "CSCO": "XLK",
    "AVGO": "XLK",
    "QCOM": "XLK",
    "TXN": "XLK",
    # Financials
    "JPM": "XLF",
    "BAC": "XLF",
    "WFC": "XLF",
    "GS": "XLF",
    "MS": "XLF",
    "C": "XLF",
    "BLK": "XLF",
    "SCHW": "XLF",
    "AXP": "XLF",
    "V": "XLK",  # Actually tech/payments
    "MA": "XLK",
    # Energy
    "XOM": "XLE",
    "CVX": "XLE",
    "COP": "XLE",
    "SLB": "XLE",
    "EOG": "XLE",
    "PXD": "XLE",
    "MPC": "XLE",
    "VLO": "XLE",
    "OXY": "XLE",
    # Healthcare
    "UNH": "XLV",
    "JNJ": "XLV",
    "PFE": "XLV",
    "ABBV": "XLV",
    "MRK": "XLV",
    "LLY": "XLV",
    "TMO": "XLV",
    "ABT": "XLV",
    "DHR": "XLV",
    "BMY": "XLV",
    "AMGN": "XLV",
    # Consumer Discretionary
    "AMZN": "XLY",
    "TSLA": "XLY",
    "HD": "XLY",
    "MCD": "XLY",
    "NKE": "XLY",
    "SBUX": "XLY",
    "LOW": "XLY",
    "TJX": "XLY",
    # Consumer Staples
    "PG": "XLP",
    "KO": "XLP",
    "PEP": "XLP",
    "COST": "XLP",
    "WMT": "XLP",
    "PM": "XLP",
    "MO": "XLP",
    "CL": "XLP",
    # Industrials
    "HON": "XLI",
    "UNP": "XLI",
    "UPS": "XLI",
    "RTX": "XLI",
    "CAT": "XLI",
    "BA": "XLI",
    "DE": "XLI",
    "GE": "XLI",
    "LMT": "XLI",
    "MMM": "XLI",
    # Utilities
    "NEE": "XLU",
    "DUK": "XLU",
    "SO": "XLU",
    "D": "XLU",
    "AEP": "XLU",
    "EXC": "XLU",
    # Real Estate
    "PLD": "XLRE",
    "AMT": "XLRE",
    "CCI": "XLRE",
    "EQIX": "XLRE",
    "PSA": "XLRE",
    "SPG": "XLRE",
    # Communication Services
    "NFLX": "XLC",
    "DIS": "XLC",
    "CMCSA": "XLC",
    "VZ": "XLC",
    "T": "XLC",
    "TMUS": "XLC",
    # Materials
    "LIN": "XLB",
    "APD": "XLB",
    "SHW": "XLB",
    "ECL": "XLB",
    "FCX": "XLB",
    "NEM": "XLB",
}


def calculate_sector_relative_strength(
    storage: PortfolioStorage,
    target_date: date | None = None,
) -> SectorRotationSignals | None:
    """Calculate relative strength for all sector ETFs vs SPY.

    Args:
        storage: Database storage
        target_date: Date to calculate for (default: most recent)

    Returns:
        SectorRotationSignals or None if insufficient data
    """
    if target_date is None:
        target_date = date.today()

    # Get longest horizon + buffer
    max(RS_HORIZONS) + 10

    # Fetch all sector ETFs and SPY
    symbols = [*list(SECTOR_ETFS.keys()), BENCHMARK]
    placeholders = ", ".join(f"${i + 1}" for i in range(len(symbols)))

    query = f"""
        SELECT symbol, date, close
        FROM day_bars
        WHERE symbol IN ({placeholders})
          AND date <= ${len(symbols) + 1}
        ORDER BY date DESC
    """
    result = storage.query(query, [*symbols, str(target_date)])

    if result.is_empty():
        logger.warning("sector_strength_no_data")
        return None

    # Build price dict: symbol -> date -> close
    prices: dict[str, dict[date, float]] = {t: {} for t in symbols}

    for row in result.iter_rows(named=True):
        symbol = row["symbol"]
        row_date = row["date"]
        if isinstance(row_date, str):
            from datetime import datetime

            row_date = datetime.strptime(row_date, "%Y-%m-%d").date()
        prices[symbol][row_date] = float(row["close"])

    # Get SPY returns for each horizon
    spy_returns = _calculate_returns(prices[BENCHMARK], RS_HORIZONS)

    if all(v is None for v in spy_returns.values()):
        logger.warning("sector_strength_no_spy_data")
        return None

    # Calculate relative strength for each sector
    sectors: list[SectorStrength] = []

    for etf, sector_name in SECTOR_ETFS.items():
        sector_returns = _calculate_returns(prices.get(etf, {}), RS_HORIZONS)

        # Relative strength = sector return - SPY return
        rs_20d = _safe_subtract(sector_returns.get(20), spy_returns.get(20))
        rs_60d = _safe_subtract(sector_returns.get(60), spy_returns.get(60))
        rs_252d = _safe_subtract(sector_returns.get(252), spy_returns.get(252))

        sectors.append(
            SectorStrength(
                etf=etf,
                sector_name=sector_name,
                rs_20d=rs_20d,
                rs_60d=rs_60d,
                rs_252d=rs_252d,
                rank=0,  # Will be set after sorting
                is_leader=False,  # Will be set after ranking
            )
        )

    # Rank by 60-day relative strength (primary ranking horizon)
    # None values go to bottom
    sectors.sort(
        key=lambda s: s.rs_60d if s.rs_60d is not None else float("-inf"),
        reverse=True,
    )

    # Assign ranks and leader status
    leaders = []
    laggards = []

    for i, sector in enumerate(sectors):
        sector.rank = i + 1
        sector.is_leader = i < TOP_SECTORS
        if sector.is_leader:
            leaders.append(sector.etf)
        if i >= len(sectors) - TOP_SECTORS:
            laggards.append(sector.etf)

    # Get latest date from SPY data
    spy_dates = sorted(prices[BENCHMARK].keys(), reverse=True)
    latest_date = spy_dates[0] if spy_dates else target_date

    return SectorRotationSignals(
        as_of_date=latest_date,
        sectors=sectors,
        leaders=leaders,
        laggards=laggards,
    )


def _calculate_returns(
    prices: dict[date, float],
    horizons: list[int],
) -> dict[int, float | None]:
    """Calculate returns for multiple horizons.

    Args:
        prices: Date -> close price mapping
        horizons: List of lookback periods (trading days)

    Returns:
        Dict of horizon -> return percentage
    """
    if not prices:
        return dict.fromkeys(horizons)

    sorted_dates = sorted(prices.keys(), reverse=True)
    if not sorted_dates:
        return dict.fromkeys(horizons)

    latest_close = prices[sorted_dates[0]]
    returns: dict[int, float | None] = {}

    for horizon in horizons:
        if len(sorted_dates) > horizon:
            prior_date = sorted_dates[horizon]
            prior_close = prices.get(prior_date)
            if prior_close and prior_close > 0:
                pct_return = ((latest_close - prior_close) / prior_close) * 100
                returns[horizon] = pct_return
            else:
                returns[horizon] = None
        else:
            returns[horizon] = None

    return returns


def _safe_subtract(a: float | None, b: float | None) -> float | None:
    """Subtract two values, returning None if either is None."""
    if a is None or b is None:
        return None
    return a - b


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

    # Find sector rank
    sector = next((s for s in signals.sectors if s.etf == sector_etf), None)
    if sector is None:
        return 0, []

    score = 0
    reasons: list[str] = []

    if sector.rank == 1:
        score = 2
        reasons.append(f"Sector leader: {sector.sector_name} (#{sector.rank})")
    elif sector.is_leader:
        score = 1
        reasons.append(f"Strong sector: {sector.sector_name} (#{sector.rank})")
    elif sector.rank >= len(signals.sectors) - 2:
        score = -1
        reasons.append(f"Weak sector: {sector.sector_name} (#{sector.rank})")
    # else: middle sector, no bonus or penalty

    # Add RS context
    if sector.rs_60d is not None:
        if sector.rs_60d > 5.0:
            reasons.append(f"Sector outperforming SPY by {sector.rs_60d:.1f}%")
        elif sector.rs_60d < -5.0:
            reasons.append(f"Sector underperforming SPY by {abs(sector.rs_60d):.1f}%")

    return score, reasons


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
        return {
            "sector_rank": None,
            "sector_is_leader": None,
            "sector_etf": None,
        }

    signals = calculate_sector_relative_strength(storage)
    if signals is None:
        return {
            "sector_rank": None,
            "sector_is_leader": None,
            "sector_etf": sector_etf,
        }

    sector = next((s for s in signals.sectors if s.etf == sector_etf), None)
    if sector is None:
        return {
            "sector_rank": None,
            "sector_is_leader": None,
            "sector_etf": sector_etf,
        }

    return {
        "sector_rank": sector.rank,
        "sector_is_leader": sector.is_leader,
        "sector_etf": sector_etf,
    }
