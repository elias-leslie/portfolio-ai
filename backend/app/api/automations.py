"""Agent Hub to Portfolio AI automation handoff."""

import asyncio

from fastapi import APIRouter, Header, HTTPException
from psycopg.errors import LockNotAvailable

from app.config import settings
from app.services.agent_hub_automation_owner import (
    WORKFLOW_KEYS,
    OwnerDispatchPayload,
    dispatch_owner_run,
    fence_legacy_workflow,
    verify_dispatch_identity,
    verify_shared_secret,
)

router = APIRouter(prefix="/api/automations", tags=["automations"])


@router.post("/dispatch/{workflow_key}")
async def dispatch_automation(
    workflow_key: str,
    payload: OwnerDispatchPayload,
    x_agent_hub_internal: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None),
) -> dict[str, str]:
    expected = settings.agent_hub_internal_secret.get_secret_value()
    if not expected:
        raise HTTPException(503, "Agent Hub dispatch identity is not configured")
    if not verify_dispatch_identity(x_agent_hub_internal, expected, idempotency_key, payload.run_id):
        raise HTTPException(403, "Agent Hub dispatch identity is invalid")
    if payload.workflow_key != workflow_key:
        raise HTTPException(409, "Workflow key does not match dispatch path")
    try:
        return await dispatch_owner_run(payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/fence/{workflow_key}")
async def fence_automation(
    workflow_key: str,
    x_agent_hub_internal: str | None = Header(default=None),
) -> dict[str, str | bool]:
    expected = settings.agent_hub_internal_secret.get_secret_value()
    if not expected:
        raise HTTPException(503, "Agent Hub fence identity is not configured")
    if not verify_shared_secret(x_agent_hub_internal, expected):
        raise HTTPException(403, "Agent Hub fence identity is invalid")
    if workflow_key not in WORKFLOW_KEYS:
        raise HTTPException(404, "Unknown Portfolio automation workflow")
    try:
        receipt = await asyncio.to_thread(fence_legacy_workflow, workflow_key)
    except LockNotAvailable as exc:
        raise HTTPException(409, "A legacy tick is still running; retry after it finishes") from exc
    except Exception as exc:
        raise HTTPException(503, "Owner fence state is unavailable") from exc
    return {"workflow_key": workflow_key, "fence_receipt": receipt, "fenced": True}
