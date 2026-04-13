"""Unit tests for Jenny portfolio routes."""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from fastapi.testclient import TestClient
from pytest_mock import MockerFixture

from app.main import app

client = TestClient(app)


def _dashboard_payload() -> dict[str, Any]:
    return {
        "routines": [
            {
                "id": "routine-1",
                "routine_type": "daily_operator",
                "status": "completed",
                "triggered_by": "manual",
                "summary": "Jenny reviewed 4 symbols.",
                "agents_used": ["persona", "analyst", "critic"],
                "symbols_scanned": 4,
                "notifications_created": 2,
                "started_at": "2026-03-07T12:00:00+00:00",
                "completed_at": "2026-03-07T12:05:00+00:00",
                "metadata": {},
            }
        ],
        "notifications": [
            {
                "id": "note-1",
                "routine_id": "routine-1",
                "symbol": "AAPL",
                "category": "position_trim",
                "severity": "warning",
                "status": "open",
                "title": "AAPL: Trim this position",
                "detail": "Position is oversized.",
                "recommendation": "Review trim size.",
                "created_at": "2026-03-07T12:05:00+00:00",
                "acknowledged_at": None,
                "metadata": {},
            }
        ],
        "symbol_reviews": [],
        "trade_reviews": [],
        "scorecards": [],
    }


def _run_response_payload() -> dict[str, Any]:
    dashboard = _dashboard_payload()
    return {
        "routine": dashboard["routines"][0],
        "dashboard": dashboard,
    }


def _dashboard_dump() -> dict[str, Any]:
    return _dashboard_payload()


def test_get_jenny_dashboard_returns_service_payload(mocker: MockerFixture) -> None:
    """Dashboard route should expose Jenny data through the portfolio API."""
    mocker.patch(
        "app.api.portfolio.jenny_routes._service",
        return_value=Mock(
            get_dashboard=Mock(return_value=Mock(model_dump=Mock(return_value=_dashboard_dump()))),
        ),
    )

    response = client.get("/api/portfolio/jenny")

    assert response.status_code == 200
    data = response.json()
    assert data["routines"][0]["routine_type"] == "daily_operator"
    assert data["notifications"][0]["symbol"] == "AAPL"


def test_run_jenny_routine_dispatches_daily_operator(mocker: MockerFixture) -> None:
    """Manual Jenny run should dispatch the requested routine."""
    service = Mock(
        run_daily_operator=Mock(return_value=Mock(model_dump=Mock(return_value=_run_response_payload()))),
    )
    mocker.patch("app.api.portfolio.jenny_routes._service", return_value=service)
    mocked = service.run_daily_operator

    response = client.post("/api/portfolio/jenny/run", json={"routine_type": "daily_operator"})

    assert response.status_code == 200
    mocked.assert_called_once_with(triggered_by="manual")


def test_run_jenny_routine_dispatches_daily_household_maintenance(mocker: MockerFixture) -> None:
    """Manual Jenny run should dispatch household maintenance when requested."""
    service = Mock(
        run_daily_household_maintenance=Mock(
            return_value=Mock(model_dump=Mock(return_value=_run_response_payload()))
        ),
    )
    mocker.patch("app.api.portfolio.jenny_routes._service", return_value=service)

    response = client.post(
        "/api/portfolio/jenny/run",
        json={"routine_type": "daily_household_maintenance"},
    )

    assert response.status_code == 200
    service.run_daily_household_maintenance.assert_called_once_with(triggered_by="manual")


def test_acknowledge_notification_returns_404_when_missing(mocker: MockerFixture) -> None:
    """Missing notifications should return 404."""
    mocker.patch(
        "app.api.portfolio.jenny_routes._service",
        return_value=Mock(acknowledge_notification=Mock(return_value=None)),
    )

    response = client.post("/api/portfolio/jenny/notifications/missing/acknowledge")

    assert response.status_code == 404


def test_chat_with_jenny_returns_reply_and_reconciled_questions(mocker: MockerFixture) -> None:
    """Jenny chat route should expose a conversational reply and any reconciled questions."""
    mocker.patch(
        "app.api.portfolio.jenny_routes._conversation_service",
        return_value=Mock(
            chat=Mock(
                return_value={
                    "reply": "I updated your retirement age to 60 and your plan still looks on track.",
                    "session_id": "session-1",
                    "resolved_questions": [
                        {
                            "id": "question-1",
                            "field_name": "target_retirement_age",
                            "question": "What age do you want to retire?",
                            "answer_text": "60",
                        }
                    ],
                    "updated_fields": ["target_retirement_age"],
                    "referenced_symbols": ["AMD"],
                }
            )
        ),
    )

    response = client.post(
        "/api/portfolio/jenny/chat",
        json={"message": "I want to retire at 60. Also, what do you think about AMD?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "session-1"
    assert data["resolved_questions"][0]["field_name"] == "target_retirement_age"
    assert data["referenced_symbols"] == ["AMD"]
