"""Market data transformation and formatting helpers."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast

from app.api.market_data_sources import calculate_daily_change_pct
from app.api.market_responses import SectorDataPoint, SectorHistory
from app.constants import SECTOR_ETFS
from app.storage import PortfolioStorage


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


def enrich_indicator_with_history(
    indicator_data: Any,
    symbol: str,
    enrich_func: Any,
    storage: PortfolioStorage,
    health_score_data: Any,
    actual_data_dates: dict[str, Any],
) -> dict[str, Any]:
    """Enrich indicator data with historical change and actual timestamp.

    Args:
        indicator_data: Raw indicator data from price fetcher
        symbol: Market symbol (e.g., "^VIX", "^GSPC")
        enrich_func: Intelligence function to enrich the indicator
        storage: Storage instance for fetching historical data
        health_score_data: Market health score data
        actual_data_dates: Mapping of symbols to actual data timestamps

    Returns:
        Enriched indicator dict with history
    """
    # Calculate daily change percentage from day_bars historical data
    change_pct = calculate_daily_change_pct(storage, symbol, indicator_data.price)

    # Get actual data timestamp (from day_bars) instead of cache timestamp
    actual_timestamp = actual_data_dates.get(symbol)
    if actual_timestamp:
        # Temporarily override cached_at with actual data date
        indicator_data.cached_at = actual_timestamp

    # Call the appropriate enrich function
    return cast(
        dict[str, Any], enrich_func(indicator_data, health_score_data, change_pct=change_pct)
    )
