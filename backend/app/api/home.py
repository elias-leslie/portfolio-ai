"""Home dashboard API routes."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.api.market._types import CORE_MARKET_SYMBOLS
from app.api.symbols.models import DecisionSection
from app.constants import SECTOR_ETFS
from app.macro_gate.service import run as run_macro_gate
from app.middleware.cache import (
    cache_response,
    invalidate_endpoint_cache,
    invalidate_market_data_cache,
)
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage

if TYPE_CHECKING:
    from app.services.automation_center_service import AutomationCenterService
    from app.services.home_action_service import HomeActionService


class HomeActionExecutionResponse(BaseModel):
    kind: str
    symbol: str | None = None
    notification_id: str | None = None
    stage: str | None = None


class HomeActionItemResponse(BaseModel):
    id: str
    source: str
    category: str
    priority: str
    title: str
    detail: str
    action_label: str
    href: str
    symbol: str | None = None
    badge: str | None = None
    decision: DecisionSection | None = None
    execution: HomeActionExecutionResponse | None = None


class HomeActionQueueResponse(BaseModel):
    generated_at: str
    actions: list[HomeActionItemResponse] = Field(default_factory=list)
    summary: str


class AutomationGuardrailResponse(BaseModel):
    key: str
    label: str
    value: str
    enabled: bool
    source: str
    detail: str


class AutomationRecentRunResponse(BaseModel):
    id: str
    label: str
    status: str
    triggered_by: str
    started_at: str
    completed_at: str | None = None
    detail: str


class AutomationCenterResponse(BaseModel):
    generated_at: str
    guardrails: list[AutomationGuardrailResponse] = Field(default_factory=list)
    recent_runs: list[AutomationRecentRunResponse] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TodayRefreshResponse(BaseModel):
    refreshed_at: str
    quote_symbols_requested: int
    quote_symbols_refreshed: int
    quote_symbols_failed: list[str] = Field(default_factory=list)
    macro_snapshot_date: str | None = None
    macro_deployment_score: float | None = None
    cache_entries_invalidated: int


router = APIRouter(prefix="/api/home", tags=["home"])


@lru_cache(maxsize=1)
def _home_action_service() -> HomeActionService:
    return import_module("app.services.home_action_service").HomeActionService()


@lru_cache(maxsize=1)
def _automation_center_service() -> AutomationCenterService:
    return import_module("app.services.automation_center_service").AutomationCenterService()


def _portfolio_symbols() -> list[str]:
    portfolio_mgr = import_module("app.portfolio.manager").PortfolioManager(get_storage())
    accounts = [
        account
        for account in portfolio_mgr.get_accounts()
        if getattr(account, "account_type", None) != "paper"
    ]
    account_ids = {str(account.id) for account in accounts}
    return sorted(
        {
            str(position.symbol).strip().upper()
            for position in portfolio_mgr.get_positions()
            if str(getattr(position, "account_id", "")) in account_ids
            and str(getattr(position, "symbol", "")).strip()
        }
    )


def _today_refresh_symbols() -> list[str]:
    symbols = [
        *CORE_MARKET_SYMBOLS,
        *SECTOR_ETFS.keys(),
        *_portfolio_symbols(),
    ]
    return list(dict.fromkeys(symbol.upper() for symbol in symbols if symbol))


def _invalidate_today_caches() -> int:
    _home_action_service().invalidate_cache()
    endpoints = [
        "/api/home/action-queue",
        "/api/household/dashboard",
        "/api/household/net-worth-trend",
        "/api/market/intelligence",
        "/api/market/conditions",
        "/api/market/indicator-history",
        "/api/market/fear-greed-history",
        "/api/market/sector-history",
        "/api/market/status",
        "/api/portfolio",
        "/api/portfolio/analytics",
    ]
    total = invalidate_market_data_cache()
    for endpoint in endpoints:
        total += invalidate_endpoint_cache(endpoint)
    return total


def _refresh_today_payload() -> TodayRefreshResponse:
    symbols = _today_refresh_symbols()
    quotes = PriceDataFetcher(get_storage()).fetch_price_data(symbols, force_refresh=True)
    failed = sorted(
        symbol
        for symbol in symbols
        if symbol not in quotes or quotes[symbol].error or quotes[symbol].price <= 0
    )
    macro = run_macro_gate(force_quote_refresh=True, current_quote_max_age_minutes=0)
    invalidated = _invalidate_today_caches()
    return TodayRefreshResponse(
        refreshed_at=datetime.now(UTC).isoformat(),
        quote_symbols_requested=len(symbols),
        quote_symbols_refreshed=len(symbols) - len(failed),
        quote_symbols_failed=failed,
        macro_snapshot_date=macro.snapshot_date.isoformat() if macro else None,
        macro_deployment_score=round(macro.deployment_score, 2) if macro else None,
        cache_entries_invalidated=invalidated,
    )


@router.get("/action-queue", response_model=HomeActionQueueResponse)
@cache_response(ttl=30)
async def get_home_action_queue(request: Request) -> HomeActionQueueResponse:
    """Return the ranked cross-product action queue for the home page."""
    del request
    payload = await run_in_threadpool(_home_action_service().get_action_queue)
    return HomeActionQueueResponse.model_validate(payload)


@router.get("/automation-center", response_model=AutomationCenterResponse)
async def get_home_automation_center() -> AutomationCenterResponse:
    """Return current automation guardrails and recent runs."""
    payload = await run_in_threadpool(_automation_center_service().get_center)
    return AutomationCenterResponse.model_validate(payload)


@router.post("/refresh-today", response_model=TodayRefreshResponse)
async def refresh_today() -> TodayRefreshResponse:
    """Force-refresh the current data surfaces used by the root Today page."""
    return await run_in_threadpool(_refresh_today_payload)
