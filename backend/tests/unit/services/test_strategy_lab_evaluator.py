"""Tests for Strategy Lab evaluator."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from types import ModuleType
from typing import Any
from unittest.mock import Mock

import pytest

from app.services.strategy_lab_evaluator import (
    EVALUATION_INTERVAL_MINUTES,
    STATE_CHANGE_CATEGORY,
    StrategyLabEvaluator,
    build_current_state,
    diff_strategy_states,
)


class FakeConnection:
    def __init__(self, storage: FakeStorage) -> None:
        self.storage = storage

    def execute(self, sql: str, params: list[Any] | None = None) -> Any:
        if "FROM strategy_screening_results" in sql:
            return FakeResult(self.storage.strategies)
        if params is None:
            raise AssertionError(f"Expected SQL params: {sql}")
        if "SELECT current_state" in sql:
            strategy_id = str(params[0])
            state = self.storage.states.get(strategy_id)
            return FakeResult([] if state is None else [(state,)])
        if "INSERT INTO strategy_lab_evaluation_states" in sql:
            strategy_id = str(params[0])
            self.storage.states[strategy_id] = params[4]
            self.storage.state_writes.append(params)
            return FakeResult([])
        if "INSERT INTO jenny_notifications" in sql:
            self.storage.notifications.append(params)
            return FakeResult([])
        raise AssertionError(f"Unexpected SQL: {sql}")

    def commit(self) -> None:
        self.storage.commits += 1


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def fetchall(self) -> list[Any]:
        return self.rows

    def fetchone(self) -> Any | None:
        return self.rows[0] if self.rows else None


class FakeStorage:
    def __init__(self, strategies: list[dict[str, Any]]) -> None:
        self.strategies = strategies
        self.states: dict[str, dict[str, Any]] = {}
        self.notifications: list[list[Any]] = []
        self.state_writes: list[list[Any]] = []
        self.commits = 0

    @contextmanager
    def connection(self) -> Any:
        yield FakeConnection(self)


def _strategy(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": uuid.uuid4(),
        "symbol": "AAPL",
        "strategy_type": "momentum",
        "run_date": "2026-05-19",
        "edge_score": 1.25,
        "mean_sharpe": 1.4,
        "mean_win_rate": 0.58,
        "max_drawdown_pct": -0.12,
        "statistically_significant": True,
        "significance_level": "p05",
    }
    data.update(overrides)
    return data


def test_diff_strategy_states_ignores_initial_state_and_detects_real_change() -> None:
    current = build_current_state(_strategy(edge_score=1.25))

    initial_diff = diff_strategy_states(None, current)
    changed_diff = diff_strategy_states({**current, "signal": "watch"}, current)
    unchanged_diff = diff_strategy_states(current, {**current, "run_date": "2026-05-20"})

    assert initial_diff.changed is False
    assert changed_diff.changed is True
    assert changed_diff.changes == {"signal": {"previous": "watch", "current": "candidate"}}
    assert unchanged_diff.changed is False


@pytest.mark.asyncio
async def test_evaluation_is_idempotent_and_only_notifies_on_state_transition() -> None:
    strategy = _strategy()
    storage = FakeStorage([strategy])
    evaluator = StrategyLabEvaluator(storage=storage)

    first = await evaluator.evaluate_all_active_strategies()
    second = await evaluator.evaluate_all_active_strategies()

    assert first == {"strategies_evaluated": 1, "notifications_created": 0}
    assert second == {"strategies_evaluated": 1, "notifications_created": 0}
    assert storage.notifications == []
    assert len(storage.state_writes) == 2

    strategy["edge_score"] = 0.5
    third = await evaluator.evaluate_all_active_strategies()

    assert third == {"strategies_evaluated": 1, "notifications_created": 1}
    assert storage.notifications[0][2] == STATE_CHANGE_CATEGORY
    assert storage.notifications[0][3] == "info"


def test_scheduler_registers_async_five_minute_job(monkeypatch: pytest.MonkeyPatch) -> None:
    instances: list[FakeScheduler] = []

    class FakeScheduler:
        def __init__(self) -> None:
            self.jobs: list[dict[str, Any]] = []
            instances.append(self)

        def add_job(self, func: Any, trigger: str, **kwargs: Any) -> None:
            self.jobs.append({"func": func, "trigger": trigger, **kwargs})

    asyncio_module = ModuleType("apscheduler.schedulers.asyncio")
    asyncio_module.AsyncIOScheduler = FakeScheduler
    monkeypatch.setitem(__import__("sys").modules, "apscheduler", ModuleType("apscheduler"))
    monkeypatch.setitem(
        __import__("sys").modules,
        "apscheduler.schedulers",
        ModuleType("apscheduler.schedulers"),
    )
    monkeypatch.setitem(__import__("sys").modules, "apscheduler.schedulers.asyncio", asyncio_module)

    import app.services.strategy_lab_scheduler as scheduler_module

    evaluator = Mock()

    scheduler = scheduler_module.create_strategy_lab_scheduler(evaluator)

    assert scheduler is instances[0]
    assert instances[0].jobs == [
        {
            "func": evaluator.evaluate_all_active_strategies,
            "trigger": "interval",
            "minutes": EVALUATION_INTERVAL_MINUTES,
            "id": "strategy_lab_evaluator",
            "replace_existing": True,
            "max_instances": 1,
            "coalesce": True,
        }
    ]
