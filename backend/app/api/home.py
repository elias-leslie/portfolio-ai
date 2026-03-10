"""Home dashboard API routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.services.home_action_service import HomeActionService


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


class HomeActionQueueResponse(BaseModel):
    generated_at: str
    actions: list[HomeActionItemResponse] = Field(default_factory=list)
    summary: str


router = APIRouter(prefix="/api/home", tags=["home"])
service = HomeActionService()


@router.get("/action-queue", response_model=HomeActionQueueResponse)
async def get_home_action_queue() -> HomeActionQueueResponse:
    """Return the ranked cross-product action queue for the home page."""
    payload = await run_in_threadpool(service.get_action_queue)
    return HomeActionQueueResponse.model_validate(payload)
