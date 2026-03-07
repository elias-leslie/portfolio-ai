"""Tests for status endpoints and service monitoring."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.constants.services import SERVICE_PROCESS_PATTERNS
from app.main import app
from app.services.service_monitor import (
    check_frontend,
    get_all_service_statuses,
    get_service_status,
)

client = TestClient(app)


class TestServiceMonitor:
    """Tests for service monitoring functions."""

    def test_get_service_status_running_process(self) -> None:
        """Test get_service_status returns correct status for running process."""
        # Mock psutil.Process to simulate a running process
        mock_process = Mock()
        mock_process.pid = 12345
        mock_process.status.return_value = "running"
        mock_process.create_time.return_value = datetime.now(UTC).timestamp() - 3600  # 1 hour ago
        mock_process.memory_info.return_value = Mock(rss=100 * 1024 * 1024)  # 100 MB

        with (
            patch("app.services.service_monitor.psutil.Process", return_value=mock_process),
            patch("app.services.service_monitor.get_process_by_pattern", return_value=12345),
        ):
            status = get_service_status(
                service_name="test-service",
                process_pattern="test-service.*",
            )

            assert status.service_name == "test-service"
            assert status.status == "running"
            assert status.pid == 12345
            assert status.uptime_seconds is not None
            assert status.uptime_seconds > 3500  # Approximately 1 hour
            assert status.memory_mb == 100
            assert status.message == ""

    def test_get_service_status_not_running(self) -> None:
        """Test get_service_status returns correct status when process not found."""
        with patch("app.services.service_monitor.get_process_by_pattern", return_value=None):
            status = get_service_status(
                service_name="test-service",
                process_pattern="test-service.*",
            )

            assert status.service_name == "test-service"
            assert status.status == "down"
            assert status.pid is None
            assert status.uptime_seconds is None
            assert status.memory_mb is None
            assert "not running" in status.message.lower()

    def test_get_process_by_pattern_found(self) -> None:
        """Test get_process_by_pattern finds process using pgrep."""
        from app.services.service_monitor import get_process_by_pattern

        # Mock subprocess.run to return a PID
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "12345\n67890\n"  # Multiple PIDs, should return first

        with patch("subprocess.run", return_value=mock_result):
            pid = get_process_by_pattern("test-pattern")
            assert pid == 12345

    def test_get_process_by_pattern_not_found(self) -> None:
        """Test get_process_by_pattern returns None when no process matches."""
        from app.services.service_monitor import get_process_by_pattern

        # Mock subprocess.run to return non-zero exit code
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            pid = get_process_by_pattern("nonexistent-pattern")
            assert pid is None

    def test_check_frontend_detects_production_next_process(self) -> None:
        """Test frontend checks accept the production Next.js start process."""
        with (
            patch(
                "app.services.service_monitor.get_service_status",
                return_value=Mock(
                    service_name="portfolio-frontend",
                    status="running",
                    pid=12345,
                    uptime_seconds=120,
                    memory_mb=256,
                    message="",
                ),
            ) as mock_get_service_status,
            patch("app.services.service_monitor.httpx.get") as mock_http_get,
        ):
            mock_http_get.return_value = Mock(status_code=200)

            status = check_frontend()

        mock_get_service_status.assert_called_once()
        assert mock_get_service_status.call_args.args[0] == "portfolio-frontend"
        assert mock_get_service_status.call_args.args[1] == SERVICE_PROCESS_PATTERNS["portfolio-frontend"]
        assert status.status == "running"

    def test_get_all_service_statuses_excludes_dev_companion(self) -> None:
        """Service monitor should only report active product services."""
        with (
            patch("app.services.service_monitor.check_redis", return_value=Mock()),
            patch("app.services.service_monitor.check_backend_api", return_value=Mock()),
            patch("app.services.service_monitor.check_hatchet_worker", return_value=Mock()),
            patch("app.services.service_monitor.check_frontend", return_value=Mock()),
        ):
            statuses = get_all_service_statuses(skip_slow_checks=True)

        assert set(statuses) == {
            "portfolio-redis",
            "portfolio-backend",
            "portfolio-hatchet-worker",
            "portfolio-frontend",
        }


class TestStatusEndpoints:
    """Tests for status API endpoints."""

    def test_health_endpoint_includes_services(self) -> None:
        """Test /health endpoint includes services field."""
        response = client.get("/health")
        assert response.status_code in [200, 503]
        data = response.json()

        # Basic health check fields
        assert "status" in data
        assert "checks" in data

        # New services field should be present (may be empty dict if not implemented yet)
        # This test will fail until we implement the services field
        assert "services" in data
        assert isinstance(data["services"], dict)

    def test_restart_all_services_endpoint_not_exposed(self) -> None:
        """Operator restart endpoint should not be exposed in the product API."""
        response = client.post("/api/status/restart-services")
        assert response.status_code == 404

    def test_restart_single_service_endpoint_not_exposed(self) -> None:
        """Per-service restart endpoint should not be exposed in the product API."""
        response = client.post("/api/status/services/backend/restart")
        assert response.status_code == 404
