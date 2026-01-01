"""Watchlist reports and history router."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from app.api.utils import handle_api_errors, require_nonempty_df
from app.logging_config import get_logger
from app.storage import get_storage
from app.watchlist._service.helpers import safe_json_loads
from app.watchlist.history import build_score_timeline
from app.watchlist.models import WatchlistSnapshot
from app.watchlist.response_builders import (
    ScoreHistoryPoint,
    ScoreHistoryResponse,
)
from app.watchlist.watchlist_repository import WatchlistRepository

from .helpers import DAILY_REPORT_STALE_HOURS

logger = get_logger(__name__)

router = APIRouter()

# Initialize services
storage = get_storage()
watchlist_repo = WatchlistRepository(storage)


@router.get("/daily-report")
@handle_api_errors("fetch daily report")
async def get_daily_report() -> dict[str, object]:
    """
    Get the latest daily watchlist report.

    Returns:
        Latest report with symbols added, removed, and score changes
    """
    # Get latest report
    report_df = watchlist_repo.get_latest_daily_report()

    if report_df.is_empty():
        return {
            "report_date": None,
            "generated_at": None,
            "symbols_added": [],
            "symbols_removed": [],
            "score_changes": [],
            "is_stale": True,
        }

    report_row = report_df.to_dicts()[0]

    # Parse JSON fields with safe parsing
    symbols_added = safe_json_loads(report_row["symbols_added"], [])
    symbols_removed = safe_json_loads(report_row["symbols_removed"], [])
    score_changes = safe_json_loads(report_row["score_changes"], [])

    # Check if report is stale (>48 hours old)
    generated_at = report_row["generated_at"]
    if isinstance(generated_at, str):
        generated_at = datetime.fromisoformat(generated_at)
    is_stale = (datetime.now(UTC) - generated_at).total_seconds() > DAILY_REPORT_STALE_HOURS * 3600

    return {
        "report_date": report_row["report_date"].isoformat() if report_row["report_date"] else None,
        "generated_at": generated_at.isoformat() if generated_at else None,
        "symbols_added": symbols_added,
        "symbols_removed": symbols_removed,
        "score_changes": score_changes,
        "is_stale": is_stale,
    }


@router.get("/{item_id}/history", response_model=ScoreHistoryResponse)
@handle_api_errors("fetch score history")
async def get_score_history(item_id: str, days: int = 10) -> ScoreHistoryResponse:
    """
    Get score history for a watchlist item from snapshots.

    Fetches historical snapshots and extracts scores from raw_metrics JSONB.

    Args:
        item_id: Watchlist item ID
        days: Number of days of history to return (default 10)

    Returns:
        Score history with price/technical scores extracted from snapshots
    """
    # Get item info
    item_df = watchlist_repo.get_symbol_by_item_id(item_id)

    require_nonempty_df(item_df, "Watchlist item not found")

    symbol = item_df.to_dicts()[0]["symbol"]

    # Fetch snapshots from database using the normalized view
    snapshots_df = watchlist_repo.get_snapshots_with_metrics(item_id)

    if snapshots_df.is_empty():
        logger.warning("No snapshot data available", symbol=symbol, item_id=item_id)
        return ScoreHistoryResponse(
            item_id=item_id,
            symbol=symbol,
            history=[],
        )

    # Convert to WatchlistSnapshot objects
    snapshots = []
    for row in snapshots_df.to_dicts():
        # Parse raw_metrics safely (JSON column might be string or dict)
        raw_metrics = safe_json_loads(row.get("raw_metrics"), {})

        snapshot = WatchlistSnapshot(
            item_id=row["item_id"],
            fetched_at=row["fetched_at"],
            price=row.get("price"),
            technical_score=row.get("technical_score"),
            overall_score=row.get("overall_score"),
            raw_metrics=raw_metrics,
        )
        snapshots.append(snapshot)

    # Build timeline from snapshots
    timeline = build_score_timeline(snapshots, window_days=days)

    # Convert to API response format
    history = []
    for point in timeline:
        history.append(
            ScoreHistoryPoint(
                timestamp=point.date.isoformat(),
                overall=point.overall_score,
                price_score=point.price_score or 0.0,
                technical_score=point.technical_score or 0.0,
            )
        )

    return ScoreHistoryResponse(
        item_id=item_id,
        symbol=symbol,
        history=history,
    )
