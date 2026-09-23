"""Old cron fence and manual weekly behavior at the Hatchet task boundary."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, cast

import pytest

from app.workflows import jenny
from app.workflows.models import EmptyInput, PriceCheckInput


@pytest.mark.asyncio
async def test_legacy_household_cron_stops_when_clock_is_not_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def denied(key: str, operation: Any) -> dict[str, Any]:
        assert key == "jenny_daily_household_maintenance"
        return {"status": "skipped", "reason": "agent_hub_clock_not_legacy"}

    monkeypatch.setattr(jenny, "run_legacy_tick", denied)
    result = await cast(
        Awaitable[dict[str, Any]],
        jenny.jenny_daily_household_maintenance_wf._task._fn(EmptyInput(), None),
    )
    assert result == {"status": "skipped", "reason": "agent_hub_clock_not_legacy"}


@pytest.mark.asyncio
async def test_weekly_learning_uses_fenced_clock_and_central_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def legacy_run(key: str, operation: Any) -> dict[str, Any]:
        assert key == "jenny_weekly_learning"
        return {"status": "skipped", "reason": "legacy_clock_fenced"}

    monkeypatch.setattr(jenny, "run_legacy_tick", legacy_run)
    legacy_result = await cast(
        Awaitable[dict[str, Any]],
        jenny.jenny_weekly_learning_wf._task._fn(EmptyInput(), None),
    )
    assert legacy_result == {"status": "skipped", "reason": "legacy_clock_fenced"}

    async def central_run(run_id: str, operation: Any) -> dict[str, Any]:
        assert run_id == "ah-weekly-learning-1"
        return await operation()

    from app.tasks import jenny_operator_tasks

    monkeypatch.setattr(jenny, "run_central_task", central_run)
    seen_triggers: list[str] = []

    def learning_task(triggered_by: str) -> dict[str, Any]:
        seen_triggers.append(triggered_by)
        return {"status": "completed"}

    monkeypatch.setattr(jenny_operator_tasks, "run_weekly_learning_task", learning_task)
    central_result = await cast(
        Awaitable[dict[str, Any]],
        jenny.jenny_weekly_learning_wf._task._fn(
            EmptyInput(agent_hub_run_id="ah-weekly-learning-1", agent_hub_trigger="manual"), None
        ),
    )
    assert central_result == {"status": "completed"}
    assert seen_triggers == ["manual"]


@pytest.mark.asyncio
async def test_central_operator_uses_owner_gate_without_old_preference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(jenny, "get_automation_preferences", lambda: pytest.fail("old preference read"))
    monkeypatch.setattr(jenny, "is_trading_day", lambda: False)

    async def central_run(run_id: str, operation: Any) -> dict[str, Any]:
        assert run_id == "ah-operator-1"
        return await operation()

    monkeypatch.setattr(jenny, "run_central_task", central_run)
    result = await cast(
        Awaitable[dict[str, Any]],
        jenny.jenny_daily_operator_wf._task._fn(
            EmptyInput(agent_hub_run_id="ah-operator-1", agent_hub_trigger="scheduled"), None
        ),
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "Not a trading day (holiday)"


@pytest.mark.asyncio
async def test_prequeued_manual_price_check_bypasses_old_cron_fence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unexpected_fence(key: str, operation: Any) -> dict[str, Any]:
        pytest.fail("manual price check queried cron fence")

    monkeypatch.setattr(jenny, "run_legacy_tick", unexpected_fence)
    from app.tasks import jenny_operator_tasks

    monkeypatch.setattr(jenny_operator_tasks, "run_weekly_price_check_task", lambda run_id: {"run_id": run_id})
    result = await cast(
        Awaitable[dict[str, Any]],
        jenny.jenny_weekly_price_check_wf._task._fn(
            PriceCheckInput(run_id="local-price-check-1", triggered_by="manual"), None
        ),
    )
    assert result == {"run_id": "local-price-check-1"}
