"""Market data transformation and formatting helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast

from app.api.market_data_sources import calculate_daily_change_pct
from app.api.market_responses import SectorDataPoint, SectorHistory
from app.constants import SECTOR_ETFS
from app.storage import PortfolioStorage


def _parse_row(row: tuple[Any, ...]) -> tuple[str, float] | None:
    """Parse a (date, close) row into (date_str, close) or None if invalid."""
    if not row[0] or row[1] is None:
        return None
    date_val = row[0]
    if not isinstance(date_val, (datetime, date)):
        return None
    return date_val.isoformat(), float(row[1])


def _calc_pct_change(close: float, base_price: float | None) -> float:
    """Calculate percentage change from base price."""
    if base_price is None or base_price == 0:
        return 0.0
    return (close - base_price) / base_price * 100


def build_indicator_data_points(
    rows: list[tuple[Any, ...]],
    period_start: str,
    period_end: str,
) -> tuple[list[dict[str, Any]], str, str]:
    """Build indicator data points from database rows.

    Args:
        rows: Database rows with (date, close) tuples
        period_start: Current period start string (will be updated if empty)
        period_end: Current period end string (will be updated)

    Returns:
        Tuple of (data_points, period_start, period_end)
    """
    data_points: list[dict[str, Any]] = []
    base_price: float | None = None
    current_start = period_start
    current_end = period_end

    for row in rows:
        parsed = _parse_row(row)
        if parsed is None:
            continue
        date_str, close = parsed
        if base_price is None:
            base_price = close
            if not current_start:
                current_start = date_str
        pct_change = round(_calc_pct_change(close, base_price), 2)
        data_points.append({"date": date_str, "close": close, "pct_change": pct_change})
        current_end = date_str

    return data_points, current_start, current_end


def build_sector_history(
    symbol: str,
    name: str,
    rows: list[tuple[Any, ...]],
    period_start: str,
    period_end: str,
) -> tuple[SectorHistory, str, str]:
    """Build sector history from database rows.

    Args:
        symbol: Sector symbol
        name: Sector name
        rows: Database rows with (date, close) tuples
        period_start: Current period start string (will be updated if empty)
        period_end: Current period end string (will be updated)

    Returns:
        Tuple of (SectorHistory, period_start, period_end)
    """
    data_points: list[SectorDataPoint] = []
    base_price: float | None = None
    current_pct = 0.0
    current_start = period_start
    current_end = period_end

    for row in rows:
        parsed = _parse_row(row)
        if parsed is None:
            continue
        date_str, close = parsed
        if base_price is None:
            base_price = close
            if not current_start:
                current_start = date_str
        pct_change = round(_calc_pct_change(close, base_price), 2)
        data_points.append(SectorDataPoint(date=date_str, close=close, pct_change=pct_change))
        current_pct = pct_change
        current_end = date_str

    return (
        SectorHistory(name=name, symbol=symbol, data=data_points, current_pct=current_pct),
        current_start,
        current_end,
    )


def sort_sectors_by_performance(sectors: list[SectorHistory]) -> list[SectorHistory]:
    """Sort sectors by current performance (descending).

    Args:
        sectors: List of sector history data

    Returns:
        Sorted list of sectors
    """
    return sorted(sectors, key=lambda s: s.current_pct, reverse=True)


def get_sector_symbols() -> list[str]:
    """Get list of sector ETF symbols.

    Returns:
        List of sector ETF symbols
    """
    return list(SECTOR_ETFS.keys())


def enrich_indicator_with_history(
    indicator_data: Any,
    symbol: str,
    enrich_func: Any,
    storage: PortfolioStorage,
    health_score_data: Any,
) -> dict[str, Any]:
    """Enrich indicator data with daily change from the right close baseline.

    Args:
        indicator_data: Raw indicator data from price fetcher
        symbol: Market symbol (e.g., "^VIX", "^GSPC")
        enrich_func: Intelligence function to enrich the indicator
        storage: Storage instance for fetching historical data
        health_score_data: Market health score data

    Returns:
        Enriched indicator dict with history
    """
    change_pct = calculate_daily_change_pct(
        storage,
        symbol,
        indicator_data.price,
        getattr(indicator_data, "cached_at", None),
    )

    return cast(
        dict[str, Any], enrich_func(indicator_data, health_score_data, change_pct=change_pct)
    )
