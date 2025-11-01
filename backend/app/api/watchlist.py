"""Watchlist API router."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import yfinance as yf  # type: ignore[import-untyped]
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.storage import get_storage
from app.tasks.agent_tasks import (
    ingest_historical_ohlcv,
    refresh_watchlist_scores_task,
    update_technical_indicators,
)
from app.watchlist.service import (
    WatchlistService,
    _get_redis_client,
)
from app.watchlist.service import (
    refresh_watchlist_scores as refresh_watchlist_scores_service,
)

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


class FailedTickerInfo(BaseModel):
    """Information about a failed ticker refresh."""

    symbol: str
    reason: str


class RefreshResponse(BaseModel):
    """Response model for manual refresh request."""

    status: str
    message: str
    refreshed_count: int
    failed_count: int = 0
    failed: list[FailedTickerInfo] = Field(default_factory=list)


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
        items = await run_in_threadpool(watchlist_service.get_items_with_scores, account_id)

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
        item_id = str(uuid.uuid4())
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


class RefreshStatusResponse(BaseModel):
    """Response model for refresh status query."""

    is_refreshing: bool = Field(..., description="Whether a refresh is currently in progress")
    started_at: str | None = Field(None, description="ISO timestamp when refresh started")
    elapsed_seconds: float | None = Field(None, description="Seconds elapsed since start")
    total_items: int | None = Field(None, description="Total number of items to process")
    processed_items: int | None = Field(None, description="Number of items processed so far")
    current_symbol: str | None = Field(None, description="Currently processing symbol")
    percent_complete: float | None = Field(None, description="Percentage complete (0-100)")


@router.get("/refresh-status", response_model=RefreshStatusResponse)
async def get_refresh_status(account_id: str) -> RefreshStatusResponse:
    """
    Get the current refresh status for an account's watchlist.

    Args:
        account_id: Account ID to check refresh status for

    Returns:
        Refresh status with progress information
    """
    try:
        redis_client = _get_redis_client()
        redis_key = f"watchlist:refresh:{account_id}"
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
        logger.error("Failed to get refresh status", account_id=account_id, error=str(e))
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

        return WatchlistItemResponse(
            id=item["id"],
            account_id=item["account_id"],
            symbol=item["symbol"],
            note=item["note"],
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
async def get_score_history(item_id: str, days: int = 10) -> ScoreHistoryResponse:
    """
    Get score history for a watchlist item.

    Fetches actual historical price data from yfinance and computes scores
    based on price trends to provide meaningful sparkline data.

    Args:
        item_id: Watchlist item ID
        days: Number of trading days of history to return (default 10)

    Returns:
        Score history with computed scores from actual price data
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

        # Fetch historical price data from yfinance
        # Request ~15 calendar days to ensure we get at least 10 trading days
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=15)

        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start_date, end=end_date, interval="1d")

        if hist.empty:
            logger.warning("No historical data available", symbol=symbol)
            # Return empty history if no data available
            return ScoreHistoryResponse(
                item_id=item_id,
                symbol=symbol,
                history=[],
            )

        # Take only the last N trading days (defaults to 10)
        hist = hist.tail(days)

        # Compute scores based on normalized price movement
        # Use closing prices to calculate a score from 0-100
        closes = hist["Close"].values
        min_price = float(closes.min())
        max_price = float(closes.max())
        price_range = max_price - min_price if max_price > min_price else 1.0

        history = []
        for idx, (timestamp, row) in enumerate(hist.iterrows()):
            close_price = float(row["Close"])

            # Normalize price to 0-100 scale based on range
            price_score = ((close_price - min_price) / price_range) * 100

            # For technical score, use a simple momentum indicator
            # (comparing current price to first price in the period)
            if idx > 0:
                first_price = float(closes[0])
                change_pct = ((close_price - first_price) / first_price) * 100
                # Map ±10% change to 0-100 scale, clamped
                technical_score = max(0, min(100, 50 + (change_pct * 5)))
            else:
                technical_score = 50.0  # Neutral for first point

            # Overall score is weighted average (50/50)
            overall_score = (price_score * 0.5) + (technical_score * 0.5)

            history.append(
                ScoreHistoryPoint(
                    timestamp=timestamp.isoformat()
                    if hasattr(timestamp, "isoformat")
                    else str(timestamp),
                    overall=overall_score,
                    price_score=price_score,
                    technical_score=technical_score,
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
        logger.error("Failed to get score history", item_id=item_id, symbol=symbol, error=str(e))
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
        Refresh status (200 OK for all success, 207 Multi-Status for partial success)
    """
    try:
        account_id = data.account_id
        logger.info("Refresh request started", account_id=account_id)

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
                failed_count=0,
                failed=[],
            )

        items = items_df.to_dicts()
        tickers = [item["symbol"] for item in items]
        logger.info("Refreshing tickers", tickers=tickers, count=len(tickers))

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

        # Do immediate synchronous refresh with Redis progress tracking
        result = refresh_watchlist_scores_service(storage, account_id=account_id)
        success_count = result.get("success_count", 0)
        failed_count = result.get("failed_count", 0)
        failed_list = [FailedTickerInfo(**f) for f in result.get("failed", [])]

        logger.info(
            "Watchlist refresh completed",
            account_id=account_id,
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
        logger.error("Failed to refresh watchlist scores", account_id=data.account_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to refresh scores: {e}") from e
