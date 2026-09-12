"""Pending pagination and exact source review on the migrated PostgreSQL schema."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from tests.integration.services.test_household_transaction_dedup import _insert_document

from app.main import app
from app.services.household_evidence_source import read_evidence_source
from app.storage import get_storage


def test_old_pending_evidence_is_selected_before_paging():
    storage = get_storage()
    old = [_insert_document(storage, source_type="manual_entry") for _ in range(3)]
    for _ in range(25):
        _insert_document(storage, source_type="manual_entry")
    rejected = _insert_document(storage, source_type="manual_entry")
    with storage.connection() as conn:
        for index, document_id in enumerate(old):
            conn.execute(
                "UPDATE household_documents SET status='needs_review',review_status='needs_review',uploaded_at=%s WHERE id=%s",
                [datetime.now(UTC) - timedelta(days=30 + index), document_id],
            )
        conn.execute(
            "UPDATE household_documents SET status='needs_review',review_status='needs_review',metadata=%s::jsonb WHERE id=%s",
            [json.dumps({"review_proposal": {"status": "rejected"}}), rejected],
        )
        conn.commit()
    client = TestClient(app)
    first = client.get("/api/intake/evidence?view=pending&limit=2").json()
    second = client.get("/api/intake/evidence?view=pending&limit=2&offset=2").json()
    assert first["total_count"] == first["pending_count"] == 3
    assert [row["id"] for row in first["items"] + second["items"]] == old
    assert second["offset"] == 2
    recent = client.get("/api/intake/evidence?view=history").json()
    assert recent["total_count"] == 29
    assert not set(old).intersection(row["id"] for row in recent["items"])


def test_source_is_bound_to_exact_review_and_file_stays_root_confined(tmp_path, monkeypatch):
    from app.services.household_finance_service import HouseholdFinanceService

    storage = get_storage()
    document_id = _insert_document(storage, source_type="receipt")
    other = _insert_document(storage, source_type="receipt")
    reviews = [str(uuid.uuid4()), str(uuid.uuid4())]
    with storage.connection() as conn:
        for index, review_id in enumerate(reviews):
            conn.execute(
                """INSERT INTO household_document_reviews
                (id,document_id,status,extracted_text,structured_data,review_payload,created_at,updated_at)
                VALUES (%s,%s,'needs_review',%s,%s::jsonb,%s::jsonb,%s,%s)""",
                [
                    review_id,
                    document_id,
                    "Source old\nOil 10.00\nSubtotal 10.00"
                    if index == 0
                    else "New review different values",
                    json.dumps(
                        {"line_items": [{"description": "Item", "amount": 10}], "subtotal": 10, "tax": 1, "amount": 11}
                    ),
                    json.dumps({"questions": [{"question": "Which account paid this receipt?"}]}),
                    datetime.now(UTC) + timedelta(seconds=index),
                    datetime.now(UTC),
                ],
            )
        conn.execute(
            "UPDATE household_documents SET metadata=%s::jsonb WHERE id=%s",
            [json.dumps({"storage_key": "receipt.txt"}), document_id],
        )
        conn.commit()
    with storage.connection() as conn:
        conn.execute("UPDATE household_documents SET metadata=metadata||%s::jsonb WHERE id=%s",[json.dumps({"review_proposal":{"review_id":reviews[0],"status":"pending"}}),document_id])
        conn.commit()
    detail = HouseholdFinanceService().get_document(document_id)
    assert detail is not None
    assert detail.metadata["review_questions"] == ["Which account paid this receipt?"]
    proposal = detail.metadata["review_proposal"]
    assert isinstance(proposal, dict)
    assert proposal["review_id"] == reviews[0]
    source = read_evidence_source(document_id, review_id=reviews[0], search="oil")
    assert source["review_id"] == reviews[0]
    assert "2: Oil 10.00" in source["text"]
    assert source["questions"] == ["Which account paid this receipt?"]
    assert source["arithmetic"][0]["line_difference"] == 0
    assert source["arithmetic"][0]["total_difference"] == 0
    assert read_evidence_source(document_id)["review_id"] == reviews[1]
    with pytest.raises(HTTPException) as error:
        read_evidence_source(other, review_id=reviews[0])
    assert error.value.status_code == 404
    monkeypatch.setattr(HouseholdFinanceService, "_upload_root", lambda _self: tmp_path)
    (tmp_path / "receipt.txt").write_text("Original receipt")
    response = TestClient(app).get(f"/api/intake/evidence/{document_id}/file")
    assert response.status_code == 200
    assert response.text == "Original receipt"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    with storage.connection() as conn:
        conn.execute(
            "UPDATE household_documents SET metadata=%s::jsonb WHERE id=%s",
            [json.dumps({"storage_key": "../outside.txt"}), document_id],
        )
        conn.commit()
    assert TestClient(app).get(f"/api/intake/evidence/{document_id}/file").status_code == 404


def test_dashboard_and_question_reads_do_not_write_household_state(monkeypatch):
    from contextlib import contextmanager

    from app.services.household_finance_service import HouseholdFinanceService

    service = HouseholdFinanceService()
    # Initial installation creates its profile separately from the read audit.
    service.get_profile()
    original = service.storage.connection

    @contextmanager
    def read_only():
        with original() as conn:
            conn.execute('SET TRANSACTION READ ONLY')
            yield conn

    monkeypatch.setattr(service.storage, 'connection', read_only)
    dashboard = service.get_dashboard()
    assert dashboard.accounts == []
    assert service.list_questions().items == []
