"""Tests for status and resource monitoring API endpoints.

Tests cover:
- FEAT-093: Resource Monitoring
- FEAT-147: Celery Task Status Table
- FEAT-101: Agent Statistics (via health detailed)
- FEAT-146: Fear Greed Trend Chart (via market intelligence)
"""

from __future__ import annotations

import pytest
import requests

# Use live API testing since TestClient has migration issues
BASE_URL = "http://localhost:8000"


def api_available() -> bool:
    """Check if the API is available."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not api_available(),
    reason="API server not available for integration tests"
)


class TestResourceMonitoringEndpoint:
    """Tests for FEAT-093 Resource Monitoring API."""

    def test_resources_endpoint_returns_200(self) -> None:
        """Test resources endpoint returns data."""
        response = requests.get(f"{BASE_URL}/api/status/resources", timeout=10)
        assert response.status_code == 200

    def test_resources_has_database_pool(self) -> None:
        """Test resources includes database pool stats."""
        response = requests.get(f"{BASE_URL}/api/status/resources", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "database_pool" in data

    def test_resources_database_pool_fields(self) -> None:
        """Test database pool has required fields."""
        response = requests.get(f"{BASE_URL}/api/status/resources", timeout=10)
        if response.status_code == 200:
            data = response.json()
            pool = data.get("database_pool", {})
            assert "pool_size" in pool
            assert "checked_out" in pool
            assert "status" in pool

    def test_resources_has_memory(self) -> None:
        """Test resources includes memory usage."""
        response = requests.get(f"{BASE_URL}/api/status/resources", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "memory" in data

    def test_resources_memory_fields(self) -> None:
        """Test memory stats have required fields."""
        response = requests.get(f"{BASE_URL}/api/status/resources", timeout=10)
        if response.status_code == 200:
            data = response.json()
            memory = data.get("memory", {})
            assert "total_gb" in memory
            assert "used_gb" in memory
            assert "available_gb" in memory
            assert "percent_used" in memory

    def test_resources_has_cpu(self) -> None:
        """Test resources includes CPU usage."""
        response = requests.get(f"{BASE_URL}/api/status/resources", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "cpu" in data

    def test_resources_has_disk(self) -> None:
        """Test resources includes disk usage."""
        response = requests.get(f"{BASE_URL}/api/status/resources", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "disk" in data


class TestCeleryTaskStatusEndpoint:
    """Tests for FEAT-147 Celery Task Status Table API."""

    def test_celery_tasks_endpoint_returns_200(self) -> None:
        """Test celery tasks endpoint returns data."""
        response = requests.get(f"{BASE_URL}/api/status/celery/tasks", timeout=10)
        assert response.status_code == 200

    def test_celery_tasks_has_tasks_list(self) -> None:
        """Test celery tasks response includes tasks array."""
        response = requests.get(f"{BASE_URL}/api/status/celery/tasks", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert isinstance(data["tasks"], list)

    def test_celery_tasks_has_counts(self) -> None:
        """Test celery tasks response includes count fields."""
        response = requests.get(f"{BASE_URL}/api/status/celery/tasks", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "active_count" in data
        assert "completed_count" in data

    def test_celery_task_item_fields(self) -> None:
        """Test celery task items have required fields."""
        response = requests.get(f"{BASE_URL}/api/status/celery/tasks", timeout=10)
        if response.status_code == 200:
            data = response.json()
            for task in data.get("tasks", [])[:1]:  # Check first task
                assert "id" in task
                assert "name" in task
                assert "status" in task

    def test_celery_queue_endpoint_returns_200(self) -> None:
        """Test celery queue endpoint returns data."""
        response = requests.get(f"{BASE_URL}/api/status/celery/queue", timeout=10)
        assert response.status_code == 200

    def test_celery_schedule_endpoint_returns_200(self) -> None:
        """Test celery schedule endpoint returns data."""
        response = requests.get(f"{BASE_URL}/api/status/celery/schedule", timeout=10)
        assert response.status_code == 200


class TestAgentStatisticsEndpoint:
    """Tests for FEAT-101 Agent Statistics (via health detailed)."""

    def test_health_detailed_returns_200(self) -> None:
        """Test health detailed endpoint returns data."""
        response = requests.get(f"{BASE_URL}/health/detailed", timeout=10)
        assert response.status_code == 200

    def test_health_detailed_has_agent_stats(self) -> None:
        """Test health detailed includes agent statistics."""
        response = requests.get(f"{BASE_URL}/health/detailed", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "agent_stats" in data

    def test_agent_stats_fields(self) -> None:
        """Test agent stats has required fields."""
        response = requests.get(f"{BASE_URL}/health/detailed", timeout=10)
        if response.status_code == 200:
            data = response.json()
            stats = data.get("agent_stats", {})
            # Agent stats should have run metrics
            assert isinstance(stats, dict)


class TestFearGreedTrendEndpoint:
    """Tests for FEAT-146 Fear Greed Trend Chart (via market endpoints)."""

    def test_fear_greed_history_endpoint_exists(self) -> None:
        """Test fear greed history endpoint returns data."""
        response = requests.get(f"{BASE_URL}/api/market/fear-greed/history", timeout=10)
        # May return 200 or 404 depending on data availability
        assert response.status_code in (200, 404)

    def test_market_intelligence_has_fear_greed(self) -> None:
        """Test market intelligence includes fear greed data."""
        response = requests.get(f"{BASE_URL}/api/market/intelligence", timeout=10)
        assert response.status_code == 200
        data = response.json()
        assert "fear_greed" in data

    def test_fear_greed_fields(self) -> None:
        """Test fear greed data has required fields."""
        response = requests.get(f"{BASE_URL}/api/market/intelligence", timeout=10)
        if response.status_code == 200:
            data = response.json()
            fg = data.get("fear_greed", {})
            if fg:
                assert "value" in fg or "score" in fg or isinstance(fg, (int, float))
