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

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.models.push_alerts import (
    PushConfig,
    PushDelivery,
    PushSubscriptionInput,
    PushSubscriptionList,
    PushSubscriptionView,
    PushTestRequest,
)

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
async def list_push_subscriptions() -> PushSubscriptionList:
    service = _service()
    config = await run_in_threadpool(service.config)
    recipients = await run_in_threadpool(service.recipients)
    subscriptions = await run_in_threadpool(service.list_subscriptions)
    return PushSubscriptionList(
        enabled=config.enabled,
        public_key=config.public_key,
        recipients=recipients,
        subscriptions=subscriptions,
    )


@router.post("/subscriptions", response_model=PushSubscriptionView)
async def register_push_subscription(
    payload: PushSubscriptionInput,
) -> PushSubscriptionView:
    if not payload.endpoint.strip():
        raise HTTPException(status_code=422, detail="endpoint is required")
    return await run_in_threadpool(_service().register, payload)


@router.delete("/subscriptions/{subscription_id}")
async def delete_push_subscription(subscription_id: str) -> dict[str, bool]:
    removed = await run_in_threadpool(_service().unregister, subscription_id)
    if not removed:
        raise HTTPException(status_code=404, detail="subscription not found")
    return {"removed": True}


@router.post("/unsubscribe")
async def unsubscribe_push_endpoint(payload: dict[str, str]) -> dict[str, bool]:
    """Turn alerts off from the device that holds the endpoint.

    A phone revoking its own permission knows its endpoint but not the row id,
    so it gets a route keyed on what it has.
    """
    endpoint = (payload.get("endpoint") or "").strip()
    if not endpoint:
        raise HTTPException(status_code=422, detail="endpoint is required")
    removed = await run_in_threadpool(_service().unregister_endpoint, endpoint)
    return {"removed": removed}


@router.post("/test", response_model=PushDelivery)
async def send_test_push(payload: PushTestRequest) -> PushDelivery:
    """Prove the round trip on a real device before an alert depends on it."""
    service = _service()
    if not service.is_configured():
        raise HTTPException(status_code=503, detail="push is not configured")
    return await run_in_threadpool(
        lambda: service.send(
            title="Portfolio AI alerts are on",
            body="This phone will get budget alerts. Tap to open the plan.",
            severity="info",
            tag="push-test",
            subscription_id=payload.subscription_id,
        )
    )
