from __future__ import annotations

import asyncio
import os
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from hatchet_sdk.runnables.types import TaskDefaults

from app.hatchet_app import (
    _HATCHET_SHUTDOWN_404_GUARD_ATTR,
    DEFAULT_TASK_EXECUTION_TIMEOUT,
    DEFAULT_TASK_SCHEDULE_TIMEOUT,
    _install_hatchet_shutdown_404_guard,
    _LazyHatchet,
    _wrap_hatchet_shutdown_404_guard,
    get_hatchet,
)
from app.worker import _disable_worker_sys_exit
from app.worker import main as worker_main


def test_task_wrapper_injects_nonrestrictive_defaults(monkeypatch) -> None:
    mock_hatchet = MagicMock()
    sentinel = object()
    mock_hatchet.task.return_value = sentinel
    monkeypatch.setattr("app.hatchet_app.get_hatchet", lambda: mock_hatchet)

    result = _LazyHatchet().task(name="example")

    assert result is sentinel
    kwargs = mock_hatchet.task.call_args.kwargs
    assert kwargs["schedule_timeout"] == DEFAULT_TASK_SCHEDULE_TIMEOUT
    assert kwargs["execution_timeout"] == DEFAULT_TASK_EXECUTION_TIMEOUT


def test_task_wrapper_preserves_explicit_timeouts(monkeypatch) -> None:
    mock_hatchet = MagicMock()
    monkeypatch.setattr("app.hatchet_app.get_hatchet", lambda: mock_hatchet)

    _LazyHatchet().task(
        name="example",
        schedule_timeout=timedelta(minutes=2),
        execution_timeout=timedelta(minutes=3),
    )

    kwargs = mock_hatchet.task.call_args.kwargs
    assert kwargs["schedule_timeout"] == timedelta(minutes=2)
    assert kwargs["execution_timeout"] == timedelta(minutes=3)


def test_workflow_wrapper_injects_task_defaults(monkeypatch) -> None:
    mock_hatchet = MagicMock()
    sentinel = object()
    mock_hatchet.workflow.return_value = sentinel
    monkeypatch.setattr("app.hatchet_app.get_hatchet", lambda: mock_hatchet)

    result = _LazyHatchet().workflow(name="example")

    assert result is sentinel
    task_defaults = mock_hatchet.workflow.call_args.kwargs["task_defaults"]
    assert isinstance(task_defaults, TaskDefaults)
    assert task_defaults.schedule_timeout == DEFAULT_TASK_SCHEDULE_TIMEOUT
    assert task_defaults.execution_timeout == DEFAULT_TASK_EXECUTION_TIMEOUT


def test_get_hatchet_primes_sdk_env_from_settings(monkeypatch) -> None:
    captured: dict[str, str | None] = {}

    class FakeHatchet:
        def __init__(self) -> None:
            captured["token"] = os.environ.get("HATCHET_CLIENT_TOKEN")
            captured["host_port"] = os.environ.get("HATCHET_CLIENT_HOST_PORT")
            captured["tls"] = os.environ.get("HATCHET_CLIENT_TLS_STRATEGY")

    fake_settings = SimpleNamespace(
        hatchet_client_token="token-from-env-file",
        hatchet_client_host_port="127.0.0.1:57070",
        hatchet_client_tls_strategy="none",
    )

    monkeypatch.delenv("HATCHET_CLIENT_TOKEN", raising=False)
    monkeypatch.delenv("HATCHET_CLIENT_HOST_PORT", raising=False)
    monkeypatch.delenv("HATCHET_CLIENT_TLS_STRATEGY", raising=False)
    monkeypatch.setattr("app.hatchet_app.get_settings", lambda: fake_settings)
    monkeypatch.setattr("hatchet_sdk.Hatchet", FakeHatchet)

    get_hatchet.cache_clear()
    try:
        get_hatchet()
    finally:
        get_hatchet.cache_clear()

    assert captured == {
        "token": "token-from-env-file",
        "host_port": "127.0.0.1:57070",
        "tls": "none",
    }


