"""Response and data builders for watchlist service.

This module provides:
- Snapshot data building
- Base item data construction
"""

from __future__ import annotations

from typing import Any

from ...storage import PortfolioStorage
from .formatters import _normalize_recent_news_payload
from .helpers import format_timestamp, parse_json_field
from .score_helpers import add_staleness_info, check_score_alert


def build_base_item_data(row: dict[str, Any]) -> dict[str, Any]:
    """Build base watchlist item data from query row."""
    return {
        "id": row["id"],
        "symbol": row["symbol"],
        "note": row.get("note"),
        "source": row.get("source", "manual"),
        "created_at": format_timestamp(row["created_at"]),
        "updated_at": format_timestamp(row["updated_at"]),
        "score": None,
        "score_alert": False,
    }


def build_snapshot_data(
    storage: PortfolioStorage,
    item_data: dict[str, Any],
    row: dict[str, Any],
    stale_ttl_minutes: int,
) -> None:
    """Build and add snapshot data to item_data in place.

    Args:
        storage: Portfolio storage instance
        item_data: Item dictionary to update
        row: Database row with snapshot fields
        stale_ttl_minutes: TTL for staleness check
    """
    # Parse JSON fields
    raw_metrics = parse_json_field(row.get("raw_metrics", {})) or {}
    news_payload = parse_json_field(row.get("recent_news_headlines"))

    # Add staleness info
    fetched_at = row.get("fetched_at")
    add_staleness_info(raw_metrics, fetched_at, stale_ttl_minutes)

    # Check for score alert
    alert = check_score_alert(storage, row["id"], row["overall_score"])

    # Build score dict (only if we have valid metric data)
    # Empty dicts cause Pydantic validation errors in ScoreComponentResponse
    price_data = raw_metrics.get("price")
    tech_data = raw_metrics.get("technical")
    fund_data = raw_metrics.get("fundamental")
    catalyst_data = raw_metrics.get("catalyst")
    options_flow_data = raw_metrics.get("options_flow")

    # Only include score if we have at least price or technical data with required fields
    if (price_data and "score" in price_data) or (tech_data and "score" in tech_data):
        item_data["score"] = {
            "price": price_data if (price_data and "score" in price_data) else {},
            "technical": tech_data if (tech_data and "score" in tech_data) else {},
            "fundamental": fund_data if (fund_data and "score" in fund_data) else {},
            "catalyst": catalyst_data if (catalyst_data and "score" in catalyst_data) else None,
            "options_flow": options_flow_data
            if (options_flow_data and "score" in options_flow_data)
            else None,
            "overall": row["overall_score"],
        }
    else:
        # No valid score data - set to None so response builder can handle it
        item_data["score"] = None

    item_data["score_alert"] = alert

    # Add all narrative and trading fields
    narrative_fields = [
        "signal_type",
        "signal_strength",
        "narrative_headline",
        "recommended_style",
        "style_confidence",
        "optimal_holding_period",
        "risk_level",
        "entry_price",
        "stop_loss",
        "profit_target",
        "position_size_shares",
        "narrative_action_plan",
        "narrative_position_sizing",
        "narrative_company_health",
        "narrative_special_notes",
        "company_health",
        "news_sentiment_score",
    ]

    for field in narrative_fields:
        item_data[field] = row.get(field)

    # Special handling for earnings_date (convert to ISO string)
    earnings_date_value = row.get("earnings_date")
    item_data["earnings_date"] = (
        earnings_date_value.isoformat() if earnings_date_value is not None else None
    )
    item_data["earnings_days_away"] = row.get("earnings_days_away")

    # Normalize news payload
    item_data["recent_news"] = (
        _normalize_recent_news_payload(news_payload)
        if isinstance(news_payload, dict)
        else news_payload
    )

    # Timeframe alignment fields (FEAT-183)
    item_data["timeframe_short_aligned"] = row.get("timeframe_short_aligned")
    item_data["timeframe_long_aligned"] = row.get("timeframe_long_aligned")
    item_data["volume_relative"] = row.get("volume_relative")


__all__ = [
    "build_base_item_data",
    "build_snapshot_data",
]
