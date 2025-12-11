"""Unit tests for AI agent action endpoints (FEAT-036).

Tests agent execution endpoints with basic mocking:
- POST /api/ideas/generate - Trigger agent runs (discovery, portfolio_analyzer)
- Input validation
- Error handling
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_celery_task() -> MagicMock:
    """Mock Celery task with ID."""
    mock = MagicMock()
    mock.id = "celery-task-123"
    return mock


# =============================================================================
# Test Generate Ideas Endpoint (Agent Trigger)
# =============================================================================


class TestGenerateIdeasEndpoint:
    """Tests for POST /api/ideas/generate endpoint."""

    def test_trigger_discovery_agent(self, mock_celery_task: MagicMock) -> None:
        """Test triggering discovery agent."""
        with patch("app.api.ideas.run_discovery_agent") as mock_discovery:
            mock_discovery.apply_async.return_value = mock_celery_task

            response = client.post(
                "/api/ideas/generate",
                json={"agent_type": "discovery"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"  # Actual API returns "running"
            assert data["task_id"] == "celery-task-123"
            assert data["agent_type"] == "discovery"

            # Verify Celery task dispatched
            mock_discovery.apply_async.assert_called_once()

    def test_trigger_portfolio_analyzer_agent(
        self, mock_celery_task: MagicMock
    ) -> None:
        """Test triggering portfolio analyzer agent."""
        with patch("app.api.ideas.run_portfolio_analyzer") as mock_analyzer:
            mock_analyzer.apply_async.return_value = mock_celery_task

            response = client.post(
                "/api/ideas/generate",
                json={"agent_type": "portfolio_analyzer"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "running"
            assert data["task_id"] == "celery-task-123"
            assert data["agent_type"] == "portfolio_analyzer"

            # Verify Celery task dispatched
            mock_analyzer.apply_async.assert_called_once()

    def test_trigger_invalid_agent_type(self) -> None:
        """Test triggering with invalid agent type."""
        response = client.post(
            "/api/ideas/generate",
            json={"agent_type": "invalid_agent"},
        )

        # Invalid literal value returns 422 Unprocessable Entity
        assert response.status_code == 422

    def test_trigger_without_agent_type(self) -> None:
        """Test triggering without agent_type field."""
        response = client.post(
            "/api/ideas/generate",
            json={},
        )

        # Should fail validation (422 Unprocessable Entity)
        assert response.status_code == 422

    def test_trigger_agent_celery_error(self) -> None:
        """Test handling of Celery task dispatch errors."""
        with patch("app.api.ideas.run_discovery_agent") as mock_discovery:
            mock_discovery.apply_async.side_effect = Exception("Celery connection failed")

            response = client.post(
                "/api/ideas/generate",
                json={"agent_type": "discovery"},
            )

            assert response.status_code == 500
            assert "Failed to dispatch agent task" in response.json()["detail"]


# =============================================================================
# Test Ideas List Endpoint
# =============================================================================


class TestIdeasListEndpoint:
    """Tests for GET /api/ideas endpoint."""

    def test_get_ideas_empty_list(self) -> None:
        """Test getting ideas when none exist."""
        with patch("app.api.ideas.storage") as mock_storage:
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)
            mock_conn.execute.return_value.fetchall.return_value = []
            mock_storage.connection.return_value = mock_conn

            response = client.get("/api/ideas/")

            assert response.status_code == 200
            data = response.json()
            assert "ideas" in data
            assert "count" in data
            assert len(data["ideas"]) == 0
            assert data["count"] == 0

    def test_get_ideas_with_filters(self) -> None:
        """Test getting ideas with type and status filters."""
        with patch("app.api.ideas.storage") as mock_storage:
            mock_conn = MagicMock()
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=None)
            mock_conn.execute.return_value.fetchall.return_value = []
            mock_storage.connection.return_value = mock_conn

            response = client.get("/api/ideas/?idea_type=swing_trade&status=pending&limit=10")

            assert response.status_code == 200

            # Verify query was built with filters
            call_args = mock_conn.execute.call_args
            query = call_args[0][0]
            params = call_args[0][1]

            assert "idea_type = ?" in query
            assert "status = ?" in query
            assert "swing_trade" in params
            assert "pending" in params
            assert 10 in params


# =============================================================================
# Test Error Handling
# =============================================================================


class TestAgentActionsErrorHandling:
    """Tests for error handling in agent action endpoints."""

    def test_generate_ideas_database_error(self) -> None:
        """Test handling database errors during idea generation logging."""
        with patch("app.api.ideas.run_discovery_agent") as mock_discovery:
            # Simulate Celery task failure
            mock_discovery.apply_async.side_effect = Exception("Database unavailable")

            response = client.post(
                "/api/ideas/generate",
                json={"agent_type": "discovery"},
            )

            assert response.status_code == 500
