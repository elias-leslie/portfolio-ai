"""Options flow data service for signal scoring (GAP-031).

Provides latest options market metrics for use in signal classification.
Data comes from options_market_metrics table, populated by options_pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..storage import PortfolioStorage

logger = get_logger(__name__)

# Sector mappings for ticker classification
SECTOR_MAPPING: dict[str, str] = {
    # Technology
    "AAPL": "Technology",
    "MSFT": "Technology",
    "GOOGL": "Technology",
    "GOOG": "Technology",
    "META": "Technology",
    "NVDA": "Technology",
    "AMD": "Technology",
    "INTC": "Technology",
    "CRM": "Technology",
    "ORCL": "Technology",
    "ADBE": "Technology",
    "CSCO": "Technology",
    "AVGO": "Technology",
    "QCOM": "Technology",
    "TXN": "Technology",
    "NOW": "Technology",
    "AMAT": "Technology",
    "MU": "Technology",
    "LRCX": "Technology",
    "KLAC": "Technology",
    # Add more as needed...
}


@dataclass
class OptionsFlowData:
    """Options flow metrics for signal scoring."""

    call_pct: float  # 0.0-1.0 (0.55 = 55% calls)
    near_term_pct: float  # 0.0-1.0
    concentration_pct: float  # 0.0-1.0
    sector_weights: dict[str, float]  # Sector name -> weight %
    as_of_date: date | None
    is_stale: bool  # True if data is >1 day old


def get_latest_options_flow(storage: PortfolioStorage) -> OptionsFlowData | None:
    """Get latest options market metrics.

    Args:
        storage: Database storage

    Returns:
        OptionsFlowData or None if no data available
    """
    query = """
        SELECT as_of_date, most_active_call_pct, near_term_pct,
               concentration_pct, sector_weights
        FROM options_market_metrics
        ORDER BY as_of_date DESC
        LIMIT 1
    """
    result = storage.query(query, [])

    if result.is_empty():
        logger.warning("options_flow_no_data")
        return None

    row = result.row(0, named=True)
    as_of_date = row["as_of_date"]

    # Check staleness (data older than 1 trading day is stale)
    today = date.today()
    is_stale = False
    if as_of_date is not None:
        days_old = (today - as_of_date).days
        # Allow weekends (2-3 days old on Monday is OK)
        is_stale = days_old > 3

    # Parse sector weights from JSON
    sector_weights = row.get("sector_weights", {}) or {}
    if isinstance(sector_weights, str):
        import json

        sector_weights = json.loads(sector_weights)

    return OptionsFlowData(
        call_pct=float(row["most_active_call_pct"]) / 100.0,  # Convert to 0-1
        near_term_pct=float(row["near_term_pct"]) / 100.0,
        concentration_pct=float(row["concentration_pct"]) / 100.0,
        sector_weights=sector_weights,
        as_of_date=as_of_date,
        is_stale=is_stale,
    )


def get_ticker_sector(ticker: str) -> str | None:
    """Get sector for a ticker symbol.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Sector name or None if unknown
    """
    return SECTOR_MAPPING.get(ticker.upper())


def is_ticker_in_active_sector(
    ticker: str,
    options_data: OptionsFlowData | None,
    threshold_pct: float = 15.0,
) -> bool:
    """Check if ticker's sector has high options activity.

    Args:
        ticker: Stock ticker symbol
        options_data: Latest options flow data
        threshold_pct: Minimum sector weight to be considered "active"

    Returns:
        True if ticker's sector has >= threshold_pct of options volume
    """
    if options_data is None:
        return False

    sector = get_ticker_sector(ticker)
    if sector is None:
        return False

    sector_weight = options_data.sector_weights.get(sector, 0.0)
    return sector_weight >= threshold_pct


def get_options_flow_inputs(
    storage: PortfolioStorage,
    ticker: str,
) -> dict[str, float | bool | None]:
    """Get options flow inputs for signal classification.

    Args:
        storage: Database storage
        ticker: Stock ticker symbol

    Returns:
        Dict with options_call_pct, options_near_term_pct, ticker_in_active_sector
    """
    options_data = get_latest_options_flow(storage)

    if options_data is None or options_data.is_stale:
        return {
            "options_call_pct": None,
            "options_near_term_pct": None,
            "ticker_in_active_sector": None,
        }

    return {
        "options_call_pct": options_data.call_pct,
        "options_near_term_pct": options_data.near_term_pct,
        "ticker_in_active_sector": is_ticker_in_active_sector(ticker, options_data),
    }
