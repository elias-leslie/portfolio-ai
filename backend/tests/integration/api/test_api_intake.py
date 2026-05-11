"""Integration coverage for the canonical intake API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

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


def test_evidence_upload_rejects_unsupported_file_before_ingest() -> None:
    client = TestClient(app)

    with patch(
        "app.services.household_document_pipeline.HouseholdDocumentPipeline.ingest_document",
        new_callable=AsyncMock,
    ) as ingest_document:
        response = client.post(
            "/api/intake/evidence",
            files={"file": ("payload.exe", b"binary", "application/octet-stream")},
        )

    assert response.status_code == 415
    ingest_document.assert_not_awaited()


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


def test_evidence_upload_preserves_selected_household_account_id(tmp_path: Path) -> None:
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
            files={"file": ("brokerage.pdf", b"bound pdf bytes", "application/pdf")},
            data={
                "account_label": "Individual - TOD",
                "household_account_id": "5deacc73-4aa5-4910-aa12-bb00d0fe3b51",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["upload_household_account_id"] == "5deacc73-4aa5-4910-aa12-bb00d0fe3b51"


def test_evidence_batch_upload_reuses_one_review_session(tmp_path: Path) -> None:
    client = TestClient(app)

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_finance_service.HouseholdFinanceService.review_documents",
        ) as review_documents,
    ):
        response = client.post(
            "/api/intake/evidence/batch",
            files=[
                ("files", ("receipt-1.jpg", b"receipt one", "image/jpeg")),
                ("files", ("receipt-2.jpg", b"receipt two", "image/jpeg")),
            ],
        )

    assert response.status_code == 200
    payload = response.json()
    assert [item["filename"] for item in payload] == ["receipt-1.jpg", "receipt-2.jpg"]
    review_session_ids = {item["metadata"]["review_session_id"] for item in payload}
    assert len(review_session_ids) == 1
    review_documents.assert_called_once()
    assert review_documents.call_args.args[-1] == next(iter(review_session_ids))


def test_evidence_delete_removes_document_and_stored_file(tmp_path: Path) -> None:
    client = TestClient(app)

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value={
                "summary": "Plain-text upload.",
                "document_type": "other",
                "source_type": "other",
                "confidence": 0.55,
                "structured_data": {},
                "inferred_values": [],
                "questions": [],
            },
        ),
    ):
        upload = client.post(
            "/api/intake/evidence",
            files={"file": ("disposable.txt", b"to be removed", "text/plain")},
        )
        assert upload.status_code == 200
        document = upload.json()
        document_id = document["id"]
        stored_path = document["metadata"].get("stored_path")
        assert isinstance(stored_path, str) and Path(stored_path).exists()

    response = client.delete(f"/api/intake/evidence/{document_id}")
    assert response.status_code == 204
    assert not Path(stored_path).exists()

    second = client.delete(f"/api/intake/evidence/{document_id}")
    assert second.status_code == 404


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
