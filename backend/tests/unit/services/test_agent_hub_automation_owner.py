"""Contract checks for Agent Hub owned Portfolio AI background work."""

from __future__ import annotations

from typing import ClassVar

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api import automations
from app.main import app
from app.services.agent_hub_automation_owner import (
    WORKFLOW_KEYS,
    OwnerDispatchPayload,
    dispatch_owner_run,
    legacy_schedule_allowed,
    verify_dispatch_identity,
)

PAYLOAD = OwnerDispatchPayload(
    run_id="ah-run-1",
    profile_id="profile-1",
    workflow_key="jenny_daily_operator",
    definition_version=1,
    profile_revision=2,
    occurrence_key="scheduled:profile-1:2026-09-23T22:15:00+00:00",
    trigger="scheduled",
    scheduled_for="2026-09-23T22:15:00+00:00",
    config={},
    policy_config={},
)


def test_dispatch_auth_requires_shared_secret_and_matching_idempotency_key() -> None:
    assert verify_dispatch_identity("shared-secret", "shared-secret", "ah-run-1", "ah-run-1")
    assert not verify_dispatch_identity("wrong", "shared-secret", "ah-run-1", "ah-run-1")
    assert not verify_dispatch_identity("shared-secret", "", "ah-run-1", "ah-run-1")
    assert not verify_dispatch_identity("shared-secret", "shared-secret", "other", "ah-run-1")


def test_legacy_clock_fails_closed_and_stops_after_central_cutover() -> None:
    assert not legacy_schedule_allowed(None, "portfolio-ai/jenny_daily_operator")
    assert legacy_schedule_allowed(
        [{"workflow_key": "portfolio-ai/jenny_daily_operator", "clock_owner": "legacy"}],
        "portfolio-ai/jenny_daily_operator",
    )
    assert not legacy_schedule_allowed(
        [{"workflow_key": "portfolio-ai/jenny_daily_operator", "clock_owner": "central"}],
        "portfolio-ai/jenny_daily_operator",
    )
    assert not legacy_schedule_allowed([], "portfolio-ai/jenny_daily_operator")


def test_weekly_learning_is_registered_for_dispatch_and_fencing() -> None:
    assert "jenny_weekly_learning" in WORKFLOW_KEYS
    assert OwnerDispatchPayload.model_validate({
        **PAYLOAD.model_dump(),
        "workflow_key": "jenny_weekly_learning",
    }).workflow_key == "jenny_weekly_learning"


@pytest.mark.asyncio
async def test_owner_dispatch_receipt_is_stable_on_replay() -> None:
    reserved: dict[str, str] = {}
    launches: list[tuple[str, str, dict[str, str]]] = []

    def reserve(payload: OwnerDispatchPayload) -> tuple[str, bool]:
        if payload.run_id in reserved:
            return reserved[payload.run_id], False
        reserved[payload.run_id] = "accepted"
        return "accepted", True

    async def launch(workflow_key: str, run_id: str, input_data: dict[str, str]) -> None:
        launches.append((workflow_key, run_id, input_data))

    first = await dispatch_owner_run(PAYLOAD, reserve=reserve, launch=launch, confirm=lambda _: None)
    replay = await dispatch_owner_run(PAYLOAD, reserve=reserve, launch=launch, confirm=lambda _: None)

    assert first == replay == {"owner_run_id": "ah-run-1", "status": "accepted"}
    assert launches == [
        (
            "jenny_daily_operator",
            "ah-run-1",
            {"agent_hub_run_id": "ah-run-1", "agent_hub_trigger": "scheduled"},
        )
    ]


