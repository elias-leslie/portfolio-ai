"""Low-level sector strength calculation helpers (GAP-013).

Pure computation functions with no storage dependencies.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import TYPE_CHECKING

from ..constants import SECTOR_ETFS
from ..logging_config import get_logger
from ._sector_types import (
    BENCHMARK,
    RS_HORIZONS,
    TOP_SECTORS,
    SectorRotationSignals,
    SectorStrength,
)

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)


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

    prices = _build_price_dict(symbols, result)
    spy_returns = _calculate_returns(prices[BENCHMARK], RS_HORIZONS)

    if all(v is None for v in spy_returns.values()):
        logger.warning("sector_strength_no_spy_data")
        return None

    sectors = _build_sector_strengths(prices, spy_returns)
    leaders, laggards = _rank_sectors(sectors)

    spy_dates = sorted(prices[BENCHMARK].keys(), reverse=True)
    latest_date = spy_dates[0] if spy_dates else target_date

    return SectorRotationSignals(
        as_of_date=latest_date,
        sectors=sectors,
        leaders=leaders,
        laggards=laggards,
    )


def _build_price_dict(
    symbols: list[str],
    result: object,
) -> dict[str, dict[date, float]]:
    """Build price dict from query result rows."""
    prices: dict[str, dict[date, float]] = {t: {} for t in symbols}
    for row in result.iter_rows(named=True):
        symbol = row["symbol"]
        row_date = row["date"]
        if isinstance(row_date, str):
            row_date = datetime.strptime(row_date, "%Y-%m-%d").date()
        prices[symbol][row_date] = float(row["close"])
    return prices


def _build_sector_strengths(
    prices: dict[str, dict[date, float]],
    spy_returns: dict[int, float | None],
) -> list[SectorStrength]:
    """Build list of SectorStrength objects from prices and SPY returns."""
    sectors: list[SectorStrength] = []
    for etf, sector_name in SECTOR_ETFS.items():
        sector_returns = _calculate_returns(prices.get(etf, {}), RS_HORIZONS)
        sectors.append(
            SectorStrength(
                etf=etf,
                sector_name=sector_name,
                rs_20d=_safe_subtract(sector_returns.get(20), spy_returns.get(20)),
                rs_60d=_safe_subtract(sector_returns.get(60), spy_returns.get(60)),
                rs_252d=_safe_subtract(sector_returns.get(252), spy_returns.get(252)),
                rank=0,
                is_leader=False,
            )
        )
    return sectors


def _rank_sectors(
    sectors: list[SectorStrength],
) -> tuple[list[str], list[str]]:
    """Sort sectors by 60-day RS and assign ranks; return leaders and laggards."""
    sectors.sort(
        key=lambda s: s.rs_60d if s.rs_60d is not None else -math.inf,
        reverse=True,
    )
    leaders: list[str] = []
    laggards: list[str] = []
    for i, sector in enumerate(sectors):
        sector.rank = i + 1
        sector.is_leader = i < TOP_SECTORS
        if sector.is_leader:
            leaders.append(sector.etf)
        if i >= len(sectors) - TOP_SECTORS:
            laggards.append(sector.etf)
    return leaders, laggards


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
    latest_close = prices[sorted_dates[0]]
    returns: dict[int, float | None] = {}

    for horizon in horizons:
        if len(sorted_dates) > horizon:
            prior_close = prices.get(sorted_dates[horizon])
            if prior_close and prior_close > 0:
                returns[horizon] = ((latest_close - prior_close) / prior_close) * 100
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
