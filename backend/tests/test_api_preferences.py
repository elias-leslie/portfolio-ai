"""Integration tests for Preferences API endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import DuckDBStorage


@pytest.fixture
def test_storage() -> DuckDBStorage:
    """Create a DuckDBStorage instance with a temporary database."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_api_preferences.duckdb"

    # Create fresh storage instance (bypass singleton)
    from app.storage.connection import ConnectionManager
    from app.storage.ingestion import IngestionManager
    from app.storage.metadata import MetadataManager
    from app.storage.queries import QueryManager
    from app.storage.schema import SchemaManager

    storage_inst = DuckDBStorage.__new__(DuckDBStorage)
    storage_inst.connection_mgr = ConnectionManager(db_path=db_path)
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
        patch("app.api.preferences.storage", test_storage),
        patch("app.api.preferences.get_storage", return_value=test_storage),
    ):
        yield TestClient(app)


def test_get_preferences_creates_defaults(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test GET /api/preferences creates default preferences if none exist."""
    # Verify no preferences exist
    with test_storage.connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM user_preferences").fetchone()
        assert result[0] == 0

    response = client.get("/api/preferences")

    assert response.status_code == 200
    data = response.json()

    # Verify default values
    assert data["risk_tolerance"] == 5
    assert data["allow_long"] is True
    assert data["allow_short"] is False
    assert data["allow_options"] is False
    assert data["allow_crypto"] is False
    assert data["allow_futures"] is False
    assert data["max_position_size_pct"] == 10.0

    # Verify defaults were saved to database
    with test_storage.connection() as conn:
        result = conn.execute("SELECT COUNT(*) FROM user_preferences").fetchone()
        assert result[0] == 1


def test_get_preferences_returns_existing(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test GET /api/preferences returns existing preferences."""
    import uuid
    from datetime import datetime

    # Insert custom preferences
    user_id = str(uuid.uuid4())
    with test_storage.connection() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (
                id, risk_tolerance, allow_long, allow_short,
                allow_options, allow_crypto, allow_futures,
                max_position_size_pct, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                user_id,
                8,
                True,
                True,
                True,
                True,
                False,
                20.0,
                datetime.now(),
                datetime.now(),
            ],
        )

    response = client.get("/api/preferences")

    assert response.status_code == 200
    data = response.json()

    assert data["risk_tolerance"] == 8
    assert data["allow_long"] is True
    assert data["allow_short"] is True
    assert data["allow_options"] is True
    assert data["allow_crypto"] is True
    assert data["allow_futures"] is False
    assert data["max_position_size_pct"] == 20.0


