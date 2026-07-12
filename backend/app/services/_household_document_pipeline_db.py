"""Database helpers for household document pipeline."""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, cast

from app.models.household_finance import HouseholdDocument, HouseholdQuestion
from app.services._household_document_pipeline_utils import (
    build_import_row_hash,
    parse_decimal,
    parse_row_date,
)
from app.services._household_finance_utils import (
    normalize_priority,
    normalize_question_direction,
    normalize_question_format,
    normalize_question_options,
    to_float,
)
from app.services.household_document_storage import document_storage_reference
from app.services.household_finance_rows import FIELD_LABELS
from app.storage.types import DatabaseConnection

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService


def save_upload_to_disk(
    content: bytes,
    *,
    document_id: str,
    filename: str,
    upload_dir: Path,
) -> Path:
    """Write upload bytes to disk and return the stored path."""
    upload_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    upload_dir.chmod(0o700)
    suffix = Path(filename).suffix or ".bin"
    stored_path = upload_dir / f"{document_id}{suffix.lower()}"
    temporary_path = stored_path.with_suffix(f"{stored_path.suffix}.tmp")
    file_descriptor = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(file_descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.replace(stored_path)
        stored_path.chmod(0o600)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return stored_path


def insert_document_db(
    conn: DatabaseConnection,
    *,
    document_id: str,
    filename: str,
    stored_path: str | Path,
    inferred_source: str,
    inferred_type: str,
    account_label: str | None,
    content_type: str | None,
    file_size: int,
    confidence: float,
    now: str,
    metadata: dict[str, object],
) -> None:
    """Insert the household_documents row and commit."""
    conn.execute(
        """
        INSERT INTO household_documents (
            id, filename, stored_path, source_type, document_type, status,
            account_label, content_type, file_size_bytes, classification_confidence,
            uploaded_at, metadata
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        [
            document_id, filename, str(stored_path),
            inferred_source, inferred_type, "staged",
            account_label, content_type, file_size,
            confidence, now, json.dumps(metadata),
        ],
    )
    conn.commit()


def update_document_and_log_review(
    conn: DatabaseConnection,
    *,
    document: HouseholdDocument,
    resolved_source_type: str,
    resolved_document_type: str,
    document_status: str,
    review_status: str,
    review_confidence: float | None,
    account_hint: object,
    structured_data: dict[str, object],
    review_metadata: dict[str, object],
    reviewed: dict[str, object],
    extracted_text: object,
    now: str,
) -> str:
    """Update the document record and insert a review audit row."""
    review_id = str(uuid.uuid4())
    conn.execute(
        """
        UPDATE household_documents
        SET source_type = %s, document_type = %s, status = %s, review_status = %s,
            review_summary = %s, review_confidence = %s,
            account_label = COALESCE(%s, account_label), parsed_at = %s,
            metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
        WHERE id = %s
        """,
        [
            resolved_source_type, resolved_document_type,
            document_status, review_status, reviewed.get("summary"), review_confidence,
            str(account_hint) if account_hint is not None else None,
            now, json.dumps(review_metadata), document.id,
        ],
    )
    conn.execute(
        """
        INSERT INTO household_document_reviews (
            id, document_id, status, summary, confidence,
            extracted_text, structured_data, review_payload, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
        """,
        [
            review_id, document.id, review_status, reviewed.get("summary"),
            review_confidence, extracted_text, json.dumps(structured_data),
            # extracted_text already has a dedicated column; do not duplicate
            # potentially large, sensitive OCR text inside JSONB.
            json.dumps({key: value for key, value in reviewed.items() if key != "extracted_text"}),
            now,
            now,
        ],
    )
    return review_id


def archive_prior_inferred_values(
    conn: DatabaseConnection,
    document_id: str,
    now: str,
) -> None:
    """Supersede prior unconfirmed inferences once replacement data is approved."""
    conn.execute(
        """
        UPDATE household_inferred_values
        SET status = CASE WHEN status = 'confirmed' THEN status ELSE 'superseded' END,
            updated_at = %s
        WHERE source_document_id = %s
        """,
        [now, document_id],
    )


def insert_inferred_values(
    conn: DatabaseConnection,
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
    now: str,
) -> int:
    inserted = 0
    for inferred in cast(list[dict[str, object]], reviewed.get("inferred_values") or []):
        field_name = str(inferred.get("field_name") or "").strip()
        if field_name not in FIELD_LABELS:
            continue
        conn.execute(
            """
            INSERT INTO household_inferred_values (
                id, field_name, value_text, confidence, status, rationale,
                source_document_id, metadata, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            [
                str(uuid.uuid4()), field_name,
                str(inferred.get("value") or "").strip() or None,
                to_float(inferred.get("confidence")),
                "inferred",
                inferred.get("rationale"),
                document.id,
                json.dumps({"document_id": document.id}),
                now, now,
            ],
        )
        inserted += 1
    return inserted


def _build_question_candidate(
    service: HouseholdFinanceService,
    *,
    question: dict[str, object],
    document: HouseholdDocument,
    resolved_source_type: str,
    resolved_document_type: str,
    structured_data: dict[str, object],
    account_hint: object,
    review_summary: object,
    now: str,
) -> HouseholdQuestion:
    """Build a HouseholdQuestion from a raw question dict and document context."""
    return HouseholdQuestion(
        id=str(uuid.uuid4()),
        field_name=str(question.get("field_name") or "").strip() or None,
        status="open",
        priority=normalize_priority(question.get("priority")),
        question=str(question.get("question") or "").strip(),
        rationale=str(question.get("rationale")) if question.get("rationale") is not None else None,
        recommendation=str(question.get("recommendation")) if question.get("recommendation") is not None else None,
        answer_text=None,
        source_document_id=document.id,
        question_format=normalize_question_format(question.get("question_format")),
        options=normalize_question_options(question.get("options")),
        direction=normalize_question_direction(question.get("direction")),
        metadata={
            "document_id": document.id,
            "recommendation": question.get("recommendation"),
            "source_document": {
                "id": document.id,
                "filename": document.filename,
                "source_type": resolved_source_type,
                "document_type": resolved_document_type,
                "account_label": str(account_hint) if account_hint is not None else document.account_label,
                "review_summary": str(review_summary) if review_summary is not None else None,
                "merchant": structured_data.get("merchant"),
                "account_hint": structured_data.get("account_hint"),
            },
        },
        created_at=now,
        answered_at=None,
    )


def insert_questions(
    conn: DatabaseConnection,
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
    now: str,
    resolved_source_type: str,
    resolved_document_type: str,
    structured_data: dict[str, object],
    account_hint: object,
) -> None:
    review_summary = reviewed.get("summary")
    for question in cast(list[dict[str, object]], reviewed.get("questions") or []):
        prompt = str(question.get("question") or "").strip()
        if not prompt:
            continue
        candidate = _build_question_candidate(
            service,
            question=question, document=document,
            resolved_source_type=resolved_source_type,
            resolved_document_type=resolved_document_type,
            structured_data=structured_data,
            account_hint=account_hint,
            review_summary=review_summary,
            now=now,
        )
        if service.question_reconciler.infer_question_resolution_from_existing_context(
            service, conn=conn, question=candidate
        ) is not None:
            continue
        conn.execute(
            """
            INSERT INTO household_questions (
                id, field_name, status, priority, question, rationale,
                source_document_id, metadata, question_format, options, direction, created_at
            ) VALUES (%s, %s, 'open', %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s)
            """,
            [
                candidate.id, candidate.field_name,
                candidate.priority, prompt,
                question.get("rationale"),
                document.id,
                json.dumps({"document_id": document.id, "recommendation": question.get("recommendation")}),
                candidate.question_format,
                json.dumps(candidate.options) if candidate.options is not None else None,
                candidate.direction,
                now,
            ],
        )


def upsert_signature_record(
    conn: DatabaseConnection,
    *,
    signature_type: str,
    signature_key: str,
    metadata: dict[str, object],
    source_type: str,
    document_type: str,
    structured_data: dict[str, object],
    confidence: float | None,
    document_id: str,
    now: str,
) -> None:
    """Upsert one document signature row."""
    metadata_payload = dict(metadata)
    metadata_payload["structured_data"] = structured_data
    conn.execute(
        """
        INSERT INTO household_document_signatures (
            id, signature_key, signature_type, source_type, document_type,
            merchant, account_hint, confidence, sample_document_id,
            metadata, match_count, created_at, updated_at, last_seen_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 1, %s, %s, %s)
        ON CONFLICT (signature_key) DO UPDATE SET
            source_type = EXCLUDED.source_type,
            document_type = EXCLUDED.document_type,
            merchant = COALESCE(EXCLUDED.merchant, household_document_signatures.merchant),
            account_hint = COALESCE(EXCLUDED.account_hint, household_document_signatures.account_hint),
            confidence = GREATEST(
                COALESCE(household_document_signatures.confidence, 0),
                COALESCE(EXCLUDED.confidence, 0)
            ),
            sample_document_id = EXCLUDED.sample_document_id,
            metadata = household_document_signatures.metadata || EXCLUDED.metadata,
            match_count = household_document_signatures.match_count + 1,
            updated_at = EXCLUDED.updated_at,
            last_seen_at = EXCLUDED.last_seen_at
        """,
        [
            str(uuid.uuid4()), signature_key, signature_type,
            source_type, document_type,
            structured_data.get("merchant"),
            structured_data.get("account_hint"),
            confidence,
            document_id, json.dumps(metadata_payload), now, now, now,
        ],
    )


def upsert_import_row(
    conn: DatabaseConnection,
    *,
    row: dict[str, str | None],
    document_id: str,
    dataset_type: str,
    now: str,
) -> bool | None:
    """Upsert one CSV import row. Returns True=inserted, False=duplicate, None=skipped."""
    row_hash = build_import_row_hash(dataset_type=dataset_type, row=row)
    if row_hash is None:
        return None
    result = conn.execute(
        """
        INSERT INTO household_import_rows (
            id, document_id, dataset_type, row_hash, external_row_id,
            row_date, merchant, description, amount, currency, row_metadata,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (row_hash) DO UPDATE SET
            document_id = EXCLUDED.document_id,
            external_row_id = COALESCE(EXCLUDED.external_row_id, household_import_rows.external_row_id),
            row_date = COALESCE(EXCLUDED.row_date, household_import_rows.row_date),
            merchant = COALESCE(EXCLUDED.merchant, household_import_rows.merchant),
            description = COALESCE(EXCLUDED.description, household_import_rows.description),
            amount = COALESCE(EXCLUDED.amount, household_import_rows.amount),
            currency = COALESCE(EXCLUDED.currency, household_import_rows.currency),
            row_metadata = household_import_rows.row_metadata || EXCLUDED.row_metadata,
            updated_at = EXCLUDED.updated_at
        RETURNING (xmax = 0) AS was_inserted
        """,
        [
            str(uuid.uuid4()), document_id, dataset_type, row_hash,
            row.get("Order ID"),
            parse_row_date(row.get("Order Date")),
            "Amazon",
            row.get("Product Name") or row.get("ASIN"),
            parse_decimal(
                row.get("Total Amount")
                or row.get("Shipment Item Subtotal")
                or row.get("Unit Price")
            ),
            row.get("Currency"),
            json.dumps(row),
            now, now,
        ],
    ).fetchone()
    return result is not None and bool(result[0])


def upsert_receipt_line_item_row(
    conn: DatabaseConnection,
    *,
    row: dict[str, str | None],
    document_id: str,
    now: str,
) -> bool | None:
    """Upsert one itemized receipt row. Returns True=inserted, False=duplicate, None=skipped."""
    dataset_type = "receipt_line_items"
    row_hash = build_import_row_hash(dataset_type=dataset_type, row=row)
    if row_hash is None:
        return None
    result = conn.execute(
        """
        INSERT INTO household_import_rows (
            id, document_id, dataset_type, row_hash, external_row_id,
            row_date, merchant, description, amount, currency, row_metadata,
            created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (row_hash) DO UPDATE SET
            document_id = EXCLUDED.document_id,
            external_row_id = COALESCE(EXCLUDED.external_row_id, household_import_rows.external_row_id),
            row_date = COALESCE(EXCLUDED.row_date, household_import_rows.row_date),
            merchant = COALESCE(EXCLUDED.merchant, household_import_rows.merchant),
            description = COALESCE(EXCLUDED.description, household_import_rows.description),
            amount = COALESCE(EXCLUDED.amount, household_import_rows.amount),
            currency = COALESCE(EXCLUDED.currency, household_import_rows.currency),
            row_metadata = household_import_rows.row_metadata || EXCLUDED.row_metadata,
            updated_at = EXCLUDED.updated_at
        RETURNING (xmax = 0) AS was_inserted
        """,
        [
            str(uuid.uuid4()),
            document_id,
            dataset_type,
            row_hash,
            row.get("External Row ID"),
            parse_row_date(row.get("Order Date")),
            row.get("Merchant"),
            row.get("Product Name") or row.get("Description"),
            parse_decimal(row.get("Total Amount") or row.get("Unit Price")),
            row.get("Currency"),
            json.dumps(row),
            now,
            now,
        ],
    ).fetchone()
    return result is not None and bool(result[0])


_DUPLICATE_LOOKUP_SQL = """
    SELECT
        id, filename, source_type, document_type, status, account_label,
        file_size_bytes, content_type, classification_confidence,
        review_status, review_summary, review_confidence,
        statement_start, statement_end, uploaded_at, parsed_at, metadata
    FROM household_documents
    WHERE metadata->>'content_sha256' = %s
    ORDER BY uploaded_at DESC
    LIMIT 1
"""


def fetch_duplicate_document_row(
    conn: DatabaseConnection,
    content_sha256: str,
) -> object:
    """Return the most recent document row matching the given SHA256, or None."""
    return conn.execute(_DUPLICATE_LOOKUP_SQL, [content_sha256]).fetchone()


def delete_document_row(
    conn: DatabaseConnection,
    *,
    document_id: str,
) -> tuple[bool, str | None]:
    """Delete a household document row by id.

    Related rows in household_evidence_accounts, household_import_rows, and
    household_document_reviews cascade-delete via FK constraints. References
    from household_inferred_values, household_questions, and
    household_document_signatures are set to NULL by their FK definitions.

    Returns (deleted, stored_path) where stored_path is the on-disk upload
    location pulled from the deleted row's metadata, or None.
    """
    result = conn.execute(
        "DELETE FROM household_documents WHERE id = %s RETURNING metadata",
        [document_id],
    ).fetchone()
    if result is None:
        return False, None
    metadata = result[0]
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, ValueError):
            metadata = None
    stored_path: str | None = None
    if isinstance(metadata, dict):
        stored_path = document_storage_reference(metadata)
    return True, stored_path


def mark_review_failed(
    conn: DatabaseConnection,
    *,
    document_id: str,
    now: str,
) -> None:
    """Mark a document review as failed and commit."""
    conn.execute(
        """
        UPDATE household_documents
        SET status = 'needs_review', review_status = 'failed',
            review_summary = %s, parsed_at = %s
        WHERE id = %s
        """,
        [
            "Jenny could not finish reviewing this document yet. Re-upload or add more context.",
            now,
            document_id,
        ],
    )
    conn.commit()


def dismiss_open_document_questions(
    conn: DatabaseConnection,
    *,
    document_id: str,
    now: str,
) -> None:
    """Dismiss all open questions for a document (pre-review cleanup)."""
    conn.execute(
        "UPDATE household_questions SET status = 'dismissed', answered_at = %s"
        " WHERE source_document_id = %s AND status = 'open'",
        [now, document_id],
    )


def update_import_summary(
    conn: DatabaseConnection,
    *,
    document_id: str,
    dataset_type: str,
    inserted: int,
    duplicates: int,
) -> None:
    """Patch the document metadata with a CSV import summary."""
    conn.execute(
        """
        UPDATE household_documents
        SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
        WHERE id = %s
        """,
        [
            json.dumps({
                "import_summary": {
                    "dataset_type": dataset_type,
                    "inserted_rows": inserted,
                    "duplicate_rows": duplicates,
                }
            }),
            document_id,
        ],
    )


def update_document_application_summary(
    conn: DatabaseConnection,
    *,
    document_id: str,
    application_summary: dict[str, object],
    reconciliation_summary: dict[str, object] | None = None,
    review_proposal: dict[str, object] | None = None,
) -> None:
    """Patch the document metadata with the evidence-application summary."""
    payload: dict[str, object] = {"application_summary": application_summary}
    if reconciliation_summary is not None:
        payload["reconciliation_summary"] = reconciliation_summary
    if review_proposal is not None:
        payload["review_proposal"] = review_proposal
    conn.execute(
        """
        UPDATE household_documents
        SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
        WHERE id = %s
        """,
        [
            json.dumps(payload),
            document_id,
        ],
    )


def update_bound_document_review_state(
    conn: DatabaseConnection,
    *,
    document_id: str,
    review_id: str,
    proposal_hash: str,
    expected_statuses: list[str],
    application_summary: dict[str, object],
    review_proposal: dict[str, object],
    reconciliation_summary: dict[str, object] | None = None,
    document_status: str | None = None,
    review_status: str | None = None,
) -> bool:
    """Update visible state only while the same bound proposal remains current."""
    payload: dict[str, object] = {
        "application_summary": application_summary,
        "review_proposal": review_proposal,
    }
    if reconciliation_summary is not None:
        payload["reconciliation_summary"] = reconciliation_summary
    conn.execute(
        """
        UPDATE household_documents
        SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
            status = COALESCE(%s, status),
            review_status = COALESCE(%s, review_status)
        WHERE id = %s
          AND metadata->'review_proposal'->>'schema_version' = '2'
          AND metadata->'review_proposal'->>'review_id' = %s
          AND metadata->'review_proposal'->>'proposal_hash' = %s
          AND metadata->'review_proposal'->>'status' = ANY(%s)
        """,
        [
            json.dumps(payload),
            document_status,
            review_status,
            document_id,
            review_id,
            proposal_hash,
            expected_statuses,
        ],
    )
    return conn.rowcount == 1


def bind_document_review_proposal(
    conn: DatabaseConnection,
    *,
    document_id: str,
    review_id: str,
    proposal_hash: str,
    proposal_preview: dict[str, object],
    now: str,
) -> bool:
    """Persist the immutable preview/hash binding on its exact review row."""
    conn.execute(
        """
        UPDATE household_document_reviews
        SET proposal_hash = %s,
            proposal_preview = %s::jsonb,
            updated_at = %s
        WHERE id = %s
          AND document_id = %s
          AND status = 'needs_review'
          AND decision IS NULL
          AND (
              (proposal_hash IS NULL AND proposal_preview IS NULL)
              OR (proposal_hash = %s AND proposal_preview = %s::jsonb)
          )
        """,
        [
            proposal_hash,
            json.dumps(proposal_preview),
            now,
            review_id,
            document_id,
            proposal_hash,
            json.dumps(proposal_preview),
        ],
    )
    return conn.rowcount == 1


def fetch_document_review_decision_binding(
    conn: DatabaseConnection,
    *,
    document_id: str,
    review_id: str,
) -> dict[str, object] | None:
    """Read the review payload, immutable binding, and current visible proposal."""
    row = conn.execute(
        """
        SELECT review.id, review.summary, review.confidence,
               review.extracted_text, review.structured_data, review.review_payload,
               review.proposal_hash, review.proposal_preview,
               review.decision, review.decision_status, review.application_phase,
               review.application_journal, document.metadata->'review_proposal'
        FROM household_document_reviews AS review
        JOIN household_documents AS document ON document.id = review.document_id
        WHERE review.id = %s
          AND review.document_id = %s
          AND review.status = 'needs_review'
          AND review.id = (
              SELECT latest.id
              FROM household_document_reviews AS latest
              WHERE latest.document_id = review.document_id
              ORDER BY latest.created_at DESC, latest.id DESC
              LIMIT 1
          )
        LIMIT 1
        """,
        [review_id, document_id],
    ).fetchone()
    if row is None:
        return None
    return {
        "id": str(row[0]),
        "summary": row[1],
        "confidence": row[2],
        "extracted_text": row[3],
        "structured_data": row[4] if isinstance(row[4], dict) else {},
        "review_payload": row[5] if isinstance(row[5], dict) else {},
        "proposal_hash": row[6],
        "proposal_preview": row[7] if isinstance(row[7], dict) else None,
        "decision": row[8],
        "decision_status": row[9],
        "application_phase": row[10],
        "application_journal": row[11] if isinstance(row[11], dict) else {},
        "visible_proposal": row[12] if isinstance(row[12], dict) else None,
    }


def try_acquire_document_review_executor(
    conn: DatabaseConnection,
    *,
    document_id: str,
) -> bool:
    """Acquire one session-scoped executor lock; process exit releases it."""
    row = conn.execute(
        "SELECT pg_try_advisory_lock(hashtext('portfolio-ai:document-review'), hashtext(%s))",
        [document_id],
    ).fetchone()
    return bool(row and row[0])


def release_document_review_executor(
    conn: DatabaseConnection,
    *,
    document_id: str,
) -> None:
    """Release the session-scoped document review executor lock."""
    conn.execute(
        "SELECT pg_advisory_unlock(hashtext('portfolio-ai:document-review'), hashtext(%s))",
        [document_id],
    )


def claim_document_review_decision(
    conn: DatabaseConnection,
    *,
    document_id: str,
    review_id: str,
    proposal_hash: str,
    proposal_preview: dict[str, object],
    decision: str,
    reason: str | None,
    executor_token: str | None,
    now: str,
) -> dict[str, object] | None:
    """Claim a first decision or resume its exact interrupted approval."""
    row = conn.execute(
        """
        UPDATE household_document_reviews
        SET decision = COALESCE(decision, %s),
            decision_status = CASE
                WHEN %s = 'approve' THEN 'applying'
                ELSE 'rejected'
            END,
            decision_reason = COALESCE(decision_reason, %s),
            decided_at = COALESCE(decided_at, %s),
            updated_at = %s,
            application_phase = CASE
                WHEN %s = 'approve' THEN COALESCE(application_phase, 'claimed')
                ELSE application_phase
            END,
            application_attempts = application_attempts +
                CASE WHEN %s = 'approve' THEN 1 ELSE 0 END,
            application_executor_token = CASE
                WHEN %s = 'approve' THEN %s
                ELSE NULL
            END,
            application_last_error = CASE
                WHEN %s = 'approve' THEN NULL
                ELSE application_last_error
            END
        WHERE id = %s
          AND document_id = %s
          AND status = 'needs_review'
          AND id = (
              SELECT latest.id
              FROM household_document_reviews AS latest
              WHERE latest.document_id = %s
              ORDER BY latest.created_at DESC, latest.id DESC
              LIMIT 1
          )
          AND proposal_hash = %s
          AND proposal_preview = %s::jsonb
          AND (
              (
                  %s = 'reject'
                  AND decision IS NULL
              )
              OR
              (
                  %s = 'approve'
                  AND (
                      decision IS NULL
                      OR (
                          decision = 'approve'
                          AND decision_status IN ('applying', 'failed')
                      )
                  )
              )
          )
          AND EXISTS (
              SELECT 1
              FROM household_documents document
              WHERE document.id = household_document_reviews.document_id
                AND document.metadata->'review_proposal'->>'schema_version' = '2'
                AND document.metadata->'review_proposal'->>'review_id' = %s
                AND document.metadata->'review_proposal'->>'proposal_hash' = %s
                AND document.metadata->'review_proposal'->'preview' = %s::jsonb
                AND (
                    (%s = 'reject' AND document.metadata->'review_proposal'->>'status' = 'pending')
                    OR
                    (%s = 'approve' AND document.metadata->'review_proposal'->>'status'
                        IN ('pending', 'applying', 'failed'))
                )
          )
        RETURNING id, summary, confidence, extracted_text, structured_data,
                  review_payload, proposal_hash, proposal_preview,
                  decision_status, application_phase, application_journal
        """,
        [
            decision,
            decision,
            reason,
            now,
            now,
            decision,
            decision,
            decision,
            executor_token,
            decision,
            review_id,
            document_id,
            document_id,
            proposal_hash,
            json.dumps(proposal_preview),
            decision,
            decision,
            review_id,
            proposal_hash,
            json.dumps(proposal_preview),
            decision,
            decision,
        ],
    ).fetchone()
    if row is None:
        return None
    return {
        "id": str(row[0]),
        "summary": row[1],
        "confidence": row[2],
        "extracted_text": row[3],
        "structured_data": row[4] if isinstance(row[4], dict) else {},
        "review_payload": row[5] if isinstance(row[5], dict) else {},
        "proposal_hash": row[6],
        "proposal_preview": row[7] if isinstance(row[7], dict) else {},
        "decision_status": row[8],
        "application_phase": row[9],
        "application_journal": row[10] if isinstance(row[10], dict) else {},
    }


def record_document_review_application_phase(
    conn: DatabaseConnection,
    *,
    review_id: str,
    executor_token: str,
    expected_phase: str,
    phase: str,
    journal_patch: dict[str, object],
    now: str,
) -> bool:
    """Advance one durable phase while retaining the exclusive executor claim."""
    conn.execute(
        """
        UPDATE household_document_reviews
        SET application_phase = %s,
            application_journal = application_journal || %s::jsonb,
            updated_at = %s
        WHERE id = %s
          AND decision = 'approve'
          AND decision_status = 'applying'
          AND application_executor_token = %s
          AND application_phase = %s
        """,
        [
            phase,
            json.dumps(journal_patch),
            now,
            review_id,
            executor_token,
            expected_phase,
        ],
    )
    return conn.rowcount == 1


def fail_document_review_application(
    conn: DatabaseConnection,
    *,
    review_id: str,
    executor_token: str,
    error: str,
    application_summary: dict[str, object] | None,
    now: str,
) -> bool:
    """Record an ordinary failure without erasing the last completed phase."""
    conn.execute(
        """
        UPDATE household_document_reviews
        SET decision_status = 'failed',
            decision_application_summary = %s::jsonb,
            application_executor_token = NULL,
            application_last_error = %s,
            updated_at = %s
        WHERE id = %s
          AND decision = 'approve'
          AND decision_status = 'applying'
          AND application_executor_token = %s
        """,
        [
            json.dumps(application_summary) if application_summary is not None else None,
            error[:2000],
            now,
            review_id,
            executor_token,
        ],
    )
    return conn.rowcount == 1


def complete_document_review_decision(
    conn: DatabaseConnection,
    *,
    review_id: str,
    executor_token: str,
    application_summary: dict[str, object] | None,
    now: str,
) -> bool:
    """Finalize the claimed approval from its last durable phase exactly once."""
    conn.execute(
        """
        UPDATE household_document_reviews
        SET decision_status = 'applied',
            decision_application_summary = %s::jsonb,
            application_phase = 'finalized',
            application_executor_token = NULL,
            application_last_error = NULL,
            updated_at = %s
        WHERE id = %s
          AND decision = 'approve'
          AND decision_status = 'applying'
          AND application_phase = 'inferences_applied'
          AND application_executor_token = %s
        """,
        [
            json.dumps(application_summary) if application_summary is not None else None,
            now,
            review_id,
            executor_token,
        ],
    )
    return conn.rowcount == 1


def fetch_document_application_counts(
    conn: DatabaseConnection,
    *,
    document_id: str,
) -> dict[str, object]:
    """Return the current applied-output counts for a document."""
    row = conn.execute(
        """
        SELECT
            COALESCE(
                (SELECT COUNT(*)
                 FROM household_import_rows
                 WHERE document_id = %s),
                0
            ) AS import_count,
            (
                SELECT MIN(dataset_type)
                FROM household_import_rows
                WHERE document_id = %s
            ) AS dataset_type,
            COALESCE(
                (SELECT COUNT(*)
                 FROM household_transactions
                 WHERE document_id = %s),
                0
            ) AS transaction_count,
            COALESCE(
                (SELECT COUNT(*)
                 FROM household_evidence_accounts
                 WHERE document_id = %s),
                0
            ) AS evidence_account_count,
            COALESCE(
                (SELECT COUNT(*)
                 FROM household_inferred_values
                 WHERE source_document_id = %s
                   AND status IN ('inferred', 'confirmed')),
                0
            ) AS inferred_count
        """,
        [document_id, document_id, document_id, document_id, document_id],
    ).fetchone()
    if row is None:
        return {
            "import_count": 0,
            "dataset_type": None,
            "transaction_count": 0,
            "evidence_account_count": 0,
            "inferred_count": 0,
        }
    return {
        "import_count": int(row[0] or 0),
        "dataset_type": str(row[1]) if row[1] is not None else None,
        "transaction_count": int(row[2] or 0),
        "evidence_account_count": int(row[3] or 0),
        "inferred_count": int(row[4] or 0),
    }
