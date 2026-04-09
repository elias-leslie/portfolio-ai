"""Integration coverage for the canonical intake API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


def test_evidence_upload_uses_canonical_intake_route(tmp_path: Path) -> None:
    client = TestClient(app)

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value={
                "summary": "Credit-card export with machine-readable transactions.",
                "document_type": "statement",
                "source_type": "credit_card",
                "confidence": 0.93,
                "structured_data": {"account_hint": "Primary rewards card"},
                "inferred_values": [],
                "questions": [],
            },
        ),
    ):
        response = client.post(
            "/api/intake/evidence",
            files={"file": ("transactions.qfx", b"<OFX><CREDITCARDMSGSRSV1><CCSTMTTRNRS>", "application/x-ofx")},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["filename"] == "transactions.qfx"
    assert payload["source_type"] == "credit_card"


def test_evidence_upload_preserves_optional_account_hint(tmp_path: Path) -> None:
    client = TestClient(app)

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value={
                "summary": "Brokerage statement with holdings.",
                "document_type": "brokerage_statement",
                "source_type": "brokerage",
                "confidence": 0.95,
                "structured_data": {"financial_accounts": []},
                "inferred_values": [],
                "questions": [],
            },
        ),
    ):
        response = client.post(
            "/api/intake/evidence",
            files={"file": ("brokerage.pdf", b"pdf bytes", "application/pdf")},
            data={"account_label": "Individual - TOD"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["account_label"] == "Individual - TOD"


def test_evidence_list_reads_existing_intake_items(tmp_path: Path) -> None:
    client = TestClient(app)

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value={
                "summary": "Brokerage screenshot with current cash balance.",
                "document_type": "brokerage_statement",
                "source_type": "brokerage",
                "confidence": 0.95,
                "structured_data": {"account_hint": "Rollover IRA"},
                "inferred_values": [],
                "questions": [],
            },
        ),
    ):
        upload = client.post(
            "/api/intake/evidence",
            files={"file": ("brokerage.png", b"image-bytes", "image/png")},
        )
        assert upload.status_code == 200

    response = client.get("/api/intake/evidence")

    assert response.status_code == 200
    items = response.json()["items"]
    assert items
    assert any(item["filename"] == "brokerage.png" for item in items)
