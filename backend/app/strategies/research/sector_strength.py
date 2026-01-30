"""Sector strength aggregation for research insights.

Handles:
- Sector relative strength vs SPY benchmark
- Sector momentum classification (leading, in_line, lagging)
- Sector rotation signals (rotate_in, hold, rotate_out)
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.storage import PortfolioStorage


def calculate_30d_return(storage: PortfolioStorage, symbol: str) -> float:
    """Calculate 30-day return for a symbol.

    Args:
        storage: Portfolio storage instance
        symbol: Stock symbol

    Returns:
        30-day return percentage
    """
    df = storage.get_ohlcv_data(symbol, limit=31)
    if df.is_empty() or len(df) < 2:
        return 0.0

    rows = df.to_dicts()
    current_price = float(rows[0]["close"])
    price_30d_ago = float(rows[-1]["close"])

    return ((current_price - price_30d_ago) / price_30d_ago) * 100.0


def aggregate_sector_strength(
    storage: PortfolioStorage, symbol: str, as_of_date: date
) -> dict[str, Any]:
    """Aggregate sector relative strength vs SPY.

    Args:
        storage: Portfolio storage instance
        symbol: Stock symbol
        as_of_date: Date to analyze

    Returns:
        Dict with sector strength fields
    """
    # Query sector from watchlist metadata (stored as JSON) or fallback to Unknown
    sector = storage.get_symbol_sector(symbol)

    # If no sector mapping, return defaults
    if sector == "Unknown" or not sector:
        return {
            "sector": "Unknown",
            "sector_momentum": "in_line",
            "sector_vs_spy_30d": 0.0,
            "sector_rotation_signal": "hold",
            "confidence": 0.0,
        }

    # Calculate 30-day return for symbol and SPY
    symbol_return = calculate_30d_return(storage, symbol)
    spy_return = calculate_30d_return(storage, "SPY")

    sector_vs_spy_30d = symbol_return - spy_return

    # Classify sector momentum
    if sector_vs_spy_30d > 5.0:
        sector_momentum = "leading"
    elif sector_vs_spy_30d < -5.0:
        sector_momentum = "lagging"
    else:
        sector_momentum = "in_line"

    # Sector rotation signal
    if sector_vs_spy_30d > 10.0:
        sector_rotation_signal = "hold"  # Already strong, hold position
    elif sector_vs_spy_30d > 0.0:
        sector_rotation_signal = "rotate_in"  # Strengthening, add exposure
    else:
        sector_rotation_signal = "rotate_out"  # Weakening, reduce exposure

    return {
        "sector": sector,
        "sector_momentum": sector_momentum,
        "sector_vs_spy_30d": sector_vs_spy_30d,
        "sector_rotation_signal": sector_rotation_signal,
        "confidence": 1.0,  # Always have sector data if symbol found
    }