@pytest.mark.asyncio
async def test_callback_rejects_wrong_identity_before_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(automations.settings, "agent_hub_internal_secret", SecretStr("shared-secret"))

    async def unexpected_dispatch(payload: OwnerDispatchPayload) -> dict[str, str]:
        raise AssertionError("Unauthorized callback reached dispatch")

    monkeypatch.setattr(automations, "dispatch_owner_run", unexpected_dispatch)
    with pytest.raises(HTTPException) as error:
        await automations.dispatch_automation(
            "jenny_daily_operator", PAYLOAD,
            x_agent_hub_internal="wrong", idempotency_key=PAYLOAD.run_id,
        )
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_callback_forwards_valid_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(automations.settings, "agent_hub_internal_secret", SecretStr("shared-secret"))
    seen: list[OwnerDispatchPayload] = []

    async def dispatch(payload: OwnerDispatchPayload) -> dict[str, str]:
        seen.append(payload)
        return {"owner_run_id": payload.run_id, "status": "accepted"}

    monkeypatch.setattr(automations, "dispatch_owner_run", dispatch)
    result = await automations.dispatch_automation(
        "jenny_daily_operator", PAYLOAD,
        x_agent_hub_internal="shared-secret", idempotency_key=PAYLOAD.run_id,
    )
    assert result == {"owner_run_id": PAYLOAD.run_id, "status": "accepted"}
    assert seen == [PAYLOAD]


def test_callback_http_route_uses_service_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(automations.settings, "agent_hub_internal_secret", SecretStr("shared-secret"))

    async def dispatch(payload: OwnerDispatchPayload) -> dict[str, str]:
        return {"owner_run_id": payload.run_id, "status": "accepted"}

    monkeypatch.setattr(automations, "dispatch_owner_run", dispatch)
    response = TestClient(app).post(
        "/api/automations/dispatch/jenny_daily_operator",
        json=PAYLOAD.model_dump(),
        headers={"X-Agent-Hub-Internal": "shared-secret", "Idempotency-Key": PAYLOAD.run_id},
    )
    assert response.status_code == 200
    assert response.json() == {"owner_run_id": PAYLOAD.run_id, "status": "accepted"}


class _FakeOwnerSDK:
    """Records SDK owner calls; the real transport is the SDK's concern."""

    profiles: ClassVar[list[dict[str, str]]] = []
    calls: ClassVar[list[tuple[str, tuple, dict]]] = []

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    def __enter__(self) -> _FakeOwnerSDK:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def list_automation_profiles(self, *args: object, **kwargs: object) -> list[dict[str, str]]:
        self.calls.append(("list", args, kwargs))
        return self.profiles

    def complete_automation_run(self, *args: object, **kwargs: object) -> dict[str, str]:
        self.calls.append(("complete", args, kwargs))
        return {}


@pytest.fixture
def owner_sdk(monkeypatch: pytest.MonkeyPatch) -> type[_FakeOwnerSDK]:
    from app.services import agent_hub_automation_owner as owner

    monkeypatch.setattr(owner.settings, "agent_hub_internal_secret", SecretStr("owner-secret"))
    monkeypatch.setattr(owner.settings, "portfolio_client_id", "portfolio-client")
    monkeypatch.setattr(owner, "AgentHubClient", _FakeOwnerSDK)
    _FakeOwnerSDK.profiles = []
    _FakeOwnerSDK.calls = []
    return _FakeOwnerSDK


def test_profile_lookup_uses_sdk_with_owner_secret(owner_sdk: type[_FakeOwnerSDK]) -> None:
    from app.services.agent_hub_automation_owner import fetch_project_profiles

    owner_sdk.profiles = [{"workflow_key": "portfolio-ai/retrain_ml", "clock_owner": "central"}]
    assert fetch_project_profiles() == owner_sdk.profiles
    (name, args, kwargs), = owner_sdk.calls
    assert (name, args) == ("list", ("portfolio-ai",))
    assert kwargs["internal_secret"] == "owner-secret"


def test_full_profile_page_closes_the_legacy_gate(owner_sdk: type[_FakeOwnerSDK]) -> None:
    from app.services.agent_hub_automation_owner import PROFILE_LIMIT, fetch_project_profiles

    owner_sdk.profiles = [{"workflow_key": f"k{i}", "clock_owner": "legacy"} for i in range(PROFILE_LIMIT)]
    assert fetch_project_profiles() is None


def test_completion_receipt_is_reported_through_sdk(owner_sdk: type[_FakeOwnerSDK]) -> None:
    from app.services.agent_hub_automation_owner import _report_complete

    _report_complete("ah-run-1", "succeeded", {"ok": True}, None)
    (name, args, kwargs), = owner_sdk.calls
    assert name == "complete"
    assert args == ("ah-run-1", {"status": "succeeded", "owner_run_id": "ah-run-1", "receipt": {"ok": True}, "error": None})
    assert kwargs == {"internal_secret": "owner-secret"}
