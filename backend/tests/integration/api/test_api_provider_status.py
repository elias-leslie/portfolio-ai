"""Runtime-schema coverage for local financial-provider status endpoints."""

from fastapi.testclient import TestClient

from app.main import app


def test_snaptrade_status_executes_against_the_current_schema() -> None:
    response = TestClient(app).get("/api/snaptrade/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["access_mode"] == "read_only"
    assert isinstance(payload["account_count"], int)
