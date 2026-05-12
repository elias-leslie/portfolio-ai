"""Home dashboard API routes."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.api.symbols.models import DecisionSection
from app.middleware.cache import cache_response

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


router = APIRouter(prefix="/api/home", tags=["home"])


@lru_cache(maxsize=1)
def _home_action_service() -> HomeActionService:
    return import_module("app.services.home_action_service").HomeActionService()


@lru_cache(maxsize=1)
def _automation_center_service() -> AutomationCenterService:
    return import_module("app.services.automation_center_service").AutomationCenterService()


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
