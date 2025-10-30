"""Watchlist API router."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.agent_tasks import (
    ingest_historical_ohlcv,
    refresh_watchlist_scores_task,
    update_technical_indicators,
)
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


class ScoreHistoryPoint(BaseModel):
    """Response model for a single score history point."""

    timestamp: str
    overall: float
    price_score: float
    technical_score: float


class ScoreHistoryResponse(BaseModel):
    """Response model for score history."""

    item_id: str
    symbol: str
    history: list[ScoreHistoryPoint]


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

        with storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO watchlist_items (id, account_id, symbol, note, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [item_id, data.account_id, symbol, data.note, now, now],
            )
            conn.commit()

        logger.info("Watchlist item created", item_id=item_id, symbol=symbol)

        # Trigger background data population for the new ticker
        try:
            # Ingest 200 days of historical OHLCV data
            ingest_historical_ohlcv.delay(tickers=[symbol], days=200)
            logger.info("Triggered historical data ingestion", symbol=symbol)

            # Calculate technical indicators (will run after ingestion completes)
            update_technical_indicators.apply_async(
                args=[[symbol]], countdown=30
            )  # Wait 30s for ingestion
            logger.info("Scheduled technical indicators calculation", symbol=symbol)

            # Refresh watchlist scores for the entire account after data ingestion
            # Note: The refresh logic now safely skips tickers without sufficient historical data,
            # preventing score degradation for existing tickers
            refresh_watchlist_scores_task.apply_async(
                args=[data.account_id], countdown=60
            )  # Wait 60s for everything
            logger.info("Scheduled watchlist score refresh", account_id=data.account_id)

        except Exception as bg_error:
            # Log but don't fail the request - background tasks are async
            logger.warning(
                "Failed to trigger background tasks",
                symbol=symbol,
                error=str(bg_error),
            )

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
        # Check if exists
        items_df = storage.query(
            """
            SELECT id FROM watchlist_items WHERE id = ?
            """,
            [item_id],
        )

        if items_df.is_empty():
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

        logger.info("Watchlist item deleted", item_id=item_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete watchlist item", item_id=item_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete item: {e}") from e


@router.get("/{item_id}/history", response_model=ScoreHistoryResponse)
async def get_score_history(item_id: str, days: int = 7) -> ScoreHistoryResponse:
    """
    Get score history for a watchlist item.

    Args:
        item_id: Watchlist item ID
        days: Number of days of history to return (default 7)

    Returns:
        Score history for the item
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

        # Get history from watchlist_snapshots
        # Note: DuckDB doesn't support parameterized INTERVAL, so we use string formatting
        # days is validated as an int by FastAPI, so this is safe
        history_df = storage.query(
            f"""
            SELECT fetched_at, overall_score, fundamental_score, technical_score
            FROM watchlist_snapshots
            WHERE item_id = ?
            AND fetched_at >= CURRENT_TIMESTAMP - INTERVAL {days} DAYS
            ORDER BY fetched_at ASC
            """,
            [item_id],
        )

        history = []
        for row in history_df.to_dicts():
            fetched_at = row["fetched_at"]
            if hasattr(fetched_at, "isoformat"):
                fetched_at = fetched_at.isoformat()

            history.append(
                ScoreHistoryPoint(
                    timestamp=fetched_at,
                    overall=row["overall_score"],
                    price_score=row[
                        "fundamental_score"
                    ],  # Using fundamental_score as proxy for price
                    technical_score=row["technical_score"],
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


class RefreshRequest(BaseModel):
    """Request model for manual refresh."""

    account_id: str = Field(..., description="Account ID to refresh")


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_watchlist_scores(data: RefreshRequest) -> RefreshResponse:
    """
    Manually trigger a refresh of all watchlist scores for an account.

    Args:
        data: Refresh request data with account_id

    Returns:
        Refresh status
    """
    try:
        account_id = data.account_id
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
        tickers = [item["symbol"] for item in items]

        # Trigger background data refresh for ALL tickers
        try:
            # Fetch latest OHLCV data (last 5 days to update recent bars)
            ingest_historical_ohlcv.delay(tickers=tickers, days=5)
            logger.info("Triggered OHLCV data refresh", tickers=tickers, account_id=account_id)

            # Update technical indicators (will run after ingestion completes)
            update_technical_indicators.apply_async(args=[tickers], countdown=15)
            logger.info("Scheduled technical indicators update", tickers=tickers)

            # Refresh watchlist scores (will run after indicators complete)
            refresh_watchlist_scores_task.apply_async(args=[account_id], countdown=30)
            logger.info("Scheduled watchlist score refresh", account_id=account_id)

        except Exception as bg_error:
            logger.warning(
                "Failed to trigger background refresh tasks",
                account_id=account_id,
                error=str(bg_error),
            )

        # Also do immediate synchronous refresh
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
            message=f"Refreshed {refreshed} of {len(items)} items (background data fetch queued)",
            refreshed_count=refreshed,
        )
    except Exception as e:
        logger.error("Failed to refresh watchlist scores", account_id=account_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to refresh scores: {e}") from e
