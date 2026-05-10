"""Strategy catalog router.

Read-only catalog list plus follow/unfollow. The catalog itself is keyed by
symbol; following promotes the screened metadata into a strategy_definitions
row that the existing daily_signals_wf picks up.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.middleware.cache import cache_response

from .models import CatalogResponse, FollowResponse
from .service import follow_symbol, list_catalog, unfollow_symbol

logger = get_logger(__name__)
router = APIRouter(prefix="/api/strategy-catalog", tags=["strategy-catalog"])


@router.get("", response_model=CatalogResponse)
@cache_response(ttl=60)
async def get_catalog(
    limit: int = Query(default=50, ge=1, le=200),
    only_significant: bool = Query(default=False),
    min_total_trades: int = Query(default=0, ge=0),
) -> CatalogResponse:
    return await run_in_threadpool(
        list_catalog,
        limit=limit,
        only_significant=only_significant,
        min_total_trades=min_total_trades,
    )


@router.post("/{symbol}/follow", response_model=FollowResponse)
async def follow_catalog_symbol(symbol: str) -> FollowResponse:
    return await run_in_threadpool(follow_symbol, symbol)


@router.delete("/{symbol}/follow", response_model=FollowResponse)
async def unfollow_catalog_symbol(symbol: str) -> FollowResponse:
    return await run_in_threadpool(unfollow_symbol, symbol)
