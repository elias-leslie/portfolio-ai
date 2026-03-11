"""Jenny operator routes for Portfolio Coach."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from .models import (
    JennyChatRequest,
    JennyChatResponseModel,
    JennyDashboardResponse,
    JennyNotificationResponse,
    JennyRunRequest,
    JennyRunResponseModel,
)

if TYPE_CHECKING:
    from app.services.jenny_conversation_service import JennyConversationService
    from app.services.jenny_operator_service import JennyOperatorService

router = APIRouter()


@lru_cache(maxsize=1)
def _service() -> JennyOperatorService:
    return import_module("app.services.jenny_operator_service").JennyOperatorService()


@lru_cache(maxsize=1)
def _conversation_service() -> JennyConversationService:
    return import_module("app.services.jenny_conversation_service").JennyConversationService()


def _get_jenny_dashboard_payload() -> JennyDashboardResponse:
    return JennyDashboardResponse.model_validate(_service().get_dashboard().model_dump())


def _run_jenny_routine_payload(payload: JennyRunRequest) -> JennyRunResponseModel:
    service = _service()
    if payload.routine_type == "weekly_learning":
        result = service.run_weekly_learning(triggered_by="manual")
    elif payload.routine_type == "daily_operator":
        result = service.run_daily_operator(triggered_by="manual")
    else:
        raise HTTPException(status_code=400, detail=f"Unknown routine_type: {payload.routine_type}")
    return JennyRunResponseModel.model_validate(result.model_dump())


def _acknowledge_jenny_notification_payload(notification_id: str) -> JennyNotificationResponse:
    notification = _service().acknowledge_notification(notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return JennyNotificationResponse.model_validate(notification.model_dump())


def _chat_with_jenny_payload(payload: JennyChatRequest) -> JennyChatResponseModel:
    response = _conversation_service().chat(payload.message, session_id=payload.session_id)
    return JennyChatResponseModel.model_validate(response)


@router.get("/jenny", response_model=JennyDashboardResponse)
async def get_jenny_dashboard() -> JennyDashboardResponse:
    """Return Jenny's latest operator dashboard."""
    return await run_in_threadpool(_get_jenny_dashboard_payload)


@router.post("/jenny/run", response_model=JennyRunResponseModel)
async def run_jenny_routine(payload: JennyRunRequest) -> JennyRunResponseModel:
    """Run a Jenny routine on demand."""
    return await run_in_threadpool(_run_jenny_routine_payload, payload)


@router.post("/jenny/notifications/{notification_id}/acknowledge", response_model=JennyNotificationResponse)
async def acknowledge_jenny_notification(notification_id: str) -> JennyNotificationResponse:
    """Acknowledge an open Jenny notification."""
    return await run_in_threadpool(_acknowledge_jenny_notification_payload, notification_id)


@router.post("/jenny/chat", response_model=JennyChatResponseModel)
async def chat_with_jenny(payload: JennyChatRequest) -> JennyChatResponseModel:
    """Chat with Jenny using portfolio-wide context."""
    return await run_in_threadpool(_chat_with_jenny_payload, payload)
