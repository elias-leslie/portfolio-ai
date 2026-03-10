"""Route coverage for market event filters and validation."""

from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.market_events import MarketEventsResponse


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    events_router_module = importlib.import_module("app.api.market.events_router")

    def fake_get_events(**_: object) -> MarketEventsResponse:
        return MarketEventsResponse(events=[], total=0, start_date=None, end_date=None)

    monkeypatch.setattr(events_router_module, "svc_get_events", fake_get_events)
    return TestClient(app)


def test_get_market_events_rejects_invalid_start_date(client: TestClient) -> None:
    response = client.get("/api/market/events?start_date=not-a-date")

    assert response.status_code == 422
    assert "start_date" in response.text


def test_get_market_events_rejects_invalid_event_type(client: TestClient) -> None:
    response = client.get("/api/market/events?event_types=invalid")

    assert response.status_code == 400
    assert "Invalid event_type" in response.json()["detail"]


def test_create_market_event_rejects_invalid_event_date(client: TestClient) -> None:
    response = client.post(
        "/api/market/events"
        "?event_type=fomc_decision"
        "&event_date=tomorrowish"
        "&title=Fed meeting"
    )

    assert response.status_code == 422
    assert "event_date" in response.text
