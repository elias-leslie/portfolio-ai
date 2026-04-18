from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.logging_config import get_logger

from .models import StrategyLabDetailResponse, StrategyLabListResponse
from .review import REVIEW_UNAVAILABLE_MESSAGE, STALE_QUOTE_MESSAGE, run_review
from .service import get_strategy_lab_detail, list_strategy_lab

logger = get_logger(__name__)
router = APIRouter(prefix="/api/strategy-lab", tags=["strategy-lab"])


@router.get("", response_model=StrategyLabListResponse)
async def get_strategy_lab() -> StrategyLabListResponse:
    return await run_in_threadpool(list_strategy_lab)


@router.get("/{symbol}", response_model=StrategyLabDetailResponse)
async def get_strategy_lab_symbol(symbol: str) -> StrategyLabDetailResponse:
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
