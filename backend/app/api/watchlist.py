"""Watchlist API router."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.agents.multi_reviewer import DualReviewResult, MultiReviewer, ProviderReview
from app.agents.strategy_reviewer import StrategyReviewer
from app.logging_config import get_logger
from app.middleware.cache import cache_response
from app.storage import get_storage
from app.utils.db_helpers import generate_uuid
from app.utils.formatters import utc_now_iso
from app.utils.watchlist_cache import invalidate_all_watchlist_caches
from app.watchlist._service.helpers import parse_json_field, safe_json_loads
from app.watchlist.background_tasks import schedule_new_symbol_tasks, schedule_refresh_tasks
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
from app.watchlist.watchlist_repository import WatchlistRepository
from app.watchlist.watchlist_service import WatchlistService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

# Initialize services
storage = get_storage()
watchlist_service = WatchlistService(storage)
watchlist_repo = WatchlistRepository(storage)
strategy_reviewer = StrategyReviewer(storage, primary_provider="gemini")
multi_reviewer = MultiReviewer(storage)


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


def _review_to_dict(review: ProviderReview | None) -> dict[str, object] | None:
    """Convert a ProviderReview to a dictionary for JSON response."""
    if review is None:
        return None
    return {
        "provider": review.provider,
        "review_text": review.review_text,
        "is_valid": review.is_valid,
        "disagreement": review.disagreement,
        "usage": review.usage,
        "error": review.error,
    }


def _store_strategy_review(
    item_id: str,
    snapshot_id: str | None,
    symbol: str,
    review: ProviderReview,
    pair_id: str | None = None,
    severity: str | None = None,
    agreement: float | None = None,
    provider_disagreement: bool | None = None,
) -> str:
    """Store a strategy review in the database."""
    review_id = generate_uuid()
    watchlist_repo.store_strategy_review(
        review_id=review_id,
        item_id=item_id,
        snapshot_id=snapshot_id,
        symbol=symbol,
        review_text=review.review_text,
        provider=review.provider,
        is_valid=review.is_valid,
        disagreement=review.disagreement,
        token_usage_json=json.dumps(review.usage),
        created_at=datetime.now(UTC),
        pair_id=pair_id,
        severity=severity,
        agreement=agreement,
        provider_disagreement=provider_disagreement,
    )
    return review_id


def _build_signal_data_from_snapshot(snapshot_row: dict[str, object], symbol: str) -> dict[str, object]:
    """Build signal data dict from a snapshot row for LLM review.

    Args:
        snapshot_row: Row from watchlist_snapshots_v
        symbol: Stock symbol

    Returns:
        Signal data dict with standardized fields for LLM review
    """
    return {
        "symbol": symbol,
        "signal_type": snapshot_row.get("signal_type"),
        "signal_strength": snapshot_row.get("signal_strength"),
        "recommended_style": snapshot_row.get("recommended_style"),
        "risk_level": snapshot_row.get("risk_level"),
        "rationale": snapshot_row.get("rationale"),
        "current_score": parse_json_field(snapshot_row.get("current_score")) or {},
        "news_sentiment_score": snapshot_row.get("news_sentiment_score"),
    }


def _store_legacy_review(
    review_result: dict[str, object],
    item_id: str,
    snapshot_id: str | None,
) -> str:
    """Store a legacy single-provider review in the database.

    Args:
        review_result: Review result from strategy_reviewer
        item_id: Watchlist item ID
        snapshot_id: Snapshot ID

    Returns:
        Generated review ID
    """
    review_id = generate_uuid()
    watchlist_repo.store_strategy_review(
        review_id=review_id,
        item_id=item_id,
        snapshot_id=snapshot_id,
        symbol=str(review_result["symbol"]),
        review_text=str(review_result["review"]),
        provider=str(review_result["provider"]),
        is_valid=bool(review_result["is_valid"]),
        disagreement=bool(review_result["disagreement"]) if review_result.get("disagreement") else None,
        token_usage_json=json.dumps(review_result["usage"]),
        created_at=datetime.now(UTC),
    )
    return review_id


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


@router.get("/daily-report")
async def get_daily_report() -> dict[str, object]:
    """
    Get the latest daily watchlist report.

    Returns:
        Latest report with symbols added, removed, and score changes
    """
    try:
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
        is_stale = (datetime.now(UTC) - generated_at).total_seconds() > 48 * 3600

        return {
            "report_date": report_row["report_date"].isoformat()
            if report_row["report_date"]
            else None,
            "generated_at": generated_at.isoformat() if generated_at else None,
            "symbols_added": symbols_added,
            "symbols_removed": symbols_removed,
            "score_changes": score_changes,
            "is_stale": is_stale,
        }

    except Exception as e:
        logger.error("Failed to get daily report", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to fetch daily report: {e}") from e


@router.post("", response_model=WatchlistItemResponse, status_code=201)
async def create_watchlist_item(data: WatchlistItemCreate) -> WatchlistItemResponse:
    """
    Add a symbol to the watchlist.

    Args:
        data: Watchlist item creation data

    Returns:
        Created watchlist item
    """
    try:
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
        logger.error("Failed to get refresh status", error=str(e))
        # Return no refresh in progress on error
        return _build_not_refreshing_response()


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
        items_df = watchlist_repo.get_item_by_id(item_id)

        if items_df.is_empty():
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        now = utc_now_iso()

        # Update note
        watchlist_repo.update_item_note(item_id, data.note, now)

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
        items_df = watchlist_repo.get_item_by_id(item_id)

        if items_df.is_empty():
            raise HTTPException(status_code=404, detail="Watchlist item not found")

        # Delete snapshots first (foreign key), then delete item
        watchlist_repo.delete_item(item_id)

        # Invalidate all watchlist caches (Redis symbols + HTTP response)
        invalidate_all_watchlist_caches()

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
        item_df = watchlist_repo.get_symbol_by_item_id(item_id)

        if item_df.is_empty():
            raise HTTPException(status_code=404, detail="Watchlist item not found")

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
        items_df = watchlist_repo.get_all_symbols()

        if items_df.is_empty():
            return RefreshResponse(
                status="success",
                message="No items in watchlist",
                refreshed_count=0,
                failed_count=0,
                failed=[],
            )

        items = items_df.to_dicts()
        symbols = [item["symbol"] for item in items]
        logger.info("Refreshing symbols", symbols=symbols, count=len(symbols))

        # Trigger background data refresh for ALL symbols
        schedule_refresh_tasks(symbols)

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


@router.post("/{item_id}/review")
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
    try:
        # Fetch watchlist item
        items_df = watchlist_repo.get_item_with_snapshots(item_id)

        if items_df.is_empty():
            raise HTTPException(status_code=404, detail=f"Watchlist item {item_id} not found")

        # Get latest snapshot
        snapshots_df = watchlist_repo.get_latest_snapshot_for_review(item_id)

        if snapshots_df.is_empty():
            raise HTTPException(
                status_code=404, detail=f"No snapshot found for item {item_id}. Run refresh first."
            )

        # Parse snapshot and build signal data using helper
        snapshot_row = snapshots_df.to_dicts()[0]
        symbol = str(items_df.to_dicts()[0]["symbol"])
        signal_data = _build_signal_data_from_snapshot(snapshot_row, symbol)

        if dual:
            # Get dual-provider LLM review (both Gemini and Claude)
            dual_result: DualReviewResult = await multi_reviewer.review_signal_dual(signal_data)

            # Store both reviews using module-level helper
            snapshot_id = snapshot_row.get("id")
            for review in [dual_result.gemini_review, dual_result.claude_review]:
                if review and not review.error:
                    _store_strategy_review(
                        item_id=item_id,
                        snapshot_id=snapshot_id,
                        symbol=dual_result.symbol,
                        review=review,
                        pair_id=dual_result.review_pair_id,
                        severity=dual_result.disagreement_severity.value,
                        agreement=dual_result.agreement_score,
                        provider_disagreement=dual_result.provider_disagreement,
                    )

            logger.info(
                f"Dual strategy review logged for {dual_result.symbol}",
                extra={
                    "symbol": dual_result.symbol,
                    "review_pair_id": dual_result.review_pair_id,
                    "agreement_score": dual_result.agreement_score,
                    "disagreement_severity": dual_result.disagreement_severity.value,
                    "provider_disagreement": dual_result.provider_disagreement,
                },
            )

            return {
                "symbol": dual_result.symbol,
                "review_pair_id": dual_result.review_pair_id,
                "gemini_review": _review_to_dict(dual_result.gemini_review),
                "claude_review": _review_to_dict(dual_result.claude_review),
                "agreement_score": dual_result.agreement_score,
                "disagreement_severity": dual_result.disagreement_severity.value,
                "provider_disagreement": dual_result.provider_disagreement,
                "consensus_summary": dual_result.consensus_summary,
            }

        # Legacy single-provider path
        review_result = await strategy_reviewer.review_signal(signal_data)

        # Log review to database using helper
        _store_legacy_review(review_result, item_id, snapshot_row.get("id"))

        logger.info(
            f"Strategy review logged for {review_result['symbol']}",
            extra={
                "symbol": review_result["symbol"],
                "provider": review_result["provider"],
                "disagreement": review_result["disagreement"],
            },
        )

        return review_result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to review signal for {item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Review failed: {e}") from e
