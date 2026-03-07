"""Regression tests for the narrowed public product API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

REMOVED_PREFIXES = (
    "/api/agents",
    "/api/analytics",
    "/api/automation",
    "/api/backtest",
    "/api/backup",
    "/api/capabilities",
    "/api/cross-validation",
    "/api/db",
    "/api/indicators",
    "/api/layouts",
    "/api/maintenance",
    "/api/ml",
    "/api/paper-trades",
    "/api/paper-trading",
    "/api/settings/profiles",
    "/api/sources",
    "/api/status",
    "/api/strategies",
    "/api/strategy-seeds",
    "/api/valuation",
    "/api/workflows",
)


def test_openapi_excludes_removed_non_core_prefixes() -> None:
    """The public app should no longer publish non-core product routes."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]

    for prefix in REMOVED_PREFIXES:
        assert not any(path == prefix or path.startswith(f"{prefix}/") for path in paths), prefix
