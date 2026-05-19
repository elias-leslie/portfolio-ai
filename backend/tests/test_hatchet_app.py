from __future__ import annotations

import os
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from hatchet_sdk.runnables.types import TaskDefaults

from app.hatchet_app import (
    DEFAULT_TASK_EXECUTION_TIMEOUT,
    DEFAULT_TASK_SCHEDULE_TIMEOUT,
    _LazyHatchet,
    get_hatchet,
)
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
