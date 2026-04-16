"""Home dashboard API routes."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.api.symbols.models import DecisionSection

if TYPE_CHECKING:
    from app.services.automation_center_service import AutomationCenterService
    from app.services.home_action_service import HomeActionService
    from app.services.home_today_brief_service import HomeTodayBriefService


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


class HomeTodayBriefAsOfResponse(BaseModel):
    household: str | None = None
    portfolio: str | None = None
    market: str | None = None
    news: str | None = None


class HomeTodayBriefBlockResponse(BaseModel):
    headline: str
    summary: str
    stance: str
    confidence: str
    why_now: str
    bullets: list[str] = Field(default_factory=list)


class HomeTodayBriefCatalystResponse(BaseModel):
    id: str
    title: str
    direction: str
    market_effect: str
    portfolio_effect: str
    money_effect: str
    source_ids: list[str] = Field(default_factory=list)


class HomeTodayBriefImpactResponse(BaseModel):
    label: str
    direction: str
    magnitude: str
    rationale: str
    affected_symbols: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)


class HomeTodayBriefMetricResponse(BaseModel):
    key: str
    label: str
    value: str
    change_pct: float | None = None
    detail: str
    tone: str


class HomeTodayBriefSourceResponse(BaseModel):
    id: str
    kind: str
    label: str
    published_at: str | None = None
    url: str | None = None
    source_signal_tier: str | None = None
    decision_value_score: float | None = None


class HomeTodayBriefResponse(BaseModel):
    generated_at: str
    cache_ttl_seconds: int
    as_of: HomeTodayBriefAsOfResponse
    market_status: str
    brief: HomeTodayBriefBlockResponse
    catalysts: list[HomeTodayBriefCatalystResponse] = Field(default_factory=list)
    impacts: list[HomeTodayBriefImpactResponse] = Field(default_factory=list)
    market_metrics: list[HomeTodayBriefMetricResponse] = Field(default_factory=list)
    sources: list[HomeTodayBriefSourceResponse] = Field(default_factory=list)
    staleness_notes: list[str] = Field(default_factory=list)


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


router = APIRouter(prefix="/api/home", tags=["home"])


@lru_cache(maxsize=1)
def _home_action_service() -> HomeActionService:
    return import_module("app.services.home_action_service").HomeActionService()


@lru_cache(maxsize=1)
def _automation_center_service() -> AutomationCenterService:
    return import_module("app.services.automation_center_service").AutomationCenterService()


@lru_cache(maxsize=1)
def _home_today_brief_service() -> HomeTodayBriefService:
    return import_module("app.services.home_today_brief_service").HomeTodayBriefService()


@router.get("/action-queue", response_model=HomeActionQueueResponse)
async def get_home_action_queue() -> HomeActionQueueResponse:
    """Return the ranked cross-product action queue for the home page."""
    payload = await run_in_threadpool(_home_action_service().get_action_queue)
    return HomeActionQueueResponse.model_validate(payload)


@router.get("/today-brief", response_model=HomeTodayBriefResponse)
async def get_home_today_brief(request: Request) -> HomeTodayBriefResponse:
    """Return catalyst, market-reaction, and personal-impact brief for Today."""
    del request
    payload = await run_in_threadpool(_home_today_brief_service().get_today_brief)
    return HomeTodayBriefResponse.model_validate(payload)


@router.get("/automation-center", response_model=AutomationCenterResponse)
async def get_home_automation_center() -> AutomationCenterResponse:
    """Return current automation guardrails and recent runs."""
    payload = await run_in_threadpool(_automation_center_service().get_center)
    return AutomationCenterResponse.model_validate(payload)
