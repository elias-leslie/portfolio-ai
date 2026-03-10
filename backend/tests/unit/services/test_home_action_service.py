"""Unit tests for the home action service."""

from __future__ import annotations

from app.services.home_action_service import HomeActionService


def test_get_action_queue_sorts_and_dedupes_actions() -> None:
    service = object.__new__(HomeActionService)
    service._recommendation_actions = lambda: [
        {
            "id": "rec-1",
            "source": "recommendations",
            "category": "investing",
            "priority": "high",
            "title": "Review NVDA",
            "detail": "Setup ready.",
            "action_label": "Open symbol",
            "href": "/symbols/NVDA",
            "symbol": "NVDA",
            "badge": "High",
        }
    ]
    service._jenny_actions = lambda: [
        {
            "id": "jenny-1",
            "source": "jenny",
            "category": "investing",
            "priority": "critical",
            "title": "Trim VTI concentration",
            "detail": "Largest position is too large.",
            "action_label": "Review with Jenny",
            "href": "/symbols/VTI",
            "symbol": "VTI",
            "badge": "Critical",
        },
        {
            "id": "dup",
            "source": "jenny",
            "category": "investing",
            "priority": "critical",
            "title": "Review NVDA",
            "detail": "Duplicate title should collapse by href and symbol.",
            "action_label": "Open symbol",
            "href": "/symbols/NVDA",
            "symbol": "NVDA",
            "badge": "Critical",
        },
    ]
    service._household_actions = lambda: []

    payload = service.get_action_queue()

    assert payload["summary"] == "2 prioritized actions ready."
    assert [action["title"] for action in payload["actions"]] == [
        "Trim VTI concentration",
        "Review NVDA",
    ]
