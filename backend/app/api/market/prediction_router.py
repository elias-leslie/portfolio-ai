"""Market prediction API endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from app.constants import CACHE_TTL_SHORT
from app.logging_config import get_logger
from app.middleware.cache import cache_response, invalidate_endpoint_cache
from app.models.market_prediction import (
    MarketPredictionCommitteeResponse,
    MarketPredictionHistoryResponse,
    MarketPredictionSeatReviewResponse,
)
from app.services.market_prediction_cluster_weighting_service import (
    MarketPredictionClusterWeightingService,
)
from app.services.market_prediction_committee_service import (
    SUPPORTED_PREDICTION_WINDOWS,
    MarketPredictionCommitteeService,
)
from app.services.market_prediction_evaluation_service import MarketPredictionEvaluationService
from app.services.market_prediction_seat_weighting_service import (
    MarketPredictionSeatWeightingService,
)
from app.tasks.market_data.macro_calendar_pipeline import ingest_macro_calendar_events
from app.tasks.market_data.options_pipeline import fetch_options_activity_metrics

router = APIRouter()
logger = get_logger(__name__)

_state: dict[str, object] = {}


def _get_prediction_service() -> MarketPredictionCommitteeService:
    if "service" not in _state:
        _state["service"] = MarketPredictionCommitteeService()
    return _state["service"]  # type: ignore[return-value]


def _get_review_service() -> MarketPredictionSeatWeightingService:
    if "review_service" not in _state:
        _state["review_service"] = MarketPredictionSeatWeightingService()
    return _state["review_service"]  # type: ignore[return-value]


def _get_evaluation_service() -> MarketPredictionEvaluationService:
    if "evaluation_service" not in _state:
        _state["evaluation_service"] = MarketPredictionEvaluationService()
    return _state["evaluation_service"]  # type: ignore[return-value]


def _get_cluster_review_service() -> MarketPredictionClusterWeightingService:
    if "cluster_review_service" not in _state:
        _state["cluster_review_service"] = MarketPredictionClusterWeightingService()
    return _state["cluster_review_service"]  # type: ignore[return-value]


def _validate_window_days(window_days: int) -> int:
    if window_days not in SUPPORTED_PREDICTION_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported window_days={window_days}. Supported values: {', '.join(str(v) for v in SUPPORTED_PREDICTION_WINDOWS)}",
        )
    return window_days


def _invalidate_prediction_caches() -> None:
    invalidate_endpoint_cache("/api/market/prediction/committee", method="GET")
    invalidate_endpoint_cache("/api/market/prediction/committee/history", method="GET")
    invalidate_endpoint_cache("/api/market/prediction/review", method="GET")


@router.get("/prediction/committee", response_model=MarketPredictionCommitteeResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_prediction_committee(
    request: Request,
    window_days: int = Query(3, description="Trading-day forecast window"),
) -> MarketPredictionCommitteeResponse:
    service = _get_prediction_service()
    snapshot = service.get_committee_snapshot(
        window_days=_validate_window_days(window_days),
        generate_if_missing=False,
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No committee snapshot available")
    return snapshot


@router.post("/prediction/committee/refresh", response_model=MarketPredictionCommitteeResponse)
async def refresh_prediction_committee(
    request: Request,
    window_days: int = Query(3, description="Trading-day forecast window"),
) -> MarketPredictionCommitteeResponse:
    service = _get_prediction_service()
    evaluation_service = _get_evaluation_service()
    review_service = _get_review_service()
    cluster_service = _get_cluster_review_service()
    validated_window = _validate_window_days(window_days)
    as_of_ts = datetime.now(UTC)
    _invalidate_prediction_caches()
    try:
        await run_in_threadpool(ingest_macro_calendar_events, horizon_days=45)
    except Exception as exc:
        logger.warning("macro_calendar_ingestion_for_refresh_failed", error=str(exc), exc_info=True)
    try:
        await run_in_threadpool(fetch_options_activity_metrics)
    except Exception as exc:
        logger.warning("options_activity_ingestion_for_refresh_failed", error=str(exc), exc_info=True)
    await run_in_threadpool(evaluation_service.evaluate_due_predictions, as_of_date=as_of_ts.date())
    await run_in_threadpool(
        evaluation_service.backfill_vote_evaluations,
        window_days=validated_window,
        as_of_ts=as_of_ts,
    )
    source_snapshot = await run_in_threadpool(service.build_source_snapshot, as_of_ts)
    review = await run_in_threadpool(
        review_service.resolve_and_persist_review,
        window_days=validated_window,
        as_of_ts=as_of_ts,
    )
    cluster_review = await run_in_threadpool(
        cluster_service.resolve_and_persist_review,
        window_days=validated_window,
        as_of_ts=as_of_ts,
        source_snapshot=source_snapshot,
    )
    snapshot = await run_in_threadpool(
        service.generate_snapshot,
        window_days=validated_window,
        as_of_ts=as_of_ts,
        review=review,
        cluster_review=cluster_review,
        source_snapshot=source_snapshot,
    )
    _invalidate_prediction_caches()
    return snapshot


@router.get("/prediction/review", response_model=MarketPredictionSeatReviewResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_prediction_review(
    request: Request,
    window_days: int = Query(3, description="Trading-day forecast window"),
) -> MarketPredictionSeatReviewResponse:
    validated_window = _validate_window_days(window_days)
    service = _get_review_service()
    cluster_service = _get_cluster_review_service()
    seat_review = service.get_review(window_days=validated_window)
    cluster_review = cluster_service.get_review(
        window_days=validated_window,
        as_of_ts=seat_review.as_of_ts,
    )
    summary = _merge_review_summary(
        seat_review.review_summary,
        cluster_review.review_summary,
    )
    return seat_review.model_copy(
        update={
            "cluster_scorecards": cluster_review.cluster_scorecards,
            "cluster_review_state": cluster_review.review_state,
            "cluster_as_of_ts": cluster_review.as_of_ts,
            "review_summary": summary,
        }
    )


def _merge_review_summary(seat_summary: object, cluster_summary: object) -> dict[str, object]:
    seat = seat_summary if isinstance(seat_summary, dict) else {}
    cluster = cluster_summary if isinstance(cluster_summary, dict) else {}
    return {
        "generated_at": seat.get("generated_at") or cluster.get("generated_at"),
        "review_state": seat.get("review_state") or cluster.get("review_state") or "warmup",
        "drift_callouts": _merge_string_lists(seat.get("drift_callouts"), cluster.get("drift_callouts")),
        "gap_callouts": _merge_string_lists(seat.get("gap_callouts"), cluster.get("gap_callouts")),
        "agent_actions": _merge_string_lists(seat.get("agent_actions"), cluster.get("agent_actions")),
        "top_upweighted": _merge_object_lists(seat.get("top_upweighted"), cluster.get("top_upweighted")),
        "top_downweighted": _merge_object_lists(seat.get("top_downweighted"), cluster.get("top_downweighted")),
    }


def _merge_string_lists(*values: object) -> list[str]:
    merged: list[str] = []
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            text = str(item).strip()
            if text and text not in merged:
                merged.append(text)
    return merged


def _merge_object_lists(*values: object) -> list[object]:
    merged: list[object] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            key = str(item)
            if key not in seen:
                seen.add(key)
                merged.append(item)
    return merged


@router.get("/prediction/committee/history", response_model=MarketPredictionHistoryResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_prediction_committee_history(
    request: Request,
    symbol: str = Query(..., min_length=1, description="Target symbol"),
    window_days: int = Query(3, description="Trading-day forecast window"),
    limit: int = Query(30, ge=1, le=100, description="Max history rows"),
) -> MarketPredictionHistoryResponse:
    service = _get_prediction_service()
    normalized_symbol = symbol.strip().upper()
    items = service.get_history(
        symbol=normalized_symbol,
        window_days=_validate_window_days(window_days),
        limit=limit,
    )
    return MarketPredictionHistoryResponse(
        symbol=normalized_symbol,
        window_days=window_days,
        items=items,
    )
