"""Watchlist strategy review router."""

from __future__ import annotations

from fastapi import APIRouter

from app.agents.multi_reviewer import MultiReviewer
from app.agents.strategy_reviewer import StrategyReviewer
from app.api.utils import handle_api_errors, require_nonempty_df
from app.storage import get_storage
from app.watchlist.watchlist_repository import WatchlistRepository

from .helpers import (
    _build_signal_data_from_snapshot,
    _handle_dual_review,
    _handle_legacy_review,
)

router = APIRouter()

# Initialize services
storage = get_storage()
watchlist_repo = WatchlistRepository(storage)
strategy_reviewer = StrategyReviewer(storage, primary_provider="gemini")
multi_reviewer = MultiReviewer(storage)


@router.post("/{item_id}/review")
@handle_api_errors("review strategy signal")
async def review_strategy_signal(item_id: str, dual: bool = True) -> dict[str, object]:
    """Get LLM review of trading signal for a watchlist item.

    Args:
        item_id: Watchlist item ID
        dual: If True (default), use both Gemini and Claude for review.
              If False, use single provider with failover.

    Returns:
        For dual=True:
        {
            "symbol": str,
            "review_pair_id": str,
            "gemini_review": {...},
            "claude_review": {...},
            "agreement_score": float,
            "disagreement_severity": str,
            "provider_disagreement": bool,
            "consensus_summary": str
        }
        For dual=False (legacy):
        {
            "symbol": str,
            "review": str,
            "is_valid": bool,
            "provider": str,
            "disagreement": bool,
            "usage": dict
        }
    """
    # Fetch watchlist item
    items_df = watchlist_repo.get_item_with_snapshots(item_id)

    require_nonempty_df(items_df, f"Watchlist item {item_id} not found")

    # Get latest snapshot
    snapshots_df = watchlist_repo.get_latest_snapshot_for_review(item_id)

    require_nonempty_df(snapshots_df, f"No snapshot found for item {item_id}. Run refresh first.")

    # Parse snapshot and build signal data using helper
    snapshot_row = snapshots_df.to_dicts()[0]
    symbol = str(items_df.to_dicts()[0]["symbol"])
    signal_data = _build_signal_data_from_snapshot(snapshot_row, symbol)
    snapshot_id = snapshot_row.get("id")

    if dual:
        return await _handle_dual_review(
            watchlist_repo, multi_reviewer, signal_data, item_id, snapshot_id
        )

    return await _handle_legacy_review(
        watchlist_repo, strategy_reviewer, signal_data, item_id, snapshot_id
    )
