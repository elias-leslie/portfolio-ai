"""API tests for the home dashboard endpoints."""

from __future__ import annotations

from unittest.mock import Mock

from fastapi.testclient import TestClient

from app.api.home import HomeActionQueueResponse
from app.main import app


def test_home_action_queue_returns_actions(monkeypatch) -> None:
    client = TestClient(app)

    monkeypatch.setattr(
        "app.api.home._home_action_service",
        lambda: Mock(
            get_action_queue=Mock(
                return_value=HomeActionQueueResponse(
                    generated_at="2026-03-10T00:00:00Z",
                    actions=[
                        {
                            "id": "action-1",
                            "source": "recommendations",
                            "category": "investing",
                            "priority": "high",
                            "title": "Review NVDA setup",
                            "detail": "Signal strength 8/10 with both thesis and strategy support.",
                            "action_label": "Open symbol",
                            "href": "/symbols/NVDA",
                            "symbol": "NVDA",
                            "badge": "High",
                        }
                    ],
                    summary="1 prioritized action ready.",
                )
            )
        ),
    )

    response = client.get("/api/home/action-queue")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"] == "1 prioritized action ready."
    assert payload["actions"][0]["href"] == "/symbols/NVDA"
    assert payload["actions"][0]["category"] == "investing"


