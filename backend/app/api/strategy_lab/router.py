from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.logging_config import get_logger
from app.middleware.cache import cache_response

from .models import (
    StrategyLabDecisionRequest,
    StrategyLabDecisionResponse,
    StrategyLabDetailResponse,
    StrategyLabListResponse,
)
from .review import REVIEW_UNAVAILABLE_MESSAGE, STALE_QUOTE_MESSAGE, run_review
from .service import (
    get_strategy_lab_detail,
    list_strategy_lab,
    record_strategy_lab_decision,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/strategy-lab", tags=["strategy-lab"])


@router.get("", response_model=StrategyLabListResponse)
@cache_response(ttl=120)
async def get_strategy_lab(request: Request) -> StrategyLabListResponse:
    del request
    return await run_in_threadpool(list_strategy_lab)


@router.get("/{symbol}", response_model=StrategyLabDetailResponse)
@cache_response(ttl=120)
async def get_strategy_lab_symbol(request: Request, symbol: str) -> StrategyLabDetailResponse:
    del request
    return await run_in_threadpool(get_strategy_lab_detail, symbol)


@router.post("/{symbol}/review")
async def review_strategy_lab_symbol(symbol: str):
    detail = await run_in_threadpool(get_strategy_lab_detail, symbol)
    if detail.review.message == STALE_QUOTE_MESSAGE:
        return JSONResponse(
            status_code=409,
            content={"status": "stale_quote", "message": "Quote is stale. Refresh market data before acting."},
        )
    if not detail.review.available:
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "message": detail.review.message or REVIEW_UNAVAILABLE_MESSAGE},
        )
    try:
        review = await run_in_threadpool(run_review, detail)
    except TimeoutError:
        return JSONResponse(status_code=504, content={"status": "timeout", "message": "Review timed out."})
    except Exception as exc:
        logger.warning("strategy_lab_review_unavailable", symbol=symbol.upper(), error=str(exc))
        return JSONResponse(status_code=503, content={"status": "unavailable", "message": REVIEW_UNAVAILABLE_MESSAGE})
    return review.model_dump(mode="json")


@router.post("/{symbol}/decision", response_model=StrategyLabDecisionResponse)
async def post_strategy_lab_decision(
    symbol: str,
    payload: StrategyLabDecisionRequest,
) -> StrategyLabDecisionResponse:
    result = await run_in_threadpool(
        record_strategy_lab_decision,
        symbol,
        payload.action,
        payload.note,
    )
    return StrategyLabDecisionResponse.model_validate(result)