def test_shutdown_guard_swallows_worker_not_found() -> None:
    class FakeNotFoundError(Exception):
        pass

    call_log: list[str] = []

    async def raise_not_found(process) -> None:
        call_log.append(process.listener.worker_id)
        raise FakeNotFoundError()

    guarded = _wrap_hatchet_shutdown_404_guard(
        raise_not_found,
        not_found_exception=FakeNotFoundError,
    )

    process = SimpleNamespace(listener=SimpleNamespace(worker_id="worker-123"))

    asyncio.run(guarded(process))

    assert call_log == ["worker-123"]


def test_shutdown_guard_preserves_unexpected_errors() -> None:
    class FakeNotFoundError(Exception):
        pass

    class UnexpectedFailureError(Exception):
        pass

    async def raise_unexpected(_process) -> None:
        raise UnexpectedFailureError("boom")

    guarded = _wrap_hatchet_shutdown_404_guard(
        raise_unexpected,
        not_found_exception=FakeNotFoundError,
    )

    with pytest.raises(UnexpectedFailureError, match="boom"):
        asyncio.run(guarded(SimpleNamespace(listener=None)))


def test_get_hatchet_installs_shutdown_404_guard(monkeypatch) -> None:
    mock_prime = MagicMock()
    mock_guard = MagicMock()
    mock_hatchet_cls = MagicMock(return_value="hatchet-client")

    monkeypatch.setattr("app.hatchet_app._prime_hatchet_sdk_env", mock_prime)
    monkeypatch.setattr("app.hatchet_app._install_hatchet_shutdown_404_guard", mock_guard)
    monkeypatch.setattr("hatchet_sdk.Hatchet", mock_hatchet_cls)

    get_hatchet.cache_clear()
    try:
        result = get_hatchet()
    finally:
        get_hatchet.cache_clear()

    assert result == "hatchet-client"
    mock_prime.assert_called_once_with()
    mock_guard.assert_called_once_with()


def test_install_shutdown_404_guard_wraps_current_worker_pause_method(monkeypatch) -> None:
    from hatchet_sdk.worker.worker import Worker

    async def fake_pause_task_assignment(_worker) -> None:
        return None

    monkeypatch.setattr(Worker, "_pause_task_assignment", fake_pause_task_assignment)

    _install_hatchet_shutdown_404_guard()

    assert Worker._pause_task_assignment is not fake_pause_task_assignment
    assert getattr(Worker._pause_task_assignment, _HATCHET_SHUTDOWN_404_GUARD_ATTR) is True


def test_disable_worker_sys_exit_handles_read_only_hatchet_property() -> None:
    class WorkerWithReadOnlyHandleKill:
        def __init__(self) -> None:
            self._handle_kill = True

        @property
        def handle_kill(self) -> bool:
            return self._handle_kill

    worker = WorkerWithReadOnlyHandleKill()

    _disable_worker_sys_exit(worker)

    assert worker._handle_kill is False


def test_worker_registers_macro_calendar_and_ohlcv_workflows(monkeypatch) -> None:
    worker = MagicMock()
    hatchet = MagicMock()
    configure_logging = MagicMock()
    hatchet.worker.return_value = worker
    exit_mock = MagicMock(side_effect=SystemExit(0))
    monkeypatch.setattr("app.worker.hatchet", hatchet)
    monkeypatch.setattr("app.worker.configure_logging", configure_logging)
    monkeypatch.setattr("app.worker.os._exit", exit_mock)

    with pytest.raises(SystemExit):
        worker_main()

    workflows = hatchet.worker.call_args.kwargs["workflows"]
    workflow_names = {workflow.name for workflow in workflows}
    assert "portfolio-market-macro-calendar-ingestion" in workflow_names
    assert "portfolio-refresh-ohlcv" in workflow_names
    configure_logging.assert_called_once_with()
    assert worker.handle_kill is False
    worker.start.assert_called_once_with()
    exit_mock.assert_called_once_with(0)
