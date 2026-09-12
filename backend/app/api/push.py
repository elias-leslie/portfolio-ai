"""Push subscription API (plan §7 3.6).

Mounted at ``/api/household/push``. Registration is per device: the browser
subscribes, names whose phone it is, and posts the result here. The VAPID
private key never crosses this boundary — only the public key, which is not a
secret and is exactly what the browser needs to subscribe at all.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.models.push_alerts import (
    PushConfig,
    PushDelivery,
    PushSubscriptionInput,
    PushSubscriptionList,
    PushSubscriptionView,
    PushTestRequest,
)
from app.services.household_identity import request_identity

if TYPE_CHECKING:
    from app.services.push_service import PushService

router = APIRouter(prefix="/api/household/push", tags=["push"])


@lru_cache(maxsize=1)
def _service() -> PushService:
    return import_module("app.services.push_service").PushService()


@router.get("/config", response_model=PushConfig)
async def get_push_config() -> PushConfig:
    """The application server key, plus whether push is configured at all."""
    return await run_in_threadpool(_service().config)


@router.get("/subscriptions", response_model=PushSubscriptionList)
async def list_push_subscriptions(request: Request) -> PushSubscriptionList:
    service = _service()
    config = await run_in_threadpool(service.config)
    recipients = await run_in_threadpool(service.recipients)
    subscriptions = await run_in_threadpool(service.list_subscriptions)
    identity = request_identity(request)
    if identity.member_id:
        recipients = [r for r in recipients if r.id == identity.member_id]
        subscriptions = [s for s in subscriptions if s.household_member_id == identity.member_id]
    return PushSubscriptionList(
        enabled=config.enabled,
        public_key=config.public_key,
        recipients=recipients,
        subscriptions=subscriptions,
    )


@router.post("/subscriptions", response_model=PushSubscriptionView)
async def register_push_subscription(
    request: Request,
    payload: PushSubscriptionInput,
) -> PushSubscriptionView:
    if not payload.endpoint.strip():
        raise HTTPException(status_code=422, detail="endpoint is required")
    identity = request_identity(request)
    if identity.member_id:
        payload = payload.model_copy(update={"household_member_id": identity.member_id})
    try:
        return await run_in_threadpool(
            _service().register, payload, enforce_owner=bool(identity.member_id)
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.delete("/subscriptions/{subscription_id}")
async def delete_push_subscription(request: Request, subscription_id: str) -> dict[str, bool]:
    removed = await run_in_threadpool(
        _service().unregister, subscription_id, member_id=request_identity(request).member_id
    )
    if not removed:
        raise HTTPException(status_code=404, detail="subscription not found")
    return {"removed": True}


@router.post("/unsubscribe")
async def unsubscribe_push_endpoint(request: Request, payload: dict[str, str]) -> dict[str, bool]:
    """Turn alerts off from the device that holds the endpoint.

    A phone revoking its own permission knows its endpoint but not the row id,
    so it gets a route keyed on what it has.
    """
    endpoint = (payload.get("endpoint") or "").strip()
    if not endpoint:
        raise HTTPException(status_code=422, detail="endpoint is required")
    removed = await run_in_threadpool(
        _service().unregister_endpoint, endpoint, member_id=request_identity(request).member_id
    )
    return {"removed": removed}


@router.post("/test", response_model=PushDelivery)
async def send_test_push(request: Request, payload: PushTestRequest) -> PushDelivery:
    """Prove the round trip on a real device before an alert depends on it."""
    service = _service()
    identity = request_identity(request)
    if not service.is_configured():
        raise HTTPException(status_code=503, detail="push is not configured")
    return await run_in_threadpool(
        lambda: service.send(
            title="Portfolio AI alerts are on",
            body="This phone will get budget alerts. Tap to open the plan.",
            severity="info",
            tag="push-test",
            subscription_id=payload.subscription_id,
            household_member_ids=[identity.member_id] if identity.member_id else None,
        )
    )
