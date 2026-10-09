from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def workflow(monkeypatch):
    # Exercise the task body without connecting a Hatchet client.
    monkeypatch.setattr(
        "app.hatchet_app.hatchet",
        SimpleNamespace(task=lambda **_kwargs: lambda function: function),
    )
    source = Path(__file__).resolve().parents[2] / "app/workflows/account_sync.py"
    spec = importlib.util.spec_from_file_location("app.workflows._account_sync_test", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "get_automation_preferences",
        lambda: {"scheduled_account_sync_enabled": {"enabled": True}},
    )
    for service in ("spend_alert_service", "budget_alert_service"):
        monkeypatch.setattr(
            f"app.services.{service}.evaluate_and_dispatch", lambda **_kwargs: []
        )
    return module


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["exception", "item_errors", "partial"])
async def test_provider_failure_reaches_hatchet_after_other_provider_runs(
    workflow, monkeypatch, failure
):
    calls = []

    def sync_snaptrade():
        calls.append("snaptrade")
        if failure == "exception":
            raise RuntimeError("provider unavailable")
        return {"status": "partial" if failure == "partial" else "success"}

    def sync_plaid():
        calls.append("plaid")
        errors = [{"error_code": "ITEM_LOGIN_REQUIRED"}] if failure == "item_errors" else []
        return {"errors": errors}

    monkeypatch.setattr(
        "app.services.snaptrade_service.SnapTradeService",
        lambda: SimpleNamespace(sync=sync_snaptrade),
    )
    monkeypatch.setattr(
        "app.services.plaid_service.PlaidService", lambda: SimpleNamespace(sync_items=sync_plaid)
    )

    with pytest.raises(RuntimeError, match="Account sync failed"):
        await workflow.sync_accounts_wf(SimpleNamespace(), SimpleNamespace())
    assert calls == ["snaptrade", "plaid"]


@pytest.mark.asyncio
async def test_alert_failure_does_not_fail_healthy_provider_sync(workflow, monkeypatch):
    monkeypatch.setattr(
        "app.services.snaptrade_service.SnapTradeService",
        lambda: SimpleNamespace(sync=lambda: {"status": "success"}),
    )
    monkeypatch.setattr(
        "app.services.plaid_service.PlaidService", lambda: SimpleNamespace(sync_items=lambda: {"errors": []})
    )

    def alert_failure(**_kwargs):
        raise RuntimeError("alert delivery unavailable")

    monkeypatch.setattr("app.services.spend_alert_service.evaluate_and_dispatch", alert_failure)
    result = await workflow.sync_accounts_wf(SimpleNamespace(), SimpleNamespace())
    assert result["snaptrade"]["status"] == "success"
    assert result["plaid"]["errors"] == []
    assert result["card_alerts"]["status"] == "error"


def test_account_sync_does_not_cancel_a_running_thread_bound_sync(monkeypatch):
    from hatchet_sdk import ConcurrencyLimitStrategy

    captured: dict[str, object] = {}

    def task(**kwargs):
        captured.update(kwargs)
        return lambda function: function

    monkeypatch.setattr("app.hatchet_app.hatchet", SimpleNamespace(task=task))
    source = Path(__file__).resolve().parents[2] / "app/workflows/account_sync.py"
    spec = importlib.util.spec_from_file_location("app.workflows._account_sync_concurrency", source)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(importlib.util.module_from_spec(spec))

    concurrency = captured["concurrency"]
    assert concurrency.max_runs == 1
    # CANCEL_IN_PROGRESS cannot stop asyncio.to_thread work, so a new run would
    # race the still-running sync; the newer run must be the one dropped.
    assert concurrency.limit_strategy == ConcurrencyLimitStrategy.CANCEL_NEWEST
