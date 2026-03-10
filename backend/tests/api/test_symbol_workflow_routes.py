"""Route coverage for symbol workflow and automation center APIs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_symbol_workflow_returns_service_payload(mocker) -> None:
    mocker.patch(
        "app.api.symbols.router.workflow_service.get_workflow",
        return_value={
            "symbol": "VTI",
            "stage": "review_due",
            "summary": "A portfolio review is due.",
            "last_transition_at": "2026-03-10T15:00:00+00:00",
            "updated_by": "jenny",
            "notes": "Concentration review needed.",
            "available_transitions": ["live", "exited"],
            "history": [],
        },
    )

    response = client.get("/api/symbols/VTI/workflow")

    assert response.status_code == 200
    assert response.json()["stage"] == "review_due"


def test_transition_symbol_workflow_returns_updated_state(mocker) -> None:
    mocked = mocker.patch(
        "app.api.symbols.router.workflow_service.transition",
        return_value={
            "symbol": "VTI",
            "stage": "live",
            "summary": "The symbol is now managed as a live position.",
            "last_transition_at": "2026-03-10T15:00:00+00:00",
            "updated_by": "user",
            "notes": "Moved back to live after review.",
            "available_transitions": ["review_due", "exited"],
            "history": [],
        },
    )

    response = client.post(
        "/api/symbols/VTI/workflow/transition",
        json={"stage": "live", "note": "Moved back to live after review."},
    )

    assert response.status_code == 200
    mocked.assert_called_once()
    assert response.json()["stage"] == "live"


def test_get_home_automation_center_returns_guardrails_and_runs(mocker) -> None:
    mocker.patch(
        "app.api.home.automation_service.get_center",
        return_value={
            "generated_at": "2026-03-10T15:00:00+00:00",
            "guardrails": [
                {
                    "key": "thesis_generation_enabled",
                    "label": "Thesis generation",
                    "value": "Enabled",
                    "detail": "Controlled by trading rules.",
                }
            ],
            "recent_runs": [
                {
                    "id": "routine-1",
                    "label": "Jenny daily operator",
                    "status": "completed",
                    "triggered_by": "scheduled",
                    "started_at": "2026-03-10T14:00:00+00:00",
                    "completed_at": "2026-03-10T14:07:00+00:00",
                    "detail": "Reviewed 7 symbols and opened 2 notifications.",
                }
            ],
            "warnings": [],
        },
    )

    response = client.get("/api/home/automation-center")

    assert response.status_code == 200
    payload = response.json()
    assert payload["guardrails"][0]["key"] == "thesis_generation_enabled"
    assert payload["recent_runs"][0]["status"] == "completed"
