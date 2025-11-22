"""Watchlist API router."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.logging_config import get_logger
from app.middleware.cache import cache_response, invalidate_endpoint_cache
from app.storage import get_storage
from app.utils.watchlist_cache import invalidate_watchlist_cache
from app.watchlist.background_tasks import schedule_new_ticker_tasks, schedule_refresh_tasks
from app.watchlist.history import build_score_timeline
from app.watchlist.models import WatchlistSnapshot
from app.watchlist.response_builders import (
    FailedTickerInfo,
    RefreshRequest,
    RefreshResponse,
    RefreshStatusResponse,
    ScoreHistoryPoint,
    ScoreHistoryResponse,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistItemUpdate,
    WatchlistListResponse,
    build_watchlist_item_responses,
)
from app.watchlist.service import (
    _get_redis_client,
)
from app.watchlist.service import (
    refresh_watchlist_scores as refresh_watchlist_scores_service,
)
from app.watchlist.validators import validate_symbol
from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# Initialize services
storage = get_storage()
watchlist_service = WatchlistService(storage)


# Endpoints
@router.get("", response_model=WatchlistListResponse)
@cache_response(ttl=60)  # 1 minute cache
async def list_watchlist_items(request: Request) -> WatchlistListResponse:
    """
    List all watchlist items with current scores.

    Watchlist is user-level (not account-specific). Shows all symbols being monitored.

    Returns:
        List of watchlist items with current scores
    """
    try:
        items = await run_in_threadpool(watchlist_service.get_items_with_scores)

        return WatchlistListResponse(
            items=build_watchlist_item_responses(items),
            total_count=len(items),
        )
    except Exception as e:
        logger.error("Failed to list watchlist items", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch watchlist: {e}") from e


@router.post("", response_model=WatchlistItemResponse, status_code=201)
async def create_watchlist_item(data: WatchlistItemCreate) -> WatchlistItemResponse:
    """
    Add a ticker to the watchlist.

    Args:
        data: Watchlist item creation data

    Returns:
        Created watchlist item
    """
    try:
        # Validate and normalize symbol
        symbol = validate_symbol(data.symbol)

        # Check if already exists (globally - watchlist is user-level)
        existing_df = storage.query(
            """
            SELECT id FROM watchlist_items
            WHERE symbol = ?
            """,
            [symbol],
        )
        if not existing_df.is_empty():
            raise HTTPException(status_code=409, detail=f"Ticker {symbol} already in watchlist")

        # Create item
        item_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO watchlist_items (id, symbol, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                [item_id, symbol, data.note, now, now],
            )
            conn.commit()

        # Invalidate watchlist symbols cache (Issue #4 fix)
        invalidate_watchlist_cache()

        # Invalidate response cache for watchlist endpoint
        invalidate_endpoint_cache("/api/watchlist", method="GET")

        logger.info("Watchlist item created", item_id=item_id, symbol=symbol)

        # Trigger background data population for the new ticker
        schedule_new_ticker_tasks(symbol)

        return WatchlistItemResponse(
            id=item_id,
            symbol=symbol,
            note=data.note,
            created_at=now,
            updated_at=now,
            readiness_score=None,
            confidence_level=None,
            gap_warning=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create watchlist item", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create item: {e}") from e


@router.get("/refresh-status", response_model=RefreshStatusResponse)
async def get_refresh_status() -> RefreshStatusResponse:
    """
    Get the current refresh status for the watchlist.

    Returns:
        Refresh status with progress information
    """
    try:
        redis_client = _get_redis_client()
        redis_key = "watchlist:refresh:global"
        status_json = redis_client.get(redis_key)

        if not status_json:
            # No refresh in progress
            return RefreshStatusResponse(
                is_refreshing=False,
                started_at=None,
                elapsed_seconds=None,
                total_items=None,
                processed_items=None,
                current_symbol=None,
                percent_complete=None,
            )

        status_data = json.loads(str(status_json))
        started_at_str = status_data.get("started_at")
        total_items = status_data.get("total_items", 0)
        processed_items = status_data.get("processed_items", 0)

        # Calculate elapsed time
        elapsed_seconds = None
        if started_at_str:
            started_at = datetime.fromisoformat(started_at_str)
            elapsed_seconds = (datetime.now(UTC) - started_at).total_seconds()

        # Calculate percentage
        percent_complete = None
        if total_items and total_items > 0:
            percent_complete = round((processed_items / total_items) * 100, 1)

        return RefreshStatusResponse(
            is_refreshing=True,
            started_at=started_at_str,
            elapsed_seconds=elapsed_seconds,
            total_items=total_items,
            processed_items=processed_items,
            current_symbol=status_data.get("current_symbol"),
            percent_complete=percent_complete,
        )

    except Exception as e:
        logger.error("Failed to get refresh status", error=str(e))
        # Return no refresh in progress on error
        return RefreshStatusResponse(
            is_refreshing=False,
            started_at=None,
            elapsed_seconds=None,
            total_items=None,
            processed_items=None,
            current_symbol=None,
            percent_complete=None,
        )


@router.get("/{item_id}", response_model=WatchlistItemResponse)
async def get_watchlist_item(item_id: str) -> WatchlistItemResponse:
    """
    Get a single watchlist item with current score and 7-day history.

    Args:
        item_id: Watchlist item ID

    Returns:
        Watchlist item with scores
    """
    try:
        # Use optimized single-item query instead of fetching all items
        item = await run_in_threadpool(watchlist_service.get_item_with_score_by_id, item_id)

        if item is None:
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        return WatchlistItemResponse.from_service_dict(item)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get watchlist item", item_id=item_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch item: {e}") from e


@router.patch("/{item_id}", response_model=WatchlistItemResponse)
async def update_watchlist_item(item_id: str, data: WatchlistItemUpdate) -> WatchlistItemResponse:
    """
    Update a watchlist item (currently only supports note updates).

    Args:
        item_id: Watchlist item ID
        data: Update data

    Returns:
        Updated watchlist item
    """
    try:
        # Check if exists
        items_df = storage.query(
            """
            SELECT id, symbol FROM watchlist_items WHERE id = ?
            """,
            [item_id],
        )

        if items_df.is_empty():
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        now = datetime.now(UTC).isoformat()

        # Update note
        with storage.connection() as conn:
            conn.execute(
                """
                UPDATE watchlist_items
                SET note = ?, updated_at = ?
                WHERE id = ?
                """,
                [data.note, now, item_id],
            )
            conn.commit()

        logger.info("Watchlist item updated", item_id=item_id)

        # Fetch updated item
        return await get_watchlist_item(item_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update watchlist item", item_id=item_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update item: {e}") from e


@router.delete("/{item_id}", status_code=204)
async def delete_watchlist_item(item_id: str) -> None:
    """
    Delete a watchlist item.

    Args:
        item_id: Watchlist item ID
    """
    try:
        # DEBUG: Log the incoming delete request
        logger.info("DELETE request received", item_id=item_id, item_id_type=type(item_id).__name__)

        # Check if exists
        items_df = storage.query(
            """
            SELECT id FROM watchlist_items WHERE id = ?
            """,
            [item_id],
        )

        # DEBUG: Log what we found
        logger.info(
            "Database query result", found=not items_df.is_empty(), result_count=len(items_df)
        )

        if items_df.is_empty():
            # DEBUG: Log all existing items to compare
            all_items = storage.query("SELECT id, symbol FROM watchlist_items")
            logger.error(
                "Item not found - listing all items",
                requested_id=item_id,
                all_items=all_items.to_dicts() if not all_items.is_empty() else [],
            )
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        # Delete snapshots first (foreign key), then delete item
        with storage.connection() as conn:
            conn.execute(
                """
                DELETE FROM watchlist_snapshots WHERE item_id = ?
                """,
                [item_id],
            )
            conn.execute(
                """
                DELETE FROM watchlist_items WHERE id = ?
                """,
                [item_id],
            )
            conn.commit()

        # Invalidate watchlist symbols cache (Issue #4 fix)
        invalidate_watchlist_cache()

        # Invalidate response cache for watchlist endpoint
        invalidate_endpoint_cache("/api/watchlist", method="GET")

        logger.info("Watchlist item deleted", item_id=item_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete watchlist item", item_id=item_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete item: {e}") from e


@router.get("/{item_id}/history", response_model=ScoreHistoryResponse)
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
    try:
        # Get item info
        item_df = storage.query(
            """
            SELECT symbol FROM watchlist_items WHERE id = ?
            """,
            [item_id],
        )

        if item_df.is_empty():
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        symbol = item_df.to_dicts()[0]["symbol"]

        # Fetch snapshots from database
        snapshots_df = storage.query(
            """
            SELECT item_id, fetched_at, price, technical_score, overall_score, raw_metrics
            FROM watchlist_snapshots
            WHERE item_id = ?
            ORDER BY fetched_at DESC
            """,
            [item_id],
        )

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
            # Parse raw_metrics if it's a string (from JSON column)
            raw_metrics = row.get("raw_metrics", {})
            if isinstance(raw_metrics, str):
                raw_metrics = json.loads(raw_metrics)

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
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get score history", item_id=item_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get history: {e}") from e


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_watchlist_scores(data: RefreshRequest) -> RefreshResponse:
    """
    Manually trigger a refresh of all watchlist scores.

    Args:
        data: Refresh request data (no fields needed)

    Returns:
        Refresh status (200 OK for all success, 207 Multi-Status for partial success)
    """
    try:
        logger.info("Refresh request started")

        # Get all watchlist items
        items_df = storage.query(
            """
            SELECT id, symbol FROM watchlist_items
            """
        )

        if items_df.is_empty():
            return RefreshResponse(
                status="success",
                message="No items in watchlist",
                refreshed_count=0,
                failed_count=0,
                failed=[],
            )

        items = items_df.to_dicts()
        tickers = [item["symbol"] for item in items]
        logger.info("Refreshing tickers", tickers=tickers, count=len(tickers))

        # Trigger background data refresh for ALL tickers
        schedule_refresh_tasks(tickers)

        # Do immediate synchronous refresh with Redis progress tracking
        result = refresh_watchlist_scores_service(storage)
        success_count = result.get("success_count", 0)
        failed_count = result.get("failed_count", 0)
        failed_list = [FailedTickerInfo(**f) for f in result.get("failed", [])]

        logger.info(
            "Watchlist refresh completed",
            success_count=success_count,
            failed_count=failed_count,
        )

        # Determine status code based on results
        if failed_count == 0:
            # All success
            return RefreshResponse(
                status="success",
                message=f"Refreshed all {success_count} items successfully",
                refreshed_count=success_count,
                failed_count=0,
                failed=[],
            )

        if success_count > 0:
            # Partial success - return 207 Multi-Status
            response_data = RefreshResponse(
                status="partial_success",
                message=f"Refreshed {success_count} of {len(items)} items ({failed_count} failed)",
                refreshed_count=success_count,
                failed_count=failed_count,
                failed=failed_list,
            )
            return JSONResponse(status_code=207, content=response_data.model_dump())  # type: ignore[return-value]

        # Complete failure - return 500
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh any items ({failed_count} failed)",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to refresh watchlist scores", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to refresh scores: {e}") from e
