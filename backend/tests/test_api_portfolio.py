"""Integration tests for Portfolio API endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint() -> None:
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint() -> None:
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data


def test_create_account() -> None:
    """Test creating a new account."""
    response = client.post(
        "/api/portfolio/account",
        json={"name": "API Test IRA", "account_type": "IRA"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "API Test IRA"
    assert data["account_type"] == "IRA"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
