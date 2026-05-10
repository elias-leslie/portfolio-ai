"""Forward-catalyst calendar router (F4).

Thin serializer over :class:`CatalystCalendarService`. Owns no
analytics — every request resolves the singleton service and returns
its contracts unchanged. Token-saving defaults (limit=20, compact
projection) are enforced at the response shaping step, not in the
service.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any

from fastapi import APIRouter, Query
from starlette.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.portfolio.contracts.catalysts import (
    Catalyst,
    CatalystCalendarResponse,
    CatalystKind,
)
from app.services.catalyst_calendar_service import (
    DEFAULT_DAYS,
    DEFAULT_KINDS,
    DEFAULT_LIMIT,
    MAX_DAYS,
    MAX_LIMIT,
    CatalystCalendarService,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/catalysts", tags=["catalysts"])


@lru_cache(maxsize=1)
def _storage() -> Any:
    return import_module("app.storage").get_storage()


@lru_cache(maxsize=1)
def _service() -> CatalystCalendarService:
    return CatalystCalendarService(_storage())


def _parse_kinds(raw: str | None) -> tuple[CatalystKind, ...]:
    if not raw:
        return DEFAULT_KINDS
    out: list[CatalystKind] = []
    for chunk in raw.split(","):
        token = chunk.strip().lower()
        if token in DEFAULT_KINDS and token not in out:
            out.append(token)
    return tuple(out) if out else DEFAULT_KINDS


@router.get("/upcoming", response_model=None)
async def get_upcoming(
    days: int = Query(DEFAULT_DAYS, ge=1, le=MAX_DAYS),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    kinds: str | None = Query(None, description="Comma-separated subset of earnings,ex_dividend,fomc"),
    include_watchlist: bool = Query(True),
    detail: bool = Query(False, description="Include time_of_day, confirmed, source"),
    symbols: str | None = Query(None, description="Comma-separated symbols; defaults to portfolio + watchlist"),
) -> dict[str, Any]:
    """List upcoming catalysts within ``days`` days, sorted by date asc.

    Default response is the compact 4-field projection per the F4
    plan: ``{symbol, kind, date, days_until}``. Setting ``detail=true``
    expands every row with ``time_of_day``, ``confirmed``, ``source``.
    """
    service = _service()
    kinds_tuple = _parse_kinds(kinds)
    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols is not None
        else None
    )
    catalysts: list[Catalyst] = await run_in_threadpool(
        service.upcoming,
        symbol_list,
        days,
        limit,
        kinds_tuple,
        include_watchlist=include_watchlist,
    )
    response = CatalystCalendarResponse(
        days=days,
        limit=limit,
        kinds=kinds_tuple,
        include_watchlist=include_watchlist,
        catalysts=tuple(catalysts),
    )
    if detail:
        return response.model_dump(mode="json")
    return response.to_minimal_payload()
