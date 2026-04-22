"""Market prediction API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from app.constants import CACHE_TTL_SHORT
from app.middleware.cache import cache_response
from app.models.market_prediction import (
    MarketPredictionCommitteeResponse,
    MarketPredictionHistoryResponse,
    MarketPredictionSeatReviewResponse,
)
from app.services.market_prediction_committee_service import (
    SUPPORTED_PREDICTION_WINDOWS,
    MarketPredictionCommitteeService,
)
from app.services.market_prediction_seat_weighting_service import (
    MarketPredictionSeatWeightingService,
)

router = APIRouter()

_state: dict[str, object] = {}


def _get_prediction_service() -> MarketPredictionCommitteeService:
    if "service" not in _state:
        _state["service"] = MarketPredictionCommitteeService()
    return _state["service"]  # type: ignore[return-value]


def _get_review_service() -> MarketPredictionSeatWeightingService:
    if "review_service" not in _state:
        _state["review_service"] = MarketPredictionSeatWeightingService()
    return _state["review_service"]  # type: ignore[return-value]


def _validate_window_days(window_days: int) -> int:
    if window_days not in SUPPORTED_PREDICTION_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported window_days={window_days}. Supported values: {', '.join(str(v) for v in SUPPORTED_PREDICTION_WINDOWS)}",
        )
    return window_days


@router.get("/prediction/committee", response_model=MarketPredictionCommitteeResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_prediction_committee(
    request: Request,
    window_days: int = Query(3, description="Trading-day forecast window"),
) -> MarketPredictionCommitteeResponse:
    service = _get_prediction_service()
    snapshot = service.get_committee_snapshot(window_days=_validate_window_days(window_days))
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No committee snapshot available")
    return snapshot


@router.get("/prediction/review", response_model=MarketPredictionSeatReviewResponse)
@cache_response(ttl=CACHE_TTL_SHORT)
async def get_prediction_review(
    request: Request,
    window_days: int = Query(3, description="Trading-day forecast window"),
) -> MarketPredictionSeatReviewResponse:
    service = _get_review_service()
    return service.get_review(window_days=_validate_window_days(window_days))


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
