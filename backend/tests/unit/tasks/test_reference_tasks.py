from __future__ import annotations

from subprocess import CompletedProcess
from typing import Any

import pytest

from app.tasks import reference_tasks


def test_refresh_financial_health_scores_isolated_parses_child_result(monkeypatch) -> None:
    calls: dict[str, Any] = {}

    def fake_run(args: list[str], **kwargs: Any) -> CompletedProcess[str]:
        calls["args"] = args
        calls["kwargs"] = kwargs
        return CompletedProcess(
            args,
            0,
            stdout='log line\nFINANCIAL_HEALTH_RESULT_JSON={"symbols_processed": 44, "symbols_updated": 26}\n',
            stderr="",
        )

    monkeypatch.setattr(reference_tasks.safe_subprocess, "run", fake_run)

    result = reference_tasks.refresh_financial_health_scores_isolated()

    assert result == {
        "symbols_processed": 44,
        "symbols_updated": 26,
        "execution_mode": "subprocess",
    }
    assert calls["args"][1:] == ["-m", "app.tasks.reference_tasks", "financial-health"]
    assert calls["kwargs"]["capture_output"] is True
    assert calls["kwargs"]["text"] is True
    assert calls["kwargs"]["timeout"] == reference_tasks._FINANCIAL_HEALTH_CHILD_TIMEOUT_SECONDS


def test_refresh_financial_health_scores_isolated_fails_loudly_on_child_error(monkeypatch) -> None:
    def fake_run(args: list[str], **_kwargs: Any) -> CompletedProcess[str]:
        return CompletedProcess(args, 1, stdout="child out", stderr="child err")

    monkeypatch.setattr(reference_tasks.safe_subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="financial health child process failed rc=1"):
        reference_tasks.refresh_financial_health_scores_isolated()


def test_refresh_financial_health_scores_isolated_requires_result_marker(monkeypatch) -> None:
    def fake_run(args: list[str], **_kwargs: Any) -> CompletedProcess[str]:
        return CompletedProcess(args, 0, stdout="missing marker", stderr="")

    monkeypatch.setattr(reference_tasks.safe_subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="did not emit a result marker"):
        reference_tasks.refresh_financial_health_scores_isolated()


def test_reference_tasks_module_financial_health_entrypoint_emits_result(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        reference_tasks,
        "refresh_financial_health_scores",
        lambda: {"symbols_processed": 44, "symbols_updated": 26},
    )

    assert reference_tasks._main(["financial-health"]) == 0

    captured = capsys.readouterr()
    assert "FINANCIAL_HEALTH_RESULT_JSON=" in captured.out
    assert '"symbols_updated": 26' in captured.out
