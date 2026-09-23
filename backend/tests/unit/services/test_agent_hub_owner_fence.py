"""Owner fence prevents a legacy tick from racing central cutover."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from psycopg.errors import LockNotAvailable
from pydantic import SecretStr

from app.api import automations
from app.main import app
from app.services import agent_hub_automation_owner as owner


@pytest.mark.asyncio
async def test_legacy_tick_holds_lease_through_domain_work(monkeypatch: pytest.MonkeyPatch) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    closed: list[bool] = []
    lease = object()
    monkeypatch.setattr(owner, "_open_legacy_tick", lambda _key: lease)
    monkeypatch.setattr(owner, "_legacy_tick_fenced", lambda _current: False)
    monkeypatch.setattr(owner, "_close_legacy_tick", lambda _current: closed.append(True))

    async def clock_allowed(key: str) -> bool:
        return True

    async def domain_work() -> dict[str, Any]:
        entered.set()
        await release.wait()
        assert not closed
        return {"status": "completed"}

    monkeypatch.setattr(owner, "legacy_cron_allowed", clock_allowed)
    running = asyncio.create_task(owner.run_legacy_tick("jenny_daily_operator", domain_work))
    await entered.wait()
    assert not closed
    release.set()
    assert await running == {"status": "completed"}
    assert closed == [True]


@pytest.mark.asyncio
async def test_sticky_fence_blocks_legacy_tick_before_clock_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    lease = object()
    monkeypatch.setattr(owner, "_open_legacy_tick", lambda _key: lease)
    monkeypatch.setattr(owner, "_legacy_tick_fenced", lambda _current: True)
    monkeypatch.setattr(owner, "_close_legacy_tick", lambda _current: None)

    async def unexpected_clock(key: str) -> bool:
        pytest.fail("fenced tick queried Agent Hub")

    monkeypatch.setattr(owner, "legacy_cron_allowed", unexpected_clock)
    result = await owner.run_legacy_tick("jenny_daily_operator", lambda: pytest.fail("domain ran"))
    assert result == {"status": "skipped", "reason": "legacy_clock_fenced"}


def test_fence_http_contract_requires_secret_and_returns_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(automations.settings, "agent_hub_internal_secret", SecretStr("shared-secret"))
    calls: list[str] = []

    def fence(key: str) -> str:
        calls.append(key)
        return "stable-fence-receipt"

    monkeypatch.setattr(automations, "fence_legacy_workflow", fence)
    client = TestClient(app)
    path = "/api/automations/fence/jenny_daily_operator"
    assert client.post(path).status_code == 403
    response = client.post(path, headers={"X-Agent-Hub-Internal": "shared-secret"})
    assert response.status_code == 200
    assert response.json() == {
        "workflow_key": "jenny_daily_operator", "fence_receipt": "stable-fence-receipt", "fenced": True,
    }
    assert calls == ["jenny_daily_operator"]


def test_fence_receipt_is_persisted_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    class Connection:
        def __init__(self) -> None:
            self.row: tuple[bool, str | None] = (False, None)
            self.statements: list[str] = []
            self.commits = 0

        def execute(self, sql: str, params: list[str] | None = None) -> Connection:
            self.statements.append(sql)
            if "UPDATE automation_legacy_fences" in sql:
                assert params is not None
                self.row = (True, params[0])
            return self

        def fetchone(self) -> tuple[bool, str | None]:
            return self.row

        def commit(self) -> None:
            self.commits += 1

    connection = Connection()

    class Storage:
        @contextmanager
        def connection(self) -> Iterator[Connection]:
            yield connection

    monkeypatch.setattr(owner, "get_storage", Storage)
    first = owner.fence_legacy_workflow("jenny_daily_operator")
    second = owner.fence_legacy_workflow("jenny_daily_operator")
    assert first == second
    assert connection.commits == 1
    assert any("FOR UPDATE NOWAIT" in sql for sql in connection.statements)
    assert not any("lock_timeout" in sql for sql in connection.statements)


def test_fence_http_returns_conflict_when_old_tick_has_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(automations.settings, "agent_hub_internal_secret", SecretStr("shared-secret"))

    def busy(_key: str) -> str:
        raise LockNotAvailable("Legacy tick still holds the fence row")

    monkeypatch.setattr(automations, "fence_legacy_workflow", busy)
    response = TestClient(app).post(
        "/api/automations/fence/retrain_ml",
        headers={"X-Agent-Hub-Internal": "shared-secret"},
    )
    assert response.status_code == 409
