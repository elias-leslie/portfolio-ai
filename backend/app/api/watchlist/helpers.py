"""Watchlist API helper functions."""

from __future__ import annotations

from fastapi import HTTPException

from app.api.utils import require_nonempty_df
from app.watchlist.response_builders import (
    FailedTickerInfo,
    RefreshResponse,
    RefreshStatusResponse,
)
from app.watchlist.watchlist_repository import WatchlistRepository

WATCHLIST_CACHE_TTL_SECONDS = 60  # Cache watchlist responses for 1 minute
REDIS_WATCHLIST_REFRESH_KEY = "watchlist:refresh:global"  # Redis key for refresh lock


def _build_not_refreshing_response() -> RefreshStatusResponse:
    """Build a RefreshStatusResponse for when no refresh is in progress."""
    return RefreshStatusResponse(
        is_refreshing=False,
        started_at=None,
        elapsed_seconds=None,
        total_items=None,
        processed_items=None,
        current_symbol=None,
        percent_complete=None,
    )


def _build_refresh_response(
    success_count: int,
    failed_count: int,
    total_count: int,
    failed_list: list[FailedTickerInfo],
) -> tuple[int, dict[str, object]]:
    """Build refresh response with appropriate status code.

    Args:
        success_count: Number of successfully refreshed items
        failed_count: Number of failed items
        total_count: Total number of items
        failed_list: List of failed ticker information

    Returns:
        Tuple of (status_code, response_dict)
    """

    if failed_count == 0:
        # All success
        response = RefreshResponse(
            status="success",
            message=f"Refreshed all {success_count} items successfully",
            refreshed_count=success_count,
            failed_count=0,
            failed=[],
        )
        return (200, response.model_dump())

    if success_count > 0:
        # Partial success - return 207 Multi-Status
        response = RefreshResponse(
            status="partial_success",
            message=f"Refreshed {success_count} of {total_count} items ({failed_count} failed)",
            refreshed_count=success_count,
            failed_count=failed_count,
            failed=failed_list,
        )
        return (207, response.model_dump())

    # Complete failure - return 500
    raise HTTPException(
        status_code=500,
        detail=f"Failed to refresh any items ({failed_count} failed)",
    )


def _require_watchlist_item(item_id: str, watchlist_repo: WatchlistRepository) -> None:
    """Validate that a watchlist item exists, raising HTTPException if not.

    Args:
        item_id: Watchlist item ID to validate
        watchlist_repo: Repository instance to query

    Raises:
        HTTPException: 404 if item not found
    """
    items_df = watchlist_repo.get_item_by_id(item_id)
    require_nonempty_df(items_df, "Watchlist item not found")
