"""Watchlist API router."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.storage import get_storage
from app.watchlist.service import WatchlistService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# Initialize services
storage = get_storage()
watchlist_service = WatchlistService(storage)


# Request/Response models
class WatchlistItemCreate(BaseModel):
    """Request model for creating a watchlist item."""

    account_id: str = Field(..., description="Account ID")
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    note: str | None = Field(None, description="Optional notes about this ticker")


class WatchlistItemUpdate(BaseModel):
    """Request model for updating a watchlist item."""

    note: str | None = Field(None, description="Optional notes about this ticker")


class ScoreComponentResponse(BaseModel):
    """Response model for individual score component."""

    score: float
    weight: float
    stale: bool
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScoreBreakdownResponse(BaseModel):
    """Response model for score breakdown."""

    price: ScoreComponentResponse
    technical: ScoreComponentResponse
    overall: float


class WatchlistItemResponse(BaseModel):
    """Response model for watchlist item with current scores."""

    id: str
    account_id: str
    symbol: str
    note: str | None = None
    created_at: str
    updated_at: str
    current_score: ScoreBreakdownResponse | None = None
    score_alert: bool = False  # True if score changed >10 points in last 7 days


class WatchlistListResponse(BaseModel):
    """Response model for list of watchlist items."""

    items: list[WatchlistItemResponse]
    total_count: int


class RefreshResponse(BaseModel):
    """Response model for manual refresh request."""

    status: str
    message: str
    refreshed_count: int


# Endpoints
@router.get("", response_model=WatchlistListResponse)
async def list_watchlist_items(account_id: str) -> WatchlistListResponse:
    """
    List all watchlist items for an account with current scores.

    Args:
        account_id: Account ID to fetch watchlist for

    Returns:
        List of watchlist items with current scores
    """
    try:
        items = watchlist_service.get_items_with_scores(account_id)

        return WatchlistListResponse(
            items=[
                WatchlistItemResponse(
                    id=item["id"],
                    account_id=item["account_id"],
                    symbol=item["symbol"],
                    note=item.get("note"),
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    current_score=(
                        ScoreBreakdownResponse(
                            price=ScoreComponentResponse(**item["score"]["price"]),
                            technical=ScoreComponentResponse(**item["score"]["technical"]),
                            overall=item["score"]["overall"],
                        )
                        if item.get("score")
                        else None
                    ),
                    score_alert=item.get("score_alert", False),
                )
                for item in items
            ],
            total_count=len(items),
        )
    except Exception as e:
        logger.error("Failed to list watchlist items", account_id=account_id, error=str(e))
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
        # Validate symbol format (basic check)
        if not data.symbol or not data.symbol.strip():
            raise HTTPException(status_code=400, detail="Symbol cannot be empty")

        symbol = data.symbol.strip().upper()

        # Check if already exists
        existing_df = storage.query(
            """
            SELECT id FROM watchlist_items
            WHERE account_id = ? AND symbol = ?
            """,
            [data.account_id, symbol],
        )
        if not existing_df.is_empty():
            raise HTTPException(status_code=409, detail=f"Ticker {symbol} already in watchlist")

        # Create item
        item_id = str(datetime.now(UTC).timestamp()).replace(".", "")
        now = datetime.now(UTC).isoformat()

        storage.query(
            """
            INSERT INTO watchlist_items (id, account_id, symbol, note, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [item_id, data.account_id, symbol, data.note, now, now],
        )

        logger.info("Watchlist item created", item_id=item_id, symbol=symbol)

        return WatchlistItemResponse(
            id=item_id,
            account_id=data.account_id,
            symbol=symbol,
            note=data.note,
            created_at=now,
            updated_at=now,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create watchlist item", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to create item: {e}") from e


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
        items_df = storage.query(
            """
            SELECT id, account_id, symbol, note, created_at, updated_at
            FROM watchlist_items
            WHERE id = ?
            """,
            [item_id],
        )

        if items_df.is_empty():
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        item = items_df.to_dicts()[0]

        # Get current score
        scores = watchlist_service.get_items_with_scores(item["account_id"])
        matching_score = next((s for s in scores if s["id"] == item_id), None)

        # Convert datetime objects to ISO strings if needed
        created_at = item["created_at"]
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()
        updated_at = item["updated_at"]
        if hasattr(updated_at, "isoformat"):
            updated_at = updated_at.isoformat()

        return WatchlistItemResponse(
            id=item["id"],
            account_id=item["account_id"],
            symbol=item["symbol"],
            note=item["note"],
            created_at=created_at,
            updated_at=updated_at,
            current_score=(
                ScoreBreakdownResponse(
                    price=ScoreComponentResponse(**matching_score["score"]["price"]),
                    technical=ScoreComponentResponse(**matching_score["score"]["technical"]),
                    overall=matching_score["score"]["overall"],
                )
                if matching_score and matching_score.get("score")
                else None
            ),
            score_alert=matching_score.get("score_alert", False) if matching_score else False,
        )
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
            SELECT account_id, symbol FROM watchlist_items WHERE id = ?
            """,
            [item_id],
        )

        if items_df.is_empty():
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        now = datetime.now(UTC).isoformat()

        # Update note
        storage.query(
            """
            UPDATE watchlist_items
            SET note = ?, updated_at = ?
            WHERE id = ?
            """,
            [data.note, now, item_id],
        )

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
        # Check if exists
        items_df = storage.query(
            """
            SELECT id FROM watchlist_items WHERE id = ?
            """,
            [item_id],
        )

        if items_df.is_empty():
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        # Delete snapshots first (foreign key)
        storage.query(
            """
            DELETE FROM watchlist_snapshots WHERE item_id = ?
            """,
            [item_id],
        )

        # Delete item
        storage.query(
            """
            DELETE FROM watchlist_items WHERE id = ?
            """,
            [item_id],
        )

        logger.info("Watchlist item deleted", item_id=item_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete watchlist item", item_id=item_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete item: {e}") from e


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_watchlist_scores(account_id: str) -> RefreshResponse:
    """
    Manually trigger a refresh of all watchlist scores for an account.

    Args:
        account_id: Account ID

    Returns:
        Refresh status
    """
    try:
        # Get all items for this account
        items_df = storage.query(
            """
            SELECT id, symbol FROM watchlist_items WHERE account_id = ?
            """,
            [account_id],
        )

        if items_df.is_empty():
            return RefreshResponse(
                status="success",
                message="No items in watchlist",
                refreshed_count=0,
            )

        items = items_df.to_dicts()

        # Refresh scores for each item
        refreshed = 0
        for item in items:
            try:
                watchlist_service.refresh_scores(item["id"], item["symbol"])
                refreshed += 1
            except Exception as e:
                logger.warning(
                    "Failed to refresh score for item",
                    item_id=item["id"],
                    symbol=item["symbol"],
                    error=str(e),
                )

        logger.info("Watchlist scores refreshed", account_id=account_id, count=refreshed)

        return RefreshResponse(
            status="success",
            message=f"Refreshed {refreshed} of {len(items)} items",
            refreshed_count=refreshed,
        )
    except Exception as e:
        logger.error("Failed to refresh watchlist scores", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to refresh scores: {e}") from e
