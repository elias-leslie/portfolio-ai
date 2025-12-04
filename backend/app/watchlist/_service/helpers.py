"""Helper utilities for watchlist service.

This module provides:
- Price change calculations
- JSON field parsing
- Timestamp formatting
"""

from __future__ import annotations

import json
from typing import Any, cast

from ...storage import PortfolioStorage


def _calculate_price_change(
    storage: PortfolioStorage, symbol: str, price: float | None, item_id: str | None = None
) -> tuple[float | None, bool]:
    """Calculate price change percentage for a symbol.

    Returns:
        Tuple of (change_pct, has_historical_data)
    """
    if price is None or price <= 0:
        return (None, False)

    # Try day_bars historical data first
    df = storage.query(
        """
        SELECT close
        FROM day_bars
        WHERE symbol = ?
        ORDER BY date DESC
        LIMIT 2
        """,
        [symbol],
    )
    if df.height >= 2:
        prev_close = df["close"][1]
        if prev_close not in (0, None):
            return (float((price - prev_close) / prev_close * 100.0), True)

    # Fallback: Use previous watchlist snapshot
    if item_id:
        snapshot_df = storage.query(
            """
            SELECT price
            FROM watchlist_snapshots_v
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            LIMIT 1
            """,
            [item_id],
        )
        if snapshot_df.height > 0:
            prev_price = snapshot_df["price"][0]
            if prev_price and prev_price > 0:
                return (float((price - prev_price) / prev_price * 100.0), False)

    return (None, False)


def parse_json_field(value: str | dict[str, Any] | None) -> dict[str, Any] | None:
    """Parse JSON field if it's a string, otherwise return as-is.

    Args:
        value: Field value (might be string, dict, or None)

    Returns:
        Parsed dictionary or None if parsing fails
    """
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
        except (json.JSONDecodeError, TypeError):
            return None
    return value if isinstance(value, dict) else None


def format_timestamp(ts: object) -> str | object:
    """Format timestamp to ISO string if it has isoformat method."""
    if hasattr(ts, "isoformat"):
        return str(cast(Any, ts).isoformat())
    return ts


__all__ = [
    "_calculate_price_change",
    "format_timestamp",
    "parse_json_field",
]
