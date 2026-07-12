"""Integration coverage for the canonical intake API."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Event
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def test_storage():
    from app.storage import get_storage

    return get_storage()


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
            data={"source_type": "credit_card", "document_type": "statement"},
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
        assert isinstance(stored_path, str) and (tmp_path / stored_path).exists()

        response = client.delete(f"/api/intake/evidence/{document_id}")
        assert response.status_code == 204
        assert not (tmp_path / stored_path).exists()

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


def test_low_confidence_review_requires_one_explicit_approval(
    tmp_path: Path,
    test_storage,
) -> None:
    client = TestClient(app)
    review = {
        "summary": "Possible brokerage account snapshot.",
        "document_type": "brokerage_statement",
        "source_type": "brokerage",
        "confidence": 0.54,
        "structured_data": {
            "financial_accounts": [
                {
                    "account_name": "Individual brokerage",
                    "institution": "Example Brokerage",
                    "account_type": "brokerage",
                    "account_mask": "1234",
                    "balance": "1000.00",
                    "as_of_date": "2026-07-12",
                }
            ]
        },
        "inferred_values": [],
        "planning_items": [],
        "questions": [],
        "review_checks": {
            "expected_account_count": 1,
            "expects_transaction_activity": False,
            "ambiguity_remaining": False,
        },
    }

    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value=review,
        ),
    ):
        upload = client.post(
            "/api/intake/evidence",
            files={"file": ("uncertain.pdf", b"uncertain statement", "application/pdf")},
        )

    assert upload.status_code == 200
    document_id = upload.json()["id"]
    listed = client.get("/api/intake/evidence").json()["items"]
    document = next(item for item in listed if item["id"] == document_id)
    assert document["metadata"]["application_summary"]["status"] == "needs_review"
    assert document["metadata"]["review_proposal"]["status"] == "pending"
    proposal = document["metadata"]["review_proposal"]
    review_id = proposal["review_id"]

    with test_storage.connection() as conn:
        before = conn.execute(
            "SELECT COUNT(*) FROM household_evidence_accounts WHERE document_id = %s",
            [document_id],
        ).fetchone()
    assert before == (0,)

    with test_storage.connection() as conn:
        conn.execute(
            """
            UPDATE household_documents
            SET metadata = jsonb_set(
                metadata, '{review_proposal,schema_version}', '1'::jsonb, TRUE
            )
            WHERE id = %s
            """,
            [document_id],
        )
        conn.commit()
    legacy = client.post(
        f"/api/intake/evidence/{document_id}/decision",
        json={
            "review_id": review_id,
            "proposal_hash": proposal["proposal_hash"],
            "proposal_preview": proposal["preview"],
            "decision": "approve",
        },
    )
    assert legacy.status_code == 409
    assert "predates exact previews" in legacy.json()["detail"]
    with test_storage.connection() as conn:
        conn.execute(
            """
            UPDATE household_documents
            SET metadata = jsonb_set(
                metadata, '{review_proposal}', %s::jsonb, TRUE
            )
            WHERE id = %s
            """,
            [json.dumps(proposal), document_id],
        )
        conn.commit()

    tampered_preview = deepcopy(proposal["preview"])
    tampered_preview["accounts"][0]["balance"] = "999999.00"
    mismatch = client.post(
        f"/api/intake/evidence/{document_id}/decision",
        json={
            "review_id": review_id,
            "proposal_hash": proposal["proposal_hash"],
            "proposal_preview": tampered_preview,
            "decision": "approve",
        },
    )
    assert mismatch.status_code == 409
    with test_storage.connection() as conn:
        mismatch_state = conn.execute(
            """
            SELECT review.decision, review.decision_status,
                   (SELECT COUNT(*) FROM household_evidence_accounts
                    WHERE document_id = %s)
            FROM household_document_reviews AS review
            WHERE review.id = %s
            """,
            [document_id, review_id],
        ).fetchone()
    assert mismatch_state == (None, None, 0)

    # A live executor owns the same document-scoped advisory lock. The API
    # must reject contention without claiming the decision or touching data.
    with test_storage.connection() as lock_conn:
        lock_conn.execute(
            "SELECT pg_advisory_lock(hashtext('portfolio-ai:document-review'), hashtext(%s))",
            [document_id],
        )
        contended = client.post(
            f"/api/intake/evidence/{document_id}/decision",
            json={
                "review_id": review_id,
                "proposal_hash": proposal["proposal_hash"],
                "proposal_preview": proposal["preview"],
                "decision": "approve",
            },
        )
        assert contended.status_code == 409
        lock_conn.execute(
            "SELECT pg_advisory_unlock(hashtext('portfolio-ai:document-review'), hashtext(%s))",
            [document_id],
        )
        lock_conn.commit()

    # Emulate a crash after core reconcilers committed but before the phase
    # journal advanced. Replaying those document-scoped reconcilers must not
    # duplicate the account snapshot.
    from app.api.intake import _service

    service = _service()
    persisted_document = service.get_document(document_id)
    assert persisted_document is not None
    first_outputs = service.document_pipeline.apply_review_outputs(
        service,
        document=persisted_document,
        reviewed=review,
    )
    assert first_outputs["evidence_accounts"] == 1

    # Emulate a hard process exit immediately after the exact approval claim.
    # The session advisory lock is gone, so the same bound request must recover.
    with test_storage.connection() as conn:
        conn.execute(
            """
            UPDATE household_document_reviews
            SET decision = 'approve', decision_status = 'applying',
                decision_reason = 'approved before crash',
                decided_at = CURRENT_TIMESTAMP,
                application_phase = 'claimed', application_attempts = 1,
                application_executor_token = 'dead-process',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            [review_id],
        )
        conn.execute(
            """
            UPDATE household_documents
            SET metadata = jsonb_set(
                metadata, '{review_proposal,status}', '"applying"'::jsonb, TRUE
            )
            WHERE id = %s
            """,
            [document_id],
        )
        conn.commit()

    approved = client.post(
        f"/api/intake/evidence/{document_id}/decision",
        json={
            "review_id": review_id,
            "proposal_hash": proposal["proposal_hash"],
            "proposal_preview": proposal["preview"],
            "decision": "approve",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "applied"
    assert approved.json()["application_summary"]["evidence_accounts"] == 1

    duplicate = client.post(
        f"/api/intake/evidence/{document_id}/decision",
        json={
            "review_id": review_id,
            "proposal_hash": proposal["proposal_hash"],
            "proposal_preview": proposal["preview"],
            "decision": "approve",
        },
    )
    assert duplicate.status_code == 409

    with test_storage.connection() as conn:
        decision = conn.execute(
            """
            SELECT decision, decision_status,
                   (SELECT COUNT(*) FROM household_evidence_accounts WHERE document_id = %s)
            FROM household_document_reviews
            WHERE document_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [document_id, document_id],
        ).fetchone()
    assert decision == ("approve", "applied", 1)


def test_failed_inference_phase_resumes_without_duplicate_values(
    tmp_path: Path,
    test_storage,
) -> None:
    """A rolled-back inference phase resumes from its durable outputs journal."""
    from app.services import household_document_pipeline as pipeline_module

    client = TestClient(app)
    review = {
        "summary": "Possible income evidence.",
        "document_type": "other",
        "source_type": "other",
        "confidence": 0.52,
        "structured_data": {},
        "inferred_values": [
            {
                "field_name": "monthly_net_income_target",
                "value": "5000",
                "confidence": 0.52,
            }
        ],
        "planning_items": [],
        "questions": [],
        "review_checks": {"ambiguity_remaining": False},
    }
    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value=review,
        ),
    ):
        upload = client.post(
            "/api/intake/evidence",
            files={"file": ("income.txt", b"monthly income 5000", "text/plain")},
        )
    assert upload.status_code == 200
    document_id = upload.json()["id"]
    document = next(
        item
        for item in client.get("/api/intake/evidence").json()["items"]
        if item["id"] == document_id
    )
    proposal = document["metadata"]["review_proposal"]
    payload = {
        "review_id": proposal["review_id"],
        "proposal_hash": proposal["proposal_hash"],
        "proposal_preview": proposal["preview"],
        "decision": "approve",
    }

    real_record_phase = pipeline_module.record_document_review_application_phase

    def fail_first_inference_phase(*args, **kwargs):
        if kwargs.get("phase") == "inferences_applied":
            return False
        return real_record_phase(*args, **kwargs)

    with patch.object(
        pipeline_module,
        "record_document_review_application_phase",
        side_effect=fail_first_inference_phase,
    ):
        failed = client.post(
            f"/api/intake/evidence/{document_id}/decision",
            json=payload,
        )
    assert failed.status_code == 503, failed.text
    assert "Retry approval" in failed.json()["detail"]

    with test_storage.connection() as conn:
        interrupted = conn.execute(
            """
            SELECT decision_status, application_phase, application_attempts,
                   (SELECT COUNT(*) FROM household_inferred_values
                    WHERE source_document_id = %s AND status = 'inferred')
            FROM household_document_reviews
            WHERE id = %s
            """,
            [document_id, proposal["review_id"]],
        ).fetchone()
    assert interrupted == ("failed", "outputs_applied", 1, 0)

    resumed = client.post(
        f"/api/intake/evidence/{document_id}/decision",
        json=payload,
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "applied"
    assert resumed.json()["application_summary"]["inferred_values"] == 1

    with test_storage.connection() as conn:
        completed = conn.execute(
            """
            SELECT decision_status, application_phase, application_attempts,
                   (SELECT COUNT(*) FROM household_inferred_values
                    WHERE source_document_id = %s AND status = 'inferred')
            FROM household_document_reviews
            WHERE id = %s
            """,
            [document_id, proposal["review_id"]],
        ).fetchone()
    assert completed == ("applied", "finalized", 2, 1)


def test_concurrent_approval_requests_run_one_executor(
    tmp_path: Path,
    test_storage,
) -> None:
    """A second live request conflicts while the first owns the advisory lock."""
    from app.services.household_document_pipeline import HouseholdDocumentPipeline

    client = TestClient(app)
    review = {
        "summary": "Possible account snapshot.",
        "document_type": "statement",
        "source_type": "bank",
        "confidence": 0.5,
        "structured_data": {
            "financial_accounts": [
                {
                    "account_name": "Checking",
                    "balance": "250.00",
                    "as_of_date": "2026-07-12",
                }
            ]
        },
        "inferred_values": [],
        "planning_items": [],
        "questions": [],
        "review_checks": {"ambiguity_remaining": False},
    }
    with (
        patch(
            "app.services.household_finance_service.HouseholdFinanceService._upload_root",
            return_value=tmp_path,
        ),
        patch(
            "app.services.household_document_review.HouseholdDocumentReviewService.review",
            return_value=review,
        ),
    ):
        upload = client.post(
            "/api/intake/evidence",
            files={"file": ("checking.pdf", b"checking snapshot", "application/pdf")},
        )
    assert upload.status_code == 200
    document_id = upload.json()["id"]
    document = next(
        item
        for item in client.get("/api/intake/evidence").json()["items"]
        if item["id"] == document_id
    )
    proposal = document["metadata"]["review_proposal"]
    payload = {
        "review_id": proposal["review_id"],
        "proposal_hash": proposal["proposal_hash"],
        "proposal_preview": proposal["preview"],
        "decision": "approve",
    }
    first_started = Event()
    release_first = Event()
    real_apply = HouseholdDocumentPipeline.apply_review_outputs

    def hold_first_executor(self, service, **kwargs):
        first_started.set()
        assert release_first.wait(timeout=5), "first approval was not released"
        return real_apply(self, service, **kwargs)

    with (
        patch.object(
            HouseholdDocumentPipeline,
            "apply_review_outputs",
            new=hold_first_executor,
        ),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        first = executor.submit(
            TestClient(app).post,
            f"/api/intake/evidence/{document_id}/decision",
            json=payload,
        )
        assert first_started.wait(timeout=5), "first approval never acquired execution"
        second = executor.submit(
            TestClient(app).post,
            f"/api/intake/evidence/{document_id}/decision",
            json=payload,
        )
        second_response = second.result(timeout=5)
        release_first.set()
        first_response = first.result(timeout=5)

    assert first_response.status_code == 200
    assert second_response.status_code == 409
    with test_storage.connection() as conn:
        state = conn.execute(
            """
            SELECT decision_status, application_attempts,
                   (SELECT COUNT(*) FROM household_evidence_accounts
                    WHERE document_id = %s)
            FROM household_document_reviews
            WHERE id = %s
            """,
            [document_id, proposal["review_id"]],
        ).fetchone()
    assert state == ("applied", 1, 1)
