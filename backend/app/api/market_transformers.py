"""Market data transformation and formatting helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.api.market_data_sources import SECTOR_ETFS
from app.api.market_responses import SectorDataPoint, SectorHistory


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
        if row[0] and row[1] is not None:
            # row[0] is date from SQL - handle as datetime/date object
            date_val = row[0]
            if not isinstance(date_val, (datetime, date)):
                continue  # Skip if not a valid date type

            date_str = date_val.isoformat()
            close = float(row[1])
            if base_price is None:
                base_price = close
                if not current_start:
                    current_start = date_str
            pct_change = ((close - base_price) / base_price * 100) if base_price else 0
            data_points.append(
                {
                    "date": date_str,
                    "close": close,
                    "pct_change": round(pct_change, 2),
                }
            )
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
        if row[0] and row[1] is not None:
            # row[0] is date from SQL - handle as datetime/date object
            date_val = row[0]
            if not isinstance(date_val, (datetime, date)):
                continue  # Skip if not a valid date type

            date_str = date_val.isoformat()
            close = float(row[1])
            if base_price is None:
                base_price = close
                if not current_start:
                    current_start = date_str
            pct_change = ((close - base_price) / base_price * 100) if base_price else 0
            data_points.append(
                SectorDataPoint(
                    date=date_str,
                    close=close,
                    pct_change=round(pct_change, 2),
                )
            )
            current_pct = round(pct_change, 2)
            current_end = date_str

    return (
        SectorHistory(
            name=name,
            symbol=symbol,
            data=data_points,
            current_pct=current_pct,
        ),
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
