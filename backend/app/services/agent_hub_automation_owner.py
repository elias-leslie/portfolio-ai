"""Portfolio AI acceptance and receipts for Agent Hub scheduled work."""

from __future__ import annotations

import asyncio
import json
import secrets
import sys
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Literal
from uuid import uuid4

import httpx
from agent_hub import AgentHubClient
from agent_hub.exceptions import AgentHubError
from hatchet_sdk import DedupeViolationError, TriggerWorkflowOptions
from psycopg.errors import LockNotAvailable
from pydantic import BaseModel, Field

from app.config import settings
from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

TERMINAL = {"succeeded", "failed", "skipped", "cancelled"}
WORKFLOW_KEYS = frozenset({
    "jenny_daily_household_maintenance", "jenny_daily_operator",
    "jenny_weekly_learning", "retrain_ml", "jenny_weekly_price_check",
})


class OwnerDispatchPayload(BaseModel):
    run_id: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)
    workflow_key: Literal[
        "jenny_daily_household_maintenance",
        "jenny_daily_operator",
        "jenny_weekly_learning",
        "retrain_ml",
        "jenny_weekly_price_check",
    ]
    definition_version: int = Field(ge=1)
    profile_revision: int = Field(ge=1)
    occurrence_key: str = Field(min_length=1)
    trigger: Literal["scheduled", "manual"]
    scheduled_for: str
    config: dict[str, Any] = Field(default_factory=dict)
    policy_config: dict[str, Any] = Field(default_factory=dict)


def verify_dispatch_identity(
    supplied_secret: str | None,
    expected_secret: str | None,
    idempotency_key: str | None,
    run_id: str,
) -> bool:
    return bool(
        supplied_secret
        and expected_secret
        and idempotency_key == run_id
        and secrets.compare_digest(supplied_secret, expected_secret)
    )


def verify_shared_secret(supplied_secret: str | None, expected_secret: str | None) -> bool:
    return bool(supplied_secret and expected_secret and secrets.compare_digest(supplied_secret, expected_secret))


def legacy_schedule_allowed(profiles: list[dict[str, Any]] | None, workflow_key: str) -> bool:
    """An unknown or central clock cannot authorize the old cron."""
    if profiles is None:
        return False
    matching = [row for row in profiles if row.get("workflow_key") == workflow_key]
    return bool(matching) and all(row.get("clock_owner") == "legacy" for row in matching)


PROFILE_LIMIT = 500  # Agent Hub's maximum page size for automation profiles.


def _owner_client(timeout: float) -> tuple[AgentHubClient, str]:
    """Return an SDK client carrying Portfolio's identity, plus the owner secret."""
    secret = settings.agent_hub_internal_secret.get_secret_value()
    if not secret or not settings.portfolio_client_id:
        raise RuntimeError("Agent Hub owner identity is not configured")
    client = AgentHubClient(
        base_url=settings.agent_hub_url,
        timeout=timeout,
        client_name="portfolio-ai",
        client_id=settings.portfolio_client_id,
        request_source=settings.portfolio_request_source,
    )
    return client, secret


def fetch_project_profiles() -> list[dict[str, Any]] | None:
    """Read clock ownership fresh for every legacy cron; failure closes the gate."""
    try:
        client, secret = _owner_client(timeout=8)
        with client:
            items = client.list_automation_profiles(
                "portfolio-ai", internal_secret=secret, limit=PROFILE_LIMIT
            )
        # A full page may hide more profiles; an incomplete view cannot authorize a cron.
        if len(items) >= PROFILE_LIMIT:
            raise ValueError("Agent Hub profile response was incomplete")
        return [row for row in items if isinstance(row, dict)]
    except (AgentHubError, httpx.HTTPError, RuntimeError, ValueError):
        logger.warning("portfolio_automation_clock_unavailable", exc_info=True)
        return None


async def legacy_cron_allowed(workflow_key: str) -> bool:
    profiles = await asyncio.to_thread(fetch_project_profiles)
    return legacy_schedule_allowed(profiles, f"portfolio-ai/{workflow_key}")


@dataclass
class LegacyTickLease:
    manager: Any
    connection: Any
    fenced: bool


