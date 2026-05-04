from __future__ import annotations

from types import SimpleNamespace

from app.services import service_monitor


def test_get_process_by_pattern_returns_none_when_no_process_matches(monkeypatch) -> None:
    monkeypatch.setattr(service_monitor.psutil, "process_iter", lambda *_args, **_kwargs: [])

    assert service_monitor.get_process_by_pattern("redis-server") is None


def test_get_process_by_pattern_matches_cmdline(monkeypatch) -> None:
    fake_process = SimpleNamespace(
        pid=1234,
        info={"pid": 1234, "name": "python", "cmdline": ["python", "-m", "app.worker"]},
    )
    monkeypatch.setattr(
        service_monitor.psutil,
        "process_iter",
        lambda *_args, **_kwargs: [fake_process],
    )

    assert service_monitor.get_process_by_pattern(r"python.*app\.worker") == 1234


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
