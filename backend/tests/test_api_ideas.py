"""Integration tests for Ideas API endpoints."""

from __future__ import annotations

import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import DuckDBStorage


@pytest.fixture
def test_storage() -> DuckDBStorage:
    """Create a DuckDBStorage instance with a temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_api_ideas.duckdb"

    # Create fresh storage instance (bypass singleton)
    from app.storage.connection import ConnectionManager
    from app.storage.ingestion import IngestionManager
    from app.storage.metadata import MetadataManager
    from app.storage.queries import QueryManager
    from app.storage.schema import SchemaManager

    storage_inst = DuckDBStorage.__new__(DuckDBStorage)
    # ConnectionManager for PostgreSQL doesn't need db_path, uses DATABASE_URL
    storage_inst.connection_mgr = ConnectionManager()
    storage_inst.schema_mgr = SchemaManager(storage_inst.connection_mgr)
    storage_inst.metadata_mgr = MetadataManager(storage_inst.connection_mgr)
    storage_inst.ingestion_mgr = IngestionManager(
        storage_inst.connection_mgr, storage_inst.metadata_mgr
    )
    storage_inst.query_mgr = QueryManager(storage_inst.connection_mgr)
    storage_inst.schema_mgr.ensure_schema()

    yield storage_inst

    # Cleanup
    if db_path.exists():
        db_path.unlink()
    Path(temp_dir).rmdir()


@pytest.fixture
def client(test_storage: DuckDBStorage) -> TestClient:
    """Create a test client with patched storage."""
    # Patch storage at multiple import points
    with (
        patch("app.api.ideas.storage", test_storage),
        patch("app.api.ideas.get_storage", return_value=test_storage),
    ):
        yield TestClient(app)


def _insert_test_agent_run(
    storage: DuckDBStorage,
    run_id: str = "run-123",
    agent_type: str = "discovery",
    num_ideas: int = 5,
) -> None:
    """Helper to insert a test agent run."""
    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_runs (
                id, agent_type, status, started_at, completed_at,
                num_ideas, cost_usd, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                run_id,
                agent_type,
                "completed",
                datetime.now(),
                datetime.now(),
                num_ideas,
                0.05,
                None,
            ],
        )
        conn.commit()  # Commit explicitly for PostgreSQL


def _insert_test_idea(
    storage: DuckDBStorage,
    agent_run_id: str = "run-123",
    idea_type: str = "long",
    title: str = "Test Idea",
    confidence_score: float = 0.75,
    status: str = "pending",
) -> str:
    """Helper to insert a test idea and return its ID."""
    # Ensure agent run exists (idempotent)
    with storage.connection() as conn:
        existing = conn.execute("SELECT id FROM agent_runs WHERE id = ?", [agent_run_id]).fetchone()
        if not existing:
            _insert_test_agent_run(storage, run_id=agent_run_id)

    idea_id = str(uuid.uuid4())

    with storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO agent_ideas (
                id, agent_run_id, idea_type, title, thesis, action,
                confidence_score, risk_level, reward_estimate,
                portfolio_impact, data_needed, risks, status,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                idea_id,
                agent_run_id,
                idea_type,
                title,
                "Test thesis",
                "Buy AAPL",
                confidence_score,
                "medium",
                "10-15%",
                "Increases tech exposure",
                "Real-time price data",
                "Market volatility",
                status,
                datetime.now(),
                datetime.now(),
            ],
        )
        conn.commit()  # Commit explicitly for PostgreSQL
        return idea_id


def test_get_ideas_empty(client: TestClient) -> None:
    """Test GET /api/ideas with no ideas in database."""
    response = client.get("/api/ideas")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["ideas"] == []


def test_get_ideas_with_data(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test GET /api/ideas returns ideas sorted by confidence score."""
    # Insert test ideas with different confidence scores
    _insert_test_idea(
        test_storage,
        idea_type="long",
        title="High Confidence Idea",
        confidence_score=0.9,
    )
    _insert_test_idea(
        test_storage,
        idea_type="short",
        title="Medium Confidence Idea",
        confidence_score=0.6,
    )
    _insert_test_idea(
        test_storage,
        idea_type="hedge",
        title="Low Confidence Idea",
        confidence_score=0.4,
    )

    response = client.get("/api/ideas")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 3
    assert len(data["ideas"]) == 3

    # Verify sorted by confidence score DESC
    assert data["ideas"][0]["title"] == "High Confidence Idea"
    assert data["ideas"][0]["confidence_score"] == 0.9
    assert data["ideas"][1]["title"] == "Medium Confidence Idea"
    assert data["ideas"][2]["title"] == "Low Confidence Idea"


