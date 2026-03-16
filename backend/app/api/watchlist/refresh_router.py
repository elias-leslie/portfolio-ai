"""Watchlist refresh operations router."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from app.api.utils import handle_api_errors
from app.logging_config import get_logger
from app.storage import get_storage
from app.watchlist._service.helpers import safe_json_loads
from app.watchlist.background_tasks import schedule_refresh_tasks
from app.watchlist.response_builders import (
    FailedTickerInfo,
    RefreshRequest,
    RefreshResponse,
    RefreshStatusResponse,
)
from app.watchlist.scoring_service import (
    get_redis_client as _get_redis_client,
)
from app.watchlist.scoring_service import (
    refresh_watchlist_scores as refresh_watchlist_scores_service,
)
from app.watchlist.watchlist_repository import WatchlistRepository

from .helpers import (
    REDIS_WATCHLIST_REFRESH_KEY,
    _build_not_refreshing_response,
    _build_refresh_response,
)

logger = get_logger(__name__)

router = APIRouter()

_state: dict[str, WatchlistRepository] = {}


def _get_watchlist_repo() -> WatchlistRepository:
    """Lazy singleton to avoid DB connection at import time."""
    if "repo" not in _state:
        _state["repo"] = WatchlistRepository(get_storage())
    return _state["repo"]


def _is_live_watchlist_symbol(symbol: str) -> bool:
    """Exclude leaked test fixtures from live refresh operations."""
    return not symbol.upper().startswith("ZZTEST")


@router.get("/refresh-status", response_model=RefreshStatusResponse)
async def get_refresh_status() -> RefreshStatusResponse:
    """
    Get the current refresh status for the watchlist.

    Returns:
        Refresh status with progress information
    """
    try:
        redis_client = _get_redis_client()
        status_json = redis_client.get(REDIS_WATCHLIST_REFRESH_KEY)

        if not status_json:
            # No refresh in progress
            return _build_not_refreshing_response()

        status_data = safe_json_loads(str(status_json), {})
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
        logger.error("get_refresh_status_failed", error=str(e), exc_info=True)
        # Return no refresh in progress on error
        return _build_not_refreshing_response()


@router.get("/refresh")
async def get_refresh_endpoint() -> None:
    """Reject GET requests so /refresh does not fall through to /{item_id}."""
    raise HTTPException(
        status_code=405,
        detail="Use POST /api/watchlist/refresh to trigger a refresh or GET /api/watchlist/refresh-status for progress",
    )


@router.post("/refresh", response_model=RefreshResponse)
@handle_api_errors("refresh watchlist scores")
async def refresh_watchlist_scores(data: RefreshRequest) -> RefreshResponse:
    """
    Manually trigger a refresh of all watchlist scores.

    Args:
        data: Refresh request data (no fields needed)

    Returns:
        Refresh status (200 OK for all success, 207 Multi-Status for partial success)
    """
    logger.info("Refresh request started")

    # Get all watchlist items
    items_df = _get_watchlist_repo().get_all_symbols()

    if items_df.is_empty():
        return RefreshResponse(
            status="success",
            message="No items in watchlist",
            refreshed_count=0,
            failed_count=0,
            failed=[],
        )

    items = [
        item
        for item in items_df.to_dicts()
        if isinstance(item.get("symbol"), str) and _is_live_watchlist_symbol(item["symbol"])
    ]

    if not items:
        return RefreshResponse(
            status="success",
            message="No items in watchlist",
            refreshed_count=0,
            failed_count=0,
            failed=[],
        )

    symbols = [item["symbol"] for item in items]
    logger.info("Refreshing symbols", symbols=symbols, count=len(symbols))

    # Trigger background data refresh for ALL symbols
    schedule_refresh_tasks(symbols)

    # Do immediate synchronous refresh with Redis progress tracking
    result = refresh_watchlist_scores_service(get_storage())
    success_count = result.get("success_count", 0)
    failed_count = result.get("failed_count", 0)
    failed_list = [FailedTickerInfo(**f) for f in result.get("failed", [])]

    logger.info(
        "Watchlist refresh completed",
        success_count=success_count,
        failed_count=failed_count,
    )

    # Build response using helper
    status_code, response_data = _build_refresh_response(
        success_count=success_count,
        failed_count=failed_count,
        total_count=len(items),
        failed_list=failed_list,
    )

    # Return with appropriate status code
    if status_code == 200:
        return RefreshResponse(**response_data)

    # 207 Multi-Status for partial success
    return JSONResponse(status_code=status_code, content=response_data)  # type: ignore[return-value]
