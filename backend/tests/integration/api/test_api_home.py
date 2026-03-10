"""Integration coverage for the home action queue API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_home_action_queue_combines_household_and_portfolio_signals(tmp_path: Path) -> None:
    client = TestClient(app)

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value={
                "summary": "Checking statement covering recurring deposits and baseline spending.",
                "document_type": "statement",
                "source_type": "bank",
                "confidence": 0.89,
                "structured_data": {"account_hint": "Joint Checking"},
                "inferred_values": [],
                "questions": [
                    {
                        "field_name": "monthly_net_income_target",
                        "question": "What is your monthly household take-home income?",
                        "priority": "high",
                        "recommendation": "Use the recurring net deposit range as the starting point.",
                        "rationale": "Jenny needs this to finish the budget baseline.",
                    }
                ],
            },
        ),
    ):
        upload = client.post(
            "/api/household/documents",
            files={"file": ("checking_statement.pdf", b"bank bytes", "application/pdf")},
        )
        assert upload.status_code == 200

        response = client.get("/api/home/action-queue")

    assert response.status_code == 200
    payload = response.json()
    assert payload["actions"]
    assert any(action["category"] == "household" for action in payload["actions"])
    assert any(action["href"] == "/money" for action in payload["actions"])