def _open_legacy_tick(workflow_key: str) -> LegacyTickLease:
    """Lock the durable workflow row until the entire old tick completes."""
    manager = get_storage().connection()
    conn = manager.__enter__()
    try:
        row = conn.execute(
            "SELECT fenced FROM automation_legacy_fences WHERE workflow_key=%s FOR UPDATE NOWAIT",
            [workflow_key],
        ).fetchone()
        if row is None:
            raise RuntimeError("Owner fence row is missing")
        return LegacyTickLease(manager, conn, bool(row[0]))
    except BaseException:
        conn.rollback()
        manager.__exit__(*sys.exc_info())
        raise


def _legacy_tick_fenced(lease: LegacyTickLease) -> bool:
    return lease.fenced


def _close_legacy_tick(lease: LegacyTickLease) -> None:
    try:
        lease.connection.rollback()
    finally:
        lease.manager.__exit__(None, None, None)


async def run_legacy_tick(
    workflow_key: str, operation: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    try:
        lease = await asyncio.to_thread(_open_legacy_tick, workflow_key)
    except LockNotAvailable:
        return {"status": "skipped", "reason": "legacy_tick_or_fence_in_progress"}
    except Exception:
        logger.warning("portfolio_legacy_fence_unavailable", workflow_key=workflow_key, exc_info=True)
        return {"status": "skipped", "reason": "owner_fence_unavailable"}
    try:
        if _legacy_tick_fenced(lease):
            return {"status": "skipped", "reason": "legacy_clock_fenced"}
        if not await legacy_cron_allowed(workflow_key):
            return {"status": "skipped", "reason": "agent_hub_clock_not_legacy"}
        return await operation()
    finally:
        await asyncio.to_thread(_close_legacy_tick, lease)


def fence_legacy_workflow(workflow_key: str) -> str:
    """Fence a drained old clock, or conflict while a legacy tick holds its row."""
    if workflow_key not in WORKFLOW_KEYS:
        raise ValueError("Unknown Portfolio automation workflow")
    with get_storage().connection() as conn:
        row = conn.execute(
            "SELECT fenced, fence_receipt FROM automation_legacy_fences WHERE workflow_key=%s FOR UPDATE NOWAIT",
            [workflow_key],
        ).fetchone()
        if row is None:
            raise RuntimeError("Owner fence row is missing")
        if row[0]:
            if not row[1]:
                raise RuntimeError("Owner fence has no receipt")
            return str(row[1])
        receipt = str(uuid4())
        conn.execute(
            """UPDATE automation_legacy_fences
               SET fenced=TRUE, fence_receipt=%s, fenced_at=NOW()
               WHERE workflow_key=%s""",
            [receipt, workflow_key],
        )
        conn.commit()
        return receipt


def _reserve(payload: OwnerDispatchPayload) -> tuple[str, bool]:
    """Persist a stable owner ID before triggering Hatchet."""
    with get_storage().connection() as conn:
        row = conn.execute(
            """INSERT INTO automation_owner_receipts
               (run_id, profile_id, workflow_key, occurrence_key, trigger, status)
               VALUES (%s,%s,%s,%s,%s,'dispatching')
               ON CONFLICT (run_id) DO NOTHING RETURNING status""",
            [payload.run_id, payload.profile_id, payload.workflow_key, payload.occurrence_key, payload.trigger],
        ).fetchone()
        if row:
            conn.commit()
            return str(row[0]), True
        existing = conn.execute(
            "SELECT profile_id, workflow_key, occurrence_key, trigger, status FROM automation_owner_receipts WHERE run_id=%s",
            [payload.run_id],
        ).fetchone()
        if not existing or tuple(str(value) for value in existing[:4]) != (
            payload.profile_id, payload.workflow_key, payload.occurrence_key, payload.trigger
        ):
            raise ValueError("Agent Hub run ID was reused with a different occurrence")
        return str(existing[4]), False


def _confirm(run_id: str) -> None:
    with get_storage().connection() as conn:
        conn.execute(
            "UPDATE automation_owner_receipts SET status='accepted' WHERE run_id=%s AND status='dispatching'",
            [run_id],
        )
        conn.commit()


async def _launch(workflow_key: str, run_id: str, input_data: dict[str, str]) -> None:
    targets = {
        "jenny_daily_household_maintenance": ("app.workflows.jenny", "jenny_daily_household_maintenance_wf"),
        "jenny_daily_operator": ("app.workflows.jenny", "jenny_daily_operator_wf"),
        "jenny_weekly_learning": ("app.workflows.jenny", "jenny_weekly_learning_wf"),
        "retrain_ml": ("app.workflows.reference", "retrain_ml_wf"),
        "jenny_weekly_price_check": ("app.workflows.jenny", "jenny_weekly_price_check_wf"),
    }
    module, task_name = targets[workflow_key]
    task = getattr(import_module(module), task_name)
    with suppress(DedupeViolationError):
        await task.aio_run_no_wait(
            input=input_data,
            options=TriggerWorkflowOptions(
                key=run_id,
                additional_metadata={"agent_hub_run_id": run_id},
            ),
        )


async def dispatch_owner_run(
    payload: OwnerDispatchPayload,
    *,
    reserve: Callable[[OwnerDispatchPayload], tuple[str, bool]] = _reserve,
    launch: Callable[[str, str, dict[str, str]], Awaitable[None]] = _launch,
    confirm: Callable[[str], None] = _confirm,
) -> dict[str, str]:
    status, created = await asyncio.to_thread(reserve, payload)
    if status in TERMINAL:
        return {"owner_run_id": payload.run_id, "status": status}
    if created or status == "dispatching":
        await launch(
            payload.workflow_key,
            payload.run_id,
            {"agent_hub_run_id": payload.run_id, "agent_hub_trigger": payload.trigger},
        )
        await asyncio.to_thread(confirm, payload.run_id)
    return {"owner_run_id": payload.run_id, "status": "accepted"}


def _receipt(run_id: str) -> tuple[str, dict[str, Any]] | None:
    with get_storage().connection() as conn:
        row = conn.execute(
            "SELECT status, receipt FROM automation_owner_receipts WHERE run_id=%s",
            [run_id],
        ).fetchone()
    if not row:
        return None
    receipt = row[1] if isinstance(row[1], dict) else json.loads(row[1] or "{}")
    return str(row[0]), receipt


def _finish(run_id: str, status: str, receipt: dict[str, Any], error: str | None) -> None:
    with get_storage().connection() as conn:
        conn.execute(
            """UPDATE automation_owner_receipts
               SET status=%s, receipt=%s::jsonb, error=%s, completed_at=NOW()
               WHERE run_id=%s AND status NOT IN ('succeeded','failed','skipped','cancelled')""",
            [status, json.dumps(receipt, default=str), error, run_id],
        )
        conn.commit()


def _report_complete(run_id: str, status: str, receipt: dict[str, Any], error: str | None) -> None:
    try:
        client, secret = _owner_client(timeout=15)
        with client:
            client.complete_automation_run(
                run_id,
                {"status": status, "owner_run_id": run_id, "receipt": receipt, "error": error},
                internal_secret=secret,
            )
    except (AgentHubError, httpx.HTTPError, RuntimeError):
        # The terminal local receipt survives; Agent Hub retries the same callback.
        logger.warning("portfolio_automation_completion_report_failed", run_id=run_id, exc_info=True)


async def run_central_task(
    run_id: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    existing = await asyncio.to_thread(_receipt, run_id)
    if existing and existing[0] in TERMINAL:
        return existing[1]
    try:
        result = await operation()
        raw_status = result.get("status")
        status = (
            "skipped" if raw_status == "skipped"
            else "failed" if raw_status in {"failed", "error", "completed_with_errors"}
            else "succeeded"
        )
        error = str(result.get("error")) if status == "failed" and result.get("error") else None
    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
        status, error = "failed", str(exc)
        await asyncio.to_thread(_finish, run_id, status, result, error)
        await asyncio.to_thread(_report_complete, run_id, status, result, error)
        raise
    await asyncio.to_thread(_finish, run_id, status, result, error)
    await asyncio.to_thread(_report_complete, run_id, status, result, error)
    return result
