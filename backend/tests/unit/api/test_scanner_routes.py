"""L2 scanner API contract tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.scanner_routes import router as scanner_router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(scanner_router)
    return TestClient(app)


def test_trigger_run_queues_scanner_workflow() -> None:
    with patch(
        "app.api.scanner_routes._enqueue_scanner_workflow",
        new_callable=AsyncMock,
    ) as enqueue:
        client = _build_client()
        resp = client.post("/api/scanner/run")

    assert resp.status_code == 202
    assert resp.json() == {
        "status": "queued",
        "workflow": "portfolio-scanner",
        "message": "Scanner run queued. Committee fan-out will follow scanner completion.",
    }
    enqueue.assert_awaited_once_with()


def test_trigger_run_returns_503_when_enqueue_fails() -> None:
    with patch(
        "app.api.scanner_routes._enqueue_scanner_workflow",
        new_callable=AsyncMock,
        side_effect=RuntimeError("hatchet unavailable"),
    ):
        client = _build_client()
        resp = client.post("/api/scanner/run")

    assert resp.status_code == 503
    assert resp.json()["detail"] == "scanner_trigger_failed"
