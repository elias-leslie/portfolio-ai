"""Integration tests for Preferences API endpoints."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.storage import PortfolioStorage, get_storage


@pytest.fixture(autouse=True)
def test_storage() -> Iterator[PortfolioStorage]:
    """Get shared storage instance and ensure clean preferences state."""
    storage = get_storage()

    # Clear existing preferences so each test starts fresh
    with storage.connection() as conn:
        conn.execute("DELETE FROM user_preferences")
        conn.commit()

    yield storage

    # Cleanup
    with storage.connection() as conn:
        conn.execute("DELETE FROM user_preferences")
        conn.commit()


@pytest.fixture
def client() -> TestClient:
    """Create a test client."""
    return TestClient(app)


def test_get_preferences_creates_defaults(
    client: TestClient, test_storage: PortfolioStorage
) -> None:
    """Test GET /api/preferences creates default preferences if none exist."""
    response = client.get("/api/preferences")

    assert response.status_code == 200
    data = response.json()

    assert data["risk_tolerance"] == 5
    assert data["allow_long"] is True
    assert data["allow_short"] is False
    assert data["allow_options"] is False
    assert data["allow_crypto"] is False
    assert data["allow_futures"] is False
    assert data["max_position_size_pct"] == 10.0
    assert data["watchlist_show_news"] is True
    assert data["news_lookback_hours"] == 6


def test_get_preferences_returns_existing(
    client: TestClient, test_storage: PortfolioStorage
) -> None:
    """Test GET /api/preferences returns existing preferences."""
    # First create defaults, then update
    client.get("/api/preferences")
    client.post(
        "/api/preferences",
        json={
            "risk_tolerance": 8,
            "allow_short": True,
            "allow_options": True,
            "allow_crypto": True,
            "max_position_size_pct": 20.0,
            "watchlist_show_news": False,
        },
    )

    response = client.get("/api/preferences")

    assert response.status_code == 200
    data = response.json()
    assert data["risk_tolerance"] == 8
    assert data["allow_short"] is True
    assert data["allow_options"] is True
    assert data["allow_crypto"] is True
    assert data["max_position_size_pct"] == 20.0
    assert data["watchlist_show_news"] is False


def test_update_preferences_all_fields(client: TestClient) -> None:
    """Test POST /api/preferences updates all fields."""
    client.get("/api/preferences")

    update_data = {
        "risk_tolerance": 7,
        "allow_long": True,
        "allow_short": True,
        "allow_options": True,
        "allow_crypto": True,
        "allow_futures": True,
        "max_position_size_pct": 15.0,
        "watchlist_show_news": False,
        "news_lookback_hours": 12,
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
    assert data["watchlist_show_news"] is False
    assert data["news_lookback_hours"] == 12


def test_update_preferences_partial_update(client: TestClient) -> None:
    """Test POST /api/preferences with partial update (only some fields)."""
    client.get("/api/preferences")

    response = client.post("/api/preferences", json={"risk_tolerance": 9})

    assert response.status_code == 200
    data = response.json()

    assert data["risk_tolerance"] == 9
    assert data["allow_long"] is True
    assert data["allow_short"] is False
    assert data["max_position_size_pct"] == 10.0


def test_update_preferences_multiple_partial_updates(client: TestClient) -> None:
    """Test multiple partial updates preserve previously set values."""
    client.get("/api/preferences")

    response = client.post("/api/preferences", json={"risk_tolerance": 8})
    assert response.status_code == 200

    response = client.post("/api/preferences", json={"allow_short": True})
    assert response.status_code == 200
    data = response.json()

    assert data["risk_tolerance"] == 8
    assert data["allow_short"] is True


def test_update_preferences_risk_tolerance_validation(client: TestClient) -> None:
    """Test POST /api/preferences validates risk_tolerance range (1-10)."""
    client.get("/api/preferences")

    response = client.post("/api/preferences", json={"risk_tolerance": 0})
    assert response.status_code == 422

    response = client.post("/api/preferences", json={"risk_tolerance": 11})
    assert response.status_code == 422

    response = client.post("/api/preferences", json={"risk_tolerance": 1})
    assert response.status_code == 200

    response = client.post("/api/preferences", json={"risk_tolerance": 10})
    assert response.status_code == 200


def test_update_preferences_max_position_size_validation(client: TestClient) -> None:
    """Test POST /api/preferences validates max_position_size_pct range (0-100)."""
    client.get("/api/preferences")

    response = client.post("/api/preferences", json={"max_position_size_pct": -5.0})
    assert response.status_code == 422

    response = client.post("/api/preferences", json={"max_position_size_pct": 150.0})
    assert response.status_code == 422

    response = client.post("/api/preferences", json={"max_position_size_pct": 0.1})
    assert response.status_code == 200

    response = client.post("/api/preferences", json={"max_position_size_pct": 100.0})
    assert response.status_code == 200


def test_update_preferences_boolean_fields(client: TestClient) -> None:
    """Test POST /api/preferences updates boolean fields correctly."""
    client.get("/api/preferences")

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
    assert data["allow_short"] is True
    assert data["allow_options"] is True
    assert data["allow_crypto"] is True
    assert data["allow_futures"] is True

    response = client.post(
        "/api/preferences",
        json={"allow_short": False, "allow_options": False, "allow_crypto": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["allow_long"] is True
    assert data["allow_short"] is False
    assert data["allow_options"] is False
    assert data["allow_crypto"] is False
    assert data["allow_futures"] is True


def test_preferences_response_structure(client: TestClient) -> None:
    """Test that preferences responses have correct structure and field types."""
    response = client.get("/api/preferences")

    assert response.status_code == 200
    data = response.json()

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

    assert isinstance(data["risk_tolerance"], int)
    assert isinstance(data["allow_long"], bool)
    assert isinstance(data["allow_short"], bool)
    assert isinstance(data["allow_options"], bool)
    assert isinstance(data["allow_crypto"], bool)
    assert isinstance(data["allow_futures"], bool)
    assert isinstance(data["max_position_size_pct"], float)


def test_get_preferences_returns_default_timezone(client: TestClient) -> None:
    """Test GET /api/preferences returns display_timezone field with default value."""
    response = client.get("/api/preferences")

    assert response.status_code == 200
    data = response.json()

    assert "display_timezone" in data
    assert data["display_timezone"] == "America/New_York"


def test_update_preferences_timezone(client: TestClient) -> None:
    """Test POST /api/preferences updates display_timezone."""
    client.get("/api/preferences")

    response = client.post(
        "/api/preferences", json={"display_timezone": "America/Los_Angeles"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["display_timezone"] == "America/Los_Angeles"


def test_update_preferences_timezone_validation(client: TestClient) -> None:
    """Test POST /api/preferences validates timezone values (USA timezones only)."""
    client.get("/api/preferences")

    response = client.post(
        "/api/preferences", json={"display_timezone": "Europe/London"}
    )
    assert response.status_code == 422

    response = client.post(
        "/api/preferences", json={"display_timezone": "Invalid/Timezone"}
    )
    assert response.status_code == 422

    valid_timezones = [
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "America/Anchorage",
        "Pacific/Honolulu",
    ]

    for tz in valid_timezones:
        response = client.post("/api/preferences", json={"display_timezone": tz})
        assert response.status_code == 200, f"Failed for timezone: {tz}"
        data = response.json()
        assert data["display_timezone"] == tz


def test_update_preferences_timezone_persists(client: TestClient) -> None:
    """Test timezone preference persists across multiple updates."""
    client.get("/api/preferences")

    response = client.post(
        "/api/preferences", json={"display_timezone": "America/Chicago"}
    )
    assert response.status_code == 200

    response = client.post("/api/preferences", json={"risk_tolerance": 8})
    assert response.status_code == 200
    data = response.json()

    assert data["display_timezone"] == "America/Chicago"
    assert data["risk_tolerance"] == 8