def test_get_ideas_filter_by_type(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test GET /api/ideas with idea_type filter."""
    _insert_test_idea(test_storage, idea_type="long", title="Long Idea")
    _insert_test_idea(test_storage, idea_type="short", title="Short Idea")
    _insert_test_idea(test_storage, idea_type="long", title="Another Long Idea")

    response = client.get("/api/ideas?idea_type=long")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert all(idea["idea_type"] == "long" for idea in data["ideas"])


def test_get_ideas_filter_by_status(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test GET /api/ideas with status filter."""
    _insert_test_idea(test_storage, title="Pending Idea", status="pending")
    _insert_test_idea(test_storage, title="Validated Idea", status="validated")
    _insert_test_idea(test_storage, title="Another Pending", status="pending")

    response = client.get("/api/ideas?status=pending")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert all(idea["status"] == "pending" for idea in data["ideas"])


def test_get_ideas_filter_by_type_and_status(
    client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test GET /api/ideas with multiple filters."""
    _insert_test_idea(test_storage, idea_type="long", title="Long Pending", status="pending")
    _insert_test_idea(test_storage, idea_type="long", title="Long Validated", status="validated")
    _insert_test_idea(test_storage, idea_type="short", title="Short Pending", status="pending")

    response = client.get("/api/ideas?idea_type=long&status=pending")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert data["ideas"][0]["title"] == "Long Pending"


def test_get_ideas_with_limit(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test GET /api/ideas with limit parameter."""
    for i in range(10):
        _insert_test_idea(test_storage, title=f"Idea {i}")

    response = client.get("/api/ideas?limit=5")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 5
    assert len(data["ideas"]) == 5


def test_get_idea_details_success(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test GET /api/ideas/{id} returns idea details."""
    idea_id = _insert_test_idea(test_storage, title="Detailed Test Idea", confidence_score=0.85)

    response = client.get(f"/api/ideas/{idea_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == idea_id
    assert data["title"] == "Detailed Test Idea"
    assert data["confidence_score"] == 0.85
    assert data["thesis"] == "Test thesis"
    assert data["action"] == "Buy AAPL"
    assert data["risk_level"] == "medium"
    assert data["status"] == "pending"


def test_get_idea_details_not_found(client: TestClient) -> None:
    """Test GET /api/ideas/{id} with non-existent ID."""
    response = client.get("/api/ideas/non-existent-id")

    assert response.status_code == 404
    assert response.json()["detail"] == "Idea not found"


def test_update_idea_status_success(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test PATCH /api/ideas/{id}/status updates status."""
    idea_id = _insert_test_idea(test_storage, status="pending")

    response = client.patch(f"/api/ideas/{idea_id}/status", json={"status": "validated"})

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == idea_id
    assert data["status"] == "validated"

    # Verify in database
    with test_storage.connection() as conn:
        result = conn.execute("SELECT status FROM agent_ideas WHERE id = ?", [idea_id]).fetchone()
        assert result[0] == "validated"


def test_update_idea_status_all_transitions(
    client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test PATCH /api/ideas/{id}/status with all valid status transitions."""
    idea_id = _insert_test_idea(test_storage, status="pending")

    # pending -> validated
    response = client.patch(f"/api/ideas/{idea_id}/status", json={"status": "validated"})
    assert response.status_code == 200
    assert response.json()["status"] == "validated"

    # validated -> executed
    response = client.patch(f"/api/ideas/{idea_id}/status", json={"status": "executed"})
    assert response.status_code == 200
    assert response.json()["status"] == "executed"

    # executed -> rejected (edge case)
    response = client.patch(f"/api/ideas/{idea_id}/status", json={"status": "rejected"})
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_update_idea_status_not_found(client: TestClient) -> None:
    """Test PATCH /api/ideas/{id}/status with non-existent ID."""
    response = client.patch("/api/ideas/non-existent-id/status", json={"status": "validated"})

    assert response.status_code == 404
    assert response.json()["detail"] == "Idea not found"


@patch("app.api.ideas.run_discovery_agent")
def test_generate_ideas_discovery_agent(
    mock_task: Mock, client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test POST /api/ideas/generate with discovery agent."""
    # Mock Celery task result
    mock_async_result = Mock()
    mock_async_result.id = "task-123"
    mock_task.apply_async.return_value = mock_async_result

    response = client.post("/api/ideas/generate", json={"agent_type": "discovery"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["task_id"] == "task-123"
    assert data["agent_type"] == "discovery"

    # Verify task was dispatched
    mock_task.apply_async.assert_called_once()


@patch("app.api.ideas.run_portfolio_analyzer")
def test_generate_ideas_portfolio_analyzer_agent(
    mock_task: Mock, client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test POST /api/ideas/generate with portfolio_analyzer agent."""
    # Mock Celery task result
    mock_async_result = Mock()
    mock_async_result.id = "task-456"
    mock_task.apply_async.return_value = mock_async_result

    response = client.post("/api/ideas/generate", json={"agent_type": "portfolio_analyzer"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
    assert data["task_id"] == "task-456"
    assert data["agent_type"] == "portfolio_analyzer"

    # Verify task was dispatched
    mock_task.apply_async.assert_called_once()


@patch("app.api.ideas.run_discovery_agent")
def test_generate_ideas_agent_failure(mock_task: Mock, client: TestClient) -> None:
    """Test POST /api/ideas/generate when Celery task dispatch fails."""
    # Mock task dispatch failure
    mock_task.apply_async.side_effect = Exception("Celery connection failed")

    response = client.post("/api/ideas/generate", json={"agent_type": "discovery"})

    assert response.status_code == 500


def test_generate_ideas_invalid_agent_type(client: TestClient) -> None:
    """Test POST /api/ideas/generate with invalid agent type."""
    # This should fail at Pydantic validation level
    response = client.post("/api/ideas/generate", json={"agent_type": "invalid"})

    assert response.status_code == 422  # Validation error


def test_ideas_api_fields_completeness(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test that all idea fields are present in API responses."""
    idea_id = _insert_test_idea(test_storage)

    response = client.get(f"/api/ideas/{idea_id}")

    assert response.status_code == 200
    data = response.json()

    # Verify all expected fields are present
    expected_fields = [
        "id",
        "agent_run_id",
        "idea_type",
        "title",
        "thesis",
        "action",
        "confidence_score",
        "risk_level",
        "reward_estimate",
        "portfolio_impact",
        "data_needed",
        "risks",
        "status",
        "created_at",
        "updated_at",
    ]

    for field in expected_fields:
        assert field in data, f"Missing field: {field}"
