"""Score and staleness checking utilities for watchlist service.

This module provides:
- Score alert checking
- Staleness information management
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

# Import from scoring_service.helpers
from app.watchlist.scoring_service.helpers import is_stale as scoring_is_stale

from ...storage import PortfolioStorage


def check_score_alert(storage: PortfolioStorage, item_id: str, current_score: float) -> bool:
    """Check if score changed >10 points in last 7 days."""
    history_df = storage.query(
        """
        SELECT overall_score
        FROM watchlist_snapshots_v
        WHERE item_id = ?
          AND fetched_at >= current_timestamp - INTERVAL '7 days'
        ORDER BY fetched_at ASC
        LIMIT 1
        """,
        [item_id],
    )

    if history_df.is_empty():
        return False

    week_ago_score = float(history_df["overall_score"][0])
    return abs(current_score - week_ago_score) > 10.0


def add_staleness_info(
    raw_metrics: dict[str, Any],
    fetched_at: datetime | None,
    stale_ttl_minutes: int,
) -> None:
    """Add staleness information to raw_metrics in place.

    Args:
        raw_metrics: Metrics dictionary to update
        fetched_at: When metrics were fetched
        stale_ttl_minutes: TTL for staleness check
    """
    if not fetched_at or not isinstance(raw_metrics, dict):
        return

    if isinstance(fetched_at, datetime) and fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=UTC)

    current_time = datetime.now(UTC)
    fetched_at_iso = fetched_at.isoformat().replace("+00:00", "Z")

    for metric_type in ["price", "technical"]:
        if metric_type in raw_metrics and isinstance(raw_metrics[metric_type], dict):
            raw_metrics[metric_type]["stale"] = scoring_is_stale(
                fetched_at, stale_ttl_minutes, current_time
            )
            raw_metrics[metric_type]["updated_at"] = fetched_at_iso


__all__ = [
    "add_staleness_info",
    "check_score_alert",
]
