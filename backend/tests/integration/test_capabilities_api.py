"""Integration tests for Capabilities API endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_data() -> None:
    """Setup test data for capabilities tests.

    Note: We'll use the actual scan task to populate data, or manually insert test data.
    For now, we test with empty database state.
    """
    # Clean up any existing test data
    from app.storage.connection import get_connection_manager

    conn_mgr = get_connection_manager()
    with conn_mgr.connection() as conn:
        # Clean capability tables
        conn.execute("TRUNCATE TABLE capability_notes CASCADE")
        conn.execute("TRUNCATE TABLE capability_insights CASCADE")
        conn.execute("TRUNCATE TABLE api_capabilities CASCADE")
        conn.execute("TRUNCATE TABLE celery_capabilities CASCADE")
        conn.execute("TRUNCATE TABLE db_capabilities CASCADE")
        conn.commit()


class TestGetCapabilities:
    """Test GET /api/capabilities endpoint."""

    def test_get_capabilities_all_empty(self) -> None:
        """Test getting all capabilities when none exist."""
        response = client.get("/api/capabilities?type=all&limit=50&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "capabilities" in data
        assert data["total"] == 0
        assert data["capabilities"] == []

    def test_get_capabilities_db_type(self) -> None:
        """Test filtering by db type."""
        response = client.get("/api/capabilities?type=db&limit=50&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "capabilities" in data

    def test_get_capabilities_invalid_type(self) -> None:
        """Test invalid type parameter."""
        response = client.get("/api/capabilities?type=invalid")

        assert response.status_code == 400
        assert "invalid type" in response.json()["detail"].lower()

    def test_get_capabilities_with_pagination(self) -> None:
        """Test pagination parameters."""
        response = client.get("/api/capabilities?type=all&limit=10&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert len(data["capabilities"]) <= 10

    def test_get_capabilities_with_category_filter(self) -> None:
        """Test filtering by category."""
        response = client.get("/api/capabilities?type=all&category=market_data")

        assert response.status_code == 200
        data = response.json()
        # Should return empty since no data exists yet
        assert data["total"] == 0


class TestGetCapabilityDetail:
    """Test GET /api/capabilities/{type}/{id} endpoint."""

    def test_get_capability_detail_not_found(self) -> None:
        """Test getting non-existent capability."""
        response = client.get("/api/capabilities/db/99999")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_capability_detail_invalid_type(self) -> None:
        """Test invalid capability type."""
        # FastAPI will validate this and return 422 Unprocessable Entity
        response = client.get("/api/capabilities/invalid/1")

        assert response.status_code == 422


class TestGetInsights:
    """Test GET /api/capabilities/insights endpoint."""

    def test_get_insights_empty(self) -> None:
        """Test getting insights when none exist."""
        response = client.get("/api/capabilities/insights?limit=50&offset=0")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "insights" in data
        assert data["total"] == 0

    def test_get_insights_with_status_filter(self) -> None:
        """Test filtering insights by status."""
        response = client.get("/api/capabilities/insights?status=pending")

        assert response.status_code == 200
        data = response.json()
        assert "insights" in data

    def test_get_insights_with_severity_filter(self) -> None:
        """Test filtering insights by severity."""
        response = client.get("/api/capabilities/insights?severity=critical")

        assert response.status_code == 200
        data = response.json()
        assert "insights" in data

    def test_get_insights_with_type_filter(self) -> None:
        """Test filtering insights by insight type."""
        response = client.get("/api/capabilities/insights?type=freshness")

        assert response.status_code == 200
        data = response.json()
        assert "insights" in data


class TestReviewInsight:
    """Test POST /api/capabilities/insights/{id}/review endpoint."""

    def test_review_insight_not_found(self) -> None:
        """Test reviewing non-existent insight."""
        response = client.post(
            "/api/capabilities/insights/99999/review",
            json={
                "status": "confirmed",
                "status_reason": "Test reason",
                "reviewed_by": "test_user",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_review_insight_invalid_status(self) -> None:
        """Test invalid status value."""
        response = client.post(
            "/api/capabilities/insights/1/review",
            json={
                "status": "invalid_status",
                "status_reason": "Test",
                "reviewed_by": "test",
            },
        )

        # Pydantic validation error
        assert response.status_code == 422


class TestCreateNote:
    """Test POST /api/capabilities/notes endpoint."""

    def test_create_note_invalid_capability(self) -> None:
        """Test creating note for non-existent capability."""
        response = client.post(
            "/api/capabilities/notes",
            json={
                "capability_type": "db",
                "capability_id": 99999,
                "note_type": "observation",
                "note": "Test note",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_note_invalid_insight(self) -> None:
        """Test creating note for non-existent insight."""
        response = client.post(
            "/api/capabilities/notes",
            json={
                "capability_type": "db",
                "insight_id": 99999,
                "note_type": "observation",
                "note": "Test note",
            },
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_create_note_invalid_type(self) -> None:
        """Test creating note with invalid type."""
        response = client.post(
            "/api/capabilities/notes",
            json={
                "capability_type": "db",
                "note_type": "invalid_type",
                "note": "Test note",
            },
        )

        # Pydantic validation error
        assert response.status_code == 422


class TestGetNotes:
    """Test GET /api/capabilities/notes endpoint."""

    def test_get_notes_empty(self) -> None:
        """Test getting notes when none exist."""
        response = client.get("/api/capabilities/notes")

        assert response.status_code == 200
        data = response.json()
        assert "notes" in data
        assert data["notes"] == []

    def test_get_notes_with_capability_filter(self) -> None:
        """Test filtering notes by capability."""
        response = client.get("/api/capabilities/notes?capability_type=db&capability_id=1")

        assert response.status_code == 200
        data = response.json()
        assert "notes" in data

    def test_get_notes_with_insight_filter(self) -> None:
        """Test filtering notes by insight."""
        response = client.get("/api/capabilities/notes?insight_id=1")

        assert response.status_code == 200
        data = response.json()
        assert "notes" in data


class TestTriggerScan:
    """Test POST /api/capabilities/scan endpoint."""

    def test_trigger_scan_success(self) -> None:
        """Test triggering manual scan."""
        response = client.post("/api/capabilities/scan")

        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert "status" in data
        assert "message" in data
        assert data["status"] == "queued"


class TestCapabilitiesAPIWithData:
    """Test API endpoints with actual data populated.

    These tests run a scan first to populate data, then test queries.
    """

    def test_full_workflow(self) -> None:
        """Test complete workflow: scan -> query -> review -> note.

        This is a smoke test to ensure all endpoints work together.
        """
        # 1. Trigger scan
        scan_response = client.post("/api/capabilities/scan")
        assert scan_response.status_code == 200

        # Wait a moment for scan to complete (in real tests, we'd mock this)
        # For now, we just verify the endpoint works

        # 2. Query capabilities
        caps_response = client.get("/api/capabilities?type=all&limit=10")
        assert caps_response.status_code == 200

        # 3. Query insights
        insights_response = client.get("/api/capabilities/insights")
        assert insights_response.status_code == 200

        # 4. Query notes
        notes_response = client.get("/api/capabilities/notes")
        assert notes_response.status_code == 200
