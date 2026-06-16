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


def test_systemd_user_service_status_reports_main_pid(monkeypatch) -> None:
    class FakeResult:
        returncode = 0
        stdout = "MainPID=4321\nLoadState=loaded\nActiveState=active\nSubState=running\n"

    class FakeProcess:
        def __init__(self, pid: int) -> None:
            self.pid = pid

        def create_time(self) -> float:
            return 100.0

        def memory_info(self) -> SimpleNamespace:
            return SimpleNamespace(rss=50 * 1024 * 1024)

    monkeypatch.setattr(service_monitor, "_is_container", lambda: False)
    monkeypatch.setattr(service_monitor.safe_subprocess, "run", lambda *_args, **_kwargs: FakeResult())
    monkeypatch.setattr(service_monitor.psutil, "Process", FakeProcess)
    monkeypatch.setattr(service_monitor.time, "time", lambda: 160.0)

    status = service_monitor.get_systemd_user_service_status("portfolio-backend")

    assert status is not None
    assert status.status == "running"
    assert status.pid == 4321
    assert status.uptime_seconds == 60
    assert status.memory_mb == 50


def test_check_backend_api_prefers_systemd_unit(monkeypatch) -> None:
    unit_status = service_monitor.ServiceStatus(
        service_name="portfolio-backend",
        status="running",
        pid=4321,
    )
    monkeypatch.setattr(
        service_monitor,
        "get_systemd_user_service_status",
        lambda _service_name: unit_status,
    )
    monkeypatch.setattr(
        service_monitor,
        "get_service_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pattern fallback used")),
    )

    status = service_monitor.check_backend_api(skip_http_check=True)

    assert status.pid == 4321


def test_check_frontend_uses_http_when_systemd_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(
        service_monitor,
        "get_systemd_user_service_status",
        lambda _service_name: None,
    )
    monkeypatch.setattr(
        service_monitor,
        "get_service_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("pattern fallback used")),
    )
    monkeypatch.setattr(
        service_monitor.httpx,
        "get",
        lambda *_args, **_kwargs: SimpleNamespace(status_code=200),
    )

    status = service_monitor.check_frontend()

    assert status.status == "running"
    assert status.pid is None
    assert "HTTP" in status.message
