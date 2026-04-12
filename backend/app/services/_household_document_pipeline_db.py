"""Database helpers for household document pipeline."""

from __future__ import annotations

import json
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
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix or ".bin"
    stored_path = upload_dir / f"{document_id}{suffix.lower()}"
    stored_path.write_bytes(content)
    return stored_path


def insert_document_db(
    conn: DatabaseConnection,
    *,
    document_id: str,
    filename: str,
    stored_path: Path,
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
    reviewed: dict[str, object],
    extracted_text: object,
    now: str,
) -> None:
    """Update the document record and insert a review audit row."""
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
            now, json.dumps({"structured_data": structured_data}), document.id,
        ],
    )
    conn.execute(
        """
        INSERT INTO household_document_reviews (
            id, document_id, status, summary, confidence,
            extracted_text, structured_data, created_at, updated_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        """,
        [
            str(uuid.uuid4()), document.id, review_status, reviewed.get("summary"),
            review_confidence, extracted_text, json.dumps(structured_data), now, now,
        ],
    )


def archive_prior_document_data(
    conn: DatabaseConnection,
    document_id: str,
    now: str,
) -> None:
    """Supersede old inferred values and dismiss prior questions for a document."""
    conn.execute(
        """
        UPDATE household_inferred_values
        SET status = CASE WHEN status = 'confirmed' THEN status ELSE 'superseded' END,
            updated_at = %s
        WHERE source_document_id = %s
        """,
        [now, document_id],
    )
    conn.execute(
        """
        UPDATE household_questions
        SET status = CASE WHEN status = 'answered' THEN status ELSE 'dismissed' END,
            answered_at = COALESCE(answered_at, %s)
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
) -> None:
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
            document_id, json.dumps(metadata), now, now, now,
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
) -> None:
    """Patch the document metadata with the evidence-application summary."""
    conn.execute(
        """
        UPDATE household_documents
        SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
        WHERE id = %s
        """,
        [
            json.dumps({"application_summary": application_summary}),
            document_id,
        ],
    )


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
