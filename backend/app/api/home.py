"""Home dashboard API routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

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
service = HomeActionService()
automation_service = AutomationCenterService()


@router.get("/action-queue", response_model=HomeActionQueueResponse)
async def get_home_action_queue() -> HomeActionQueueResponse:
    """Return the ranked cross-product action queue for the home page."""
    payload = await run_in_threadpool(service.get_action_queue)
    return HomeActionQueueResponse.model_validate(payload)


@router.get("/automation-center", response_model=AutomationCenterResponse)
async def get_home_automation_center() -> AutomationCenterResponse:
    """Return current automation guardrails and recent runs."""
    payload = await run_in_threadpool(automation_service.get_center)
    return AutomationCenterResponse.model_validate(payload)
