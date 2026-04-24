"""Unit tests for thesis API routes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_generate_thesis_accepts_force_regenerate_without_symbol(mocker) -> None:
    """The generate endpoint should rely on the path symbol, not require it in the body."""
    thesis_payload = {
        "id": "thesis-1",
        "symbol": "AAPL",
        "version": 1,
        "status": "active",
        "action": "BUY",
        "core_reasons": [],
        "key_catalysts": [],
        "risks": [],
        "value_drivers": None,
        "expected_return_pct": 12.0,
        "expected_timeframe_days": 90,
        "claude_validation": None,
        "gemini_validation": None,
        "cross_validation_score": 0.8,
        "invalidation_reason": None,
        "invalidated_at": None,
        "created_at": "2026-03-07T10:00:00+00:00",
        "updated_at": "2026-03-07T10:00:00+00:00",
    }
    decision_eligibility = {
        "eligible": True,
        "status": "eligible",
        "reasons": [],
        "age_hours": 2.0,
        "evaluated_at": "2026-03-07T12:00:00+00:00",
    }

    mocker.patch(
        "app.api.thesis._get_thesis_service",
        return_value=mocker.Mock(
            generate_thesis=mocker.Mock(return_value=thesis_payload),
            get_thesis_versions=mocker.Mock(return_value=[]),
            evaluate_decision_eligibility=mocker.Mock(
                return_value=decision_eligibility
            ),
        ),
    )

    response = client.post(
        "/api/thesis/AAPL/generate",
        json={"force_regenerate": False},
    )

    assert response.status_code == 200
    assert response.json()["thesis"]["symbol"] == "AAPL"
    assert response.json()["decision_eligibility"]["eligible"] is True
