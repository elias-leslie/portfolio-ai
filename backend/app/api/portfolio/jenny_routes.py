"""Jenny operator routes for Portfolio Coach."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.jenny_operator_service import JennyOperatorService

from .models import (
    JennyDashboardResponse,
    JennyNotificationResponse,
    JennyRunRequest,
    JennyRunResponseModel,
)

router = APIRouter()
service = JennyOperatorService()


@router.get("/jenny", response_model=JennyDashboardResponse)
async def get_jenny_dashboard() -> JennyDashboardResponse:
    """Return Jenny's latest operator dashboard."""
    return JennyDashboardResponse.model_validate(service.get_dashboard().model_dump())


@router.post("/jenny/run", response_model=JennyRunResponseModel)
async def run_jenny_routine(payload: JennyRunRequest) -> JennyRunResponseModel:
    """Run a Jenny routine on demand."""
    if payload.routine_type == "weekly_learning":
        result = service.run_weekly_learning(triggered_by="manual")
    else:
        result = service.run_daily_operator(triggered_by="manual")
    return JennyRunResponseModel.model_validate(result.model_dump())


@router.post("/jenny/notifications/{notification_id}/acknowledge", response_model=JennyNotificationResponse)
async def acknowledge_jenny_notification(notification_id: str) -> JennyNotificationResponse:
    """Acknowledge an open Jenny notification."""
    notification = service.acknowledge_notification(notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return JennyNotificationResponse.model_validate(notification.model_dump())
