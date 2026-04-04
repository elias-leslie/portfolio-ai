from __future__ import annotations

import subprocess

from app.services import service_monitor


def test_get_process_by_pattern_returns_none_when_pgrep_missing(monkeypatch) -> None:
    def fake_run(*_args, **_kwargs):
        raise FileNotFoundError("pgrep")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert service_monitor.get_process_by_pattern("redis-server") is None


def test_check_backend_api_in_container_marks_backend_running(monkeypatch) -> None:
    monkeypatch.setattr(service_monitor, "_is_container", lambda: True)
    monkeypatch.setattr(
        service_monitor,
        "get_service_status",
        lambda *_args, **_kwargs: service_monitor.ServiceStatus(
            service_name="portfolio-backend",
            status="down",
            message="Process not visible across containers",
        ),
    )

    status = service_monitor.check_backend_api(skip_http_check=True)

    assert status.status == "running"
    assert "Container mode" in status.message
