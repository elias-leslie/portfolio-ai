"""Watchlist CRUD operations router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.api.utils import handle_api_errors
from app.logging_config import get_logger
from app.middleware.cache import cache_response
from app.storage import get_storage
from app.utils.db_helpers import generate_uuid
from app.utils.formatters import utc_now_iso
from app.utils.watchlist_cache import invalidate_all_watchlist_caches
from app.watchlist.background_tasks import schedule_new_symbol_tasks
from app.watchlist.response_builders import (
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistItemUpdate,
    WatchlistListResponse,
    build_watchlist_item_responses,
)
from app.watchlist.validators import validate_symbol
from app.watchlist.watchlist_repository import WatchlistRepository
from app.watchlist.watchlist_service import WatchlistService

from .helpers import WATCHLIST_CACHE_TTL_SECONDS, _require_watchlist_item

logger = get_logger(__name__)

router = APIRouter()

# Initialize services
storage = get_storage()
watchlist_service = WatchlistService(storage)
watchlist_repo = WatchlistRepository(storage)


@router.get("/", response_model=WatchlistListResponse)
@cache_response(ttl=WATCHLIST_CACHE_TTL_SECONDS)
@handle_api_errors("fetch watchlist items")
async def list_watchlist_items(request: Request) -> WatchlistListResponse:
    """
    List all watchlist items with current scores.

    Watchlist is user-level (not account-specific). Shows all symbols being monitored.

    Returns:
        List of watchlist items with current scores
    """
    items = await run_in_threadpool(watchlist_service.get_items_with_scores)

    return WatchlistListResponse(
        items=build_watchlist_item_responses(items),
        total_count=len(items),
    )


@router.get("/{item_id}", response_model=WatchlistItemResponse)
@handle_api_errors("fetch watchlist item")
async def get_watchlist_item(item_id: str) -> WatchlistItemResponse:
    """
    Get a single watchlist item with current score and 7-day history.

    Args:
        item_id: Watchlist item ID

    Returns:
        Watchlist item with scores
    """
    # Use optimized single-item query instead of fetching all items
    item = await run_in_threadpool(watchlist_service.get_item_with_score_by_id, item_id)

    if item is None:
        raise HTTPException(status_code=404, detail="Watchlist item not found")

    return WatchlistItemResponse.from_service_dict(item)


@router.post("/", response_model=WatchlistItemResponse, status_code=201)
@handle_api_errors("create watchlist item")
async def create_watchlist_item(data: WatchlistItemCreate) -> WatchlistItemResponse:
    """
    Add a symbol to the watchlist.

    Args:
        data: Watchlist item creation data

    Returns:
        Created watchlist item
    """
    # Validate and normalize symbol
    symbol = validate_symbol(data.symbol)

    # Check if already exists (globally - watchlist is user-level)
    if watchlist_repo.check_item_exists(symbol):
        raise HTTPException(status_code=409, detail=f"Symbol {symbol} already in watchlist")

    # Create item
    item_id = generate_uuid()
    now = utc_now_iso()

    watchlist_repo.create_item(item_id, symbol, data.note, now)

    # Invalidate all watchlist caches (Redis symbols + HTTP response)
    invalidate_all_watchlist_caches()

    logger.info("Watchlist item created", item_id=item_id, symbol=symbol)

    # Trigger background data population for the new symbol
    schedule_new_symbol_tasks(symbol)

    return WatchlistItemResponse(
        id=item_id,
        symbol=symbol,
        note=data.note,
        created_at=now,
        updated_at=now,
        readiness_score=None,
        confidence_level=None,
        gap_warning=None,
        timeframe_short_aligned=None,
        timeframe_long_aligned=None,
        volume_relative=None,
        data_quality=None,
    )


@router.patch("/{item_id}", response_model=WatchlistItemResponse)
@handle_api_errors("update watchlist item")
async def update_watchlist_item(item_id: str, data: WatchlistItemUpdate) -> WatchlistItemResponse:
    """
    Update a watchlist item (currently only supports note updates).

    Args:
        item_id: Watchlist item ID
        data: Update data

    Returns:
        Updated watchlist item
    """
    # Check if exists
    _require_watchlist_item(item_id, watchlist_repo)

    now = utc_now_iso()

    # Update note
    watchlist_repo.update_item_note(item_id, data.note, now)

    logger.info("Watchlist item updated", item_id=item_id)

    # Fetch updated item
    return await get_watchlist_item(item_id)


@router.delete("/{item_id}", status_code=204)
@handle_api_errors("delete watchlist item")
async def delete_watchlist_item(item_id: str) -> None:
    """
    Delete a watchlist item.

    Args:
        item_id: Watchlist item ID
    """
    # Check if exists
    _require_watchlist_item(item_id, watchlist_repo)

    # Delete snapshots first (foreign key), then delete item
    watchlist_repo.delete_item(item_id)

    # Invalidate all watchlist caches (Redis symbols + HTTP response)
    invalidate_all_watchlist_caches()

    logger.info("Watchlist item deleted", item_id=item_id)
