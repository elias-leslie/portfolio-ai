from __future__ import annotations

from types import SimpleNamespace

from app.services.service_monitor import ServiceStatus
from app.utils import health_service


def _service_status(name: str, status: str) -> ServiceStatus:
    return ServiceStatus(service_name=name, status=status)


def _configure_health_service_dependencies(
    monkeypatch,
    *,
    frontend_status: str,
) -> health_service.HealthCheckService:
    storage = object()

    def fake_get_storage() -> object:
        return storage

    def fake_check_database(_storage) -> SimpleNamespace:
        return SimpleNamespace(status="ok")

    def fake_check_sources(_storage) -> dict[str, SimpleNamespace]:
        return {}

    def fake_get_all_service_statuses(**_kwargs) -> dict[str, ServiceStatus]:
        return {
            "portfolio-backend": _service_status("portfolio-backend", "running"),
            "portfolio-frontend": _service_status("portfolio-frontend", frontend_status),
        }

    def fake_metrics(_storage) -> SimpleNamespace:
        return SimpleNamespace()

    def fake_get_api_quotas(_storage) -> list[SimpleNamespace]:
        return []

    monkeypatch.setattr(health_service, "get_storage", fake_get_storage)
    monkeypatch.setattr(
        health_service,
        "check_database",
        fake_check_database,
    )
    monkeypatch.setattr(health_service, "check_sources", fake_check_sources)
    monkeypatch.setattr(
        health_service,
        "get_all_service_statuses",
        fake_get_all_service_statuses,
    )
    monkeypatch.setattr(health_service, "get_cache_stats", fake_metrics)
    monkeypatch.setattr(health_service, "get_agent_stats", fake_metrics)
    monkeypatch.setattr(health_service, "get_workflow_health", fake_metrics)
    monkeypatch.setattr(health_service, "get_watchlist_stats", fake_metrics)
    monkeypatch.setattr(health_service, "get_api_quotas", fake_get_api_quotas)
    return health_service.HealthCheckService()


def test_perform_health_check_degrades_when_any_service_is_down(monkeypatch) -> None:
    service = _configure_health_service_dependencies(
        monkeypatch,
        frontend_status="down",
    )

    result = service.perform_health_check()

    assert result["status"] == "degraded"


def test_perform_health_check_degrades_when_any_service_is_degraded(monkeypatch) -> None:
    service = _configure_health_service_dependencies(
        monkeypatch,
        frontend_status="degraded",
    )

    result = service.perform_health_check()

    assert result["status"] == "degraded"
