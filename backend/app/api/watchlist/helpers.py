"""Watchlist API helper functions."""

from __future__ import annotations

import json

from app.agents.multi_reviewer import DualReviewResult, ProviderReview
from app.api.utils import require_nonempty_df
from app.logging_config import get_logger
from app.utils.db_helpers import generate_uuid
from app.utils.formatters import utc_now_iso
from app.watchlist._service.helpers import parse_json_field
from app.watchlist.response_builders import (
    FailedTickerInfo,
    RefreshResponse,
    RefreshStatusResponse,
)
from app.watchlist.watchlist_repository import WatchlistRepository

logger = get_logger(__name__)

# Watchlist constants
DAILY_REPORT_STALE_HOURS = 48  # Consider daily report stale after 48 hours
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
    from fastapi import HTTPException

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
    watchlist_repo: WatchlistRepository,
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
        created_at=utc_now_iso(),
        pair_id=pair_id,
        severity=severity,
        agreement=agreement,
        provider_disagreement=provider_disagreement,
    )
    return review_id


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


def _build_signal_data_from_snapshot(
    snapshot_row: dict[str, object], symbol: str
) -> dict[str, object]:
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
    watchlist_repo: WatchlistRepository,
    review_result: dict[str, object],
    item_id: str,
    snapshot_id: str | None,
) -> str:
    """Store a legacy single-provider review in the database.

    Args:
        watchlist_repo: Repository instance
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
        disagreement=bool(review_result["disagreement"])
        if review_result.get("disagreement")
        else None,
        token_usage_json=json.dumps(review_result["usage"]),
        created_at=utc_now_iso(),
    )
    return review_id


async def _handle_dual_review(
    watchlist_repo: WatchlistRepository,
    multi_reviewer,
    signal_data: dict[str, object],
    item_id: str,
    snapshot_id: str | None,
) -> dict:
    """Handle dual-provider review flow (both Gemini and Claude).

    Args:
        watchlist_repo: Repository instance
        multi_reviewer: MultiReviewer instance
        signal_data: Signal data dict for LLM review
        item_id: Watchlist item ID
        snapshot_id: Snapshot ID

    Returns:
        Dual review response dict with both provider results
    """
    dual_result: DualReviewResult = await multi_reviewer.review_signal_dual(signal_data)

    # Store both reviews
    for review in [dual_result.gemini_review, dual_result.claude_review]:
        if review and not review.error:
            _store_strategy_review(
                watchlist_repo=watchlist_repo,
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


async def _handle_legacy_review(
    watchlist_repo: WatchlistRepository,
    strategy_reviewer,
    signal_data: dict[str, object],
    item_id: str,
    snapshot_id: str | None,
) -> dict:
    """Handle legacy single-provider review flow.

    Args:
        watchlist_repo: Repository instance
        strategy_reviewer: StrategyReviewer instance
        signal_data: Signal data dict for LLM review
        item_id: Watchlist item ID
        snapshot_id: Snapshot ID

    Returns:
        Legacy review response dict
    """
    review_result = await strategy_reviewer.review_signal(signal_data)

    # Store review
    _store_legacy_review(watchlist_repo, review_result, item_id, snapshot_id)

    logger.info(
        f"Strategy review logged for {review_result['symbol']}",
        extra={
            "symbol": review_result["symbol"],
            "provider": review_result["provider"],
            "disagreement": review_result["disagreement"],
        },
    )

    return review_result