def test_update_preferences_all_fields(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test POST /api/preferences updates all fields."""
    # First get/create defaults
    client.get("/api/preferences")

    # Update all fields
    update_data = {
        "risk_tolerance": 7,
        "allow_long": True,
        "allow_short": True,
        "allow_options": True,
        "allow_crypto": True,
        "allow_futures": True,
        "max_position_size_pct": 15.0,
    }

    response = client.post("/api/preferences", json=update_data)

    assert response.status_code == 200
    data = response.json()

    assert data["risk_tolerance"] == 7
    assert data["allow_long"] is True
    assert data["allow_short"] is True
    assert data["allow_options"] is True
    assert data["allow_crypto"] is True
    assert data["allow_futures"] is True
    assert data["max_position_size_pct"] == 15.0

    # Verify persisted to database
    with test_storage.connection() as conn:
        result = conn.execute(
            "SELECT risk_tolerance, max_position_size_pct FROM user_preferences"
        ).fetchone()
        assert result[0] == 7
        assert result[1] == 15.0


def test_update_preferences_partial_update(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test POST /api/preferences with partial update (only some fields)."""
    # Create defaults first
    client.get("/api/preferences")

    # Update only risk tolerance
    update_data = {"risk_tolerance": 9}

    response = client.post("/api/preferences", json=update_data)

    assert response.status_code == 200
    data = response.json()

    # Updated field
    assert data["risk_tolerance"] == 9

    # Other fields should remain at defaults
    assert data["allow_long"] is True
    assert data["allow_short"] is False
    assert data["allow_options"] is False
    assert data["allow_crypto"] is False
    assert data["allow_futures"] is False
    assert data["max_position_size_pct"] == 10.0


def test_update_preferences_multiple_partial_updates(
    client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test multiple partial updates preserve previously set values."""
    # Create defaults
    client.get("/api/preferences")

    # First update
    response = client.post("/api/preferences", json={"risk_tolerance": 8})
    assert response.status_code == 200

    # Second update (different field)
    response = client.post("/api/preferences", json={"allow_short": True})
    assert response.status_code == 200
    data = response.json()

    # Both updates should be preserved
    assert data["risk_tolerance"] == 8
    assert data["allow_short"] is True


def test_update_preferences_risk_tolerance_validation(
    client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test POST /api/preferences validates risk_tolerance range (1-10)."""
    # Create defaults first
    client.get("/api/preferences")

    # Try to set risk tolerance too low
    response = client.post("/api/preferences", json={"risk_tolerance": 0})
    assert response.status_code == 422

    # Try to set risk tolerance too high
    response = client.post("/api/preferences", json={"risk_tolerance": 11})
    assert response.status_code == 422

    # Valid values should work
    response = client.post("/api/preferences", json={"risk_tolerance": 1})
    assert response.status_code == 200

    response = client.post("/api/preferences", json={"risk_tolerance": 10})
    assert response.status_code == 200


def test_update_preferences_max_position_size_validation(
    client: TestClient, test_storage: DuckDBStorage
) -> None:
    """Test POST /api/preferences validates max_position_size_pct range (0-100)."""
    # Create defaults first
    client.get("/api/preferences")

    # Try to set negative value
    response = client.post("/api/preferences", json={"max_position_size_pct": -5.0})
    assert response.status_code == 422

    # Try to set value over 100
    response = client.post("/api/preferences", json={"max_position_size_pct": 150.0})
    assert response.status_code == 422

    # Valid values should work
    response = client.post("/api/preferences", json={"max_position_size_pct": 0.1})
    assert response.status_code == 200

    response = client.post("/api/preferences", json={"max_position_size_pct": 100.0})
    assert response.status_code == 200


def test_update_preferences_boolean_fields(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test POST /api/preferences updates boolean fields correctly."""
    # Create defaults
    client.get("/api/preferences")

    # Enable all trading types
    response = client.post(
        "/api/preferences",
        json={
            "allow_long": True,
            "allow_short": True,
            "allow_options": True,
            "allow_crypto": True,
            "allow_futures": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["allow_long"] is True
    assert data["allow_short"] is True
    assert data["allow_options"] is True
    assert data["allow_crypto"] is True
    assert data["allow_futures"] is True

    # Disable shorts, options, and crypto
    response = client.post(
        "/api/preferences",
        json={"allow_short": False, "allow_options": False, "allow_crypto": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["allow_long"] is True  # Should remain True
    assert data["allow_short"] is False
    assert data["allow_options"] is False
    assert data["allow_crypto"] is False
    assert data["allow_futures"] is True  # Should remain True


def test_preferences_response_structure(client: TestClient, test_storage: DuckDBStorage) -> None:
    """Test that preferences responses have correct structure and field types."""
    response = client.get("/api/preferences")

    assert response.status_code == 200
    data = response.json()

    # Verify all required fields are present
    required_fields = [
        "risk_tolerance",
        "allow_long",
        "allow_short",
        "allow_options",
        "allow_crypto",
        "allow_futures",
        "max_position_size_pct",
    ]

    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    # Verify field types
    assert isinstance(data["risk_tolerance"], int)
    assert isinstance(data["allow_long"], bool)
    assert isinstance(data["allow_short"], bool)
    assert isinstance(data["allow_options"], bool)
    assert isinstance(data["allow_crypto"], bool)
    assert isinstance(data["allow_futures"], bool)
    assert isinstance(data["max_position_size_pct"], float)
