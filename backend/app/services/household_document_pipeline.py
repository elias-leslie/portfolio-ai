"""Document intake, review persistence, and import helpers for household finance."""

from __future__ import annotations

import hashlib
import json
import uuid
from csv import DictReader
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import TYPE_CHECKING, cast

from fastapi import UploadFile

from app.models.household_finance import HouseholdDocument, HouseholdQuestion
from app.services.household_finance_rows import row_to_document
from app.storage.types import DatabaseConnection

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService


# ---------------------------------------------------------------------------
# Pure utilities (module-level)
# ---------------------------------------------------------------------------


def classify_document(
    *,
    filename: str,
    content_type: str | None,
    source_type: str | None,
    document_type: str | None,
) -> tuple[str, str, float]:
    """Return (inferred_source, inferred_type, confidence) for an upload."""
    if source_type and document_type:
        return source_type, document_type, 0.99

    lowered = filename.lower()
    inferred_source = source_type or "other"
    inferred_type = document_type or "other"
    confidence = 0.55

    rules: list[tuple[list[str], str, str, float]] = [
        (["checking", "bank", "statement"], "bank", "statement", 0.82),
        (["visa", "mastercard", "amex", "credit"], "credit_card", "statement", 0.88),
        (["brokerage", "fidelity", "schwab", "vanguard"], "brokerage", "brokerage_statement", 0.9),
        (["ira", "401k", "roth", "retirement"], "retirement", "retirement_statement", 0.9),
        (["receipt", "walmart", "target", "costco"], "receipt", "receipt", 0.8),
        (["invoice", "bill", "utility", "insurance"], "billing", "invoice", 0.8),
    ]
    for tokens, src, doc_type, conf in rules:
        if any(t in lowered for t in tokens):
            inferred_source = source_type or src
            inferred_type = document_type or doc_type
            confidence = conf

    if content_type and content_type.startswith("image/") and inferred_type == "other":
        inferred_type = "receipt"
        inferred_source = source_type or "receipt"
        confidence = max(confidence, 0.72)

    return inferred_source, inferred_type, confidence


def parse_row_date(value: str | None) -> str | None:
    """Parse an ISO-ish date string; return None on failure."""
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = normalized.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).isoformat()
    except ValueError:
        return None


def parse_decimal(value: str | None) -> str | None:
    """Parse a currency string to a plain Decimal string; return None on failure."""
    if value is None:
        return None
    normalized = value.strip().replace(",", "").replace("$", "")
    if not normalized or normalized.lower() in {"not available", "not applicable"}:
        return None
    if normalized.startswith("'") and normalized.endswith("'"):
        normalized = normalized[1:-1]
    if normalized.startswith("(") and normalized.endswith(")"):
        normalized = f"-{normalized[1:-1]}"
    try:
        return str(Decimal(normalized))
    except InvalidOperation:
        return None


def detect_import_dataset(
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
) -> str | None:
    """Return dataset type key if the document should be imported as CSV rows."""
    if not document.filename.lower().endswith(".csv"):
        return None
    structured_data = reviewed.get("structured_data")
    if not isinstance(structured_data, dict):
        structured_data = {}
    merchant = structured_data.get("merchant")
    if document.filename.lower() == "order history.csv" and merchant == "Amazon":
        return "amazon_order_history"
    return None


def build_import_row_hash(
    *,
    dataset_type: str,
    row: dict[str, str | None],
) -> str | None:
    """Compute a dedup hash for a CSV import row; return None if key fields are missing."""
    if dataset_type != "amazon_order_history":
        return None
    order_id = (row.get("Order ID") or "").strip()
    asin = (row.get("ASIN") or "").strip()
    order_date = (row.get("Order Date") or "").strip()
    if not order_id or not asin or not order_date:
        return None
    quantity = (row.get("Original Quantity") or "").strip()
    fingerprint = "|".join([dataset_type, order_id, asin, order_date, quantity])
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def _insert_inferred_values(
    conn: DatabaseConnection,
    service: HouseholdFinanceService,
    *,
    document: HouseholdDocument,
    reviewed: dict[str, object],
    now: str,
) -> None:
    for inferred in cast(list[dict[str, object]], reviewed.get("inferred_values") or []):
        field_name = str(inferred.get("field_name") or "").strip()
        if field_name not in service.FIELD_LABELS:
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
                service._to_float(inferred.get("confidence")),
                "inferred",
                inferred.get("rationale"),
                document.id,
                json.dumps({"document_id": document.id}),
                now, now,
            ],
        )


def _insert_questions(
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
    for question in cast(list[dict[str, object]], reviewed.get("questions") or []):
        prompt = str(question.get("question") or "").strip()
        if not prompt:
            continue
        field_name = str(question.get("field_name") or "").strip() or None
        candidate = HouseholdQuestion(
            id=str(uuid.uuid4()),
            field_name=field_name,
            status="open",
            priority=service._normalize_priority(question.get("priority")),
            question=prompt,
            rationale=str(question.get("rationale")) if question.get("rationale") is not None else None,
            recommendation=str(question.get("recommendation")) if question.get("recommendation") is not None else None,
            answer_text=None,
            source_document_id=document.id,
            question_format=service._normalize_question_format(question.get("question_format")),
            options=service._normalize_question_options(question.get("options")),
            direction=service._normalize_question_direction(question.get("direction")),
            metadata={
                "document_id": document.id,
                "recommendation": question.get("recommendation"),
                "source_document": {
                    "id": document.id,
                    "filename": document.filename,
                    "source_type": resolved_source_type,
                    "document_type": resolved_document_type,
                    "account_label": str(account_hint) if account_hint is not None else document.account_label,
                    "review_summary": str(reviewed.get("summary")) if reviewed.get("summary") is not None else None,
                    "merchant": structured_data.get("merchant"),
                    "account_hint": structured_data.get("account_hint"),
                },
            },
            created_at=now,
            answered_at=None,
        )
        resolution = service._question_reconciler().infer_question_resolution_from_existing_context(
            service, conn=conn, question=candidate
        )
        if resolution is not None:
            continue
        conn.execute(
            """
            INSERT INTO household_questions (
                id, field_name, status, priority, question, rationale,
                source_document_id, metadata, question_format, options, direction, created_at
            ) VALUES (%s, %s, 'open', %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s, %s)
            """,
            [
                candidate.id, field_name,
                service._normalize_priority(question.get("priority")),
                prompt,
                question.get("rationale"),
                document.id,
                json.dumps({"document_id": document.id, "recommendation": question.get("recommendation")}),
                candidate.question_format,
                json.dumps(candidate.options) if candidate.options is not None else None,
                candidate.direction,
                now,
            ],
        )


# ---------------------------------------------------------------------------
# Pipeline class (≤10 methods)
# ---------------------------------------------------------------------------


class HouseholdDocumentPipeline:
    """Persist household uploads and review outcomes."""

    # Expose module-level pure helpers as instance attributes for backward compat.
    classify_document = staticmethod(classify_document)
    parse_row_date = staticmethod(parse_row_date)
    parse_decimal = staticmethod(parse_decimal)
    detect_import_dataset = staticmethod(detect_import_dataset)
    build_import_row_hash = staticmethod(build_import_row_hash)

    async def ingest_document(
        self,
        service: HouseholdFinanceService,
        *,
        upload: UploadFile,
        source_type: str | None = None,
        document_type: str | None = None,
        account_label: str | None = None,
    ) -> HouseholdDocument:
        document_id = str(uuid.uuid4())
        filename = upload.filename or f"{document_id}.bin"
        content = await upload.read()
        content_sha256 = hashlib.sha256(content).hexdigest()

        duplicate = self.find_duplicate_document_by_hash(service, content_sha256)
        if duplicate is not None:
            duplicate.metadata["duplicate_detected"] = True
            duplicate.metadata["duplicate_reason"] = "exact_content_match"
            return duplicate

        inferred_source, inferred_type, confidence = classify_document(
            filename=filename,
            content_type=upload.content_type,
            source_type=source_type,
            document_type=document_type,
        )
        suffix = Path(filename).suffix or ".bin"
        upload_dir = service._upload_root()
        upload_dir.mkdir(parents=True, exist_ok=True)
        stored_path = upload_dir / f"{document_id}{suffix.lower()}"
        stored_path.write_bytes(content)

        now = datetime.now(UTC).isoformat()
        metadata = {
            "original_filename": filename,
            "stored_path": str(stored_path),
            "content_sha256": content_sha256,
        }
        with service.storage.connection() as conn:
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
                    account_label, upload.content_type, len(content),
                    confidence, now, json.dumps(metadata),
                ],
            )
            conn.commit()

        document = service.get_document(document_id)
        if document is None:
            raise RuntimeError("Failed to persist uploaded document")
        return document

    def find_duplicate_document_by_hash(
        self,
        service: HouseholdFinanceService,
        content_sha256: str,
    ) -> HouseholdDocument | None:
        with service.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT
                    id, filename, source_type, document_type, status, account_label,
                    file_size_bytes, content_type, classification_confidence,
                    review_status, review_summary, review_confidence,
                    statement_start, statement_end, uploaded_at, parsed_at, metadata
                FROM household_documents
                WHERE metadata->>'content_sha256' = %s
                ORDER BY uploaded_at DESC
                LIMIT 1
                """,
                [content_sha256],
            ).fetchone()
        if row is None:
            return None
        return row_to_document(
            row,
            to_float=service._to_float,
            iso=service._iso,
            iso_or_none=service._iso_or_none,
        )

    def review_document(self, service: HouseholdFinanceService, document_id: str) -> None:
        document = service.get_document(document_id)
        if document is None:
            service.logger.warning(
                "household_document_missing_for_review", document_id=document_id
            )
            return
        try:
            self.process_document_review(service, document)
        except Exception as exc:
            service.logger.exception(
                "household_document_review_failed", document_id=document_id, error=str(exc)
            )
            with service.storage.connection() as conn:
                conn.execute(
                    """
                    UPDATE household_documents
                    SET status = 'needs_review', review_status = 'failed',
                        review_summary = %s, parsed_at = %s
                    WHERE id = %s
                    """,
                    [
                        "Jenny could not finish reviewing this document yet. Re-upload or add more context.",
                        datetime.now(UTC).isoformat(),
                        document_id,
                    ],
                )
                conn.commit()

    def process_document_review(self, service: HouseholdFinanceService, document: HouseholdDocument) -> None:
        stored_path = document.metadata.get("stored_path")
        if not isinstance(stored_path, str) or not stored_path:
            return

        now = datetime.now(UTC).isoformat()
        reviewed = service.review_service.review(
            document_id=document.id,
            filename=document.filename,
            stored_path=Path(stored_path),
            content_type=document.content_type,
            source_type=document.source_type,
            document_type=document.document_type,
        )
        self._persist_review(service, document=document, reviewed=reviewed, now=now)
        self.upsert_document_signatures(service, document=document, reviewed=reviewed)
        self.import_document_rows(service, document=document, reviewed=reviewed)
        service.transaction_service.import_document_transactions(
            document=document, reviewed=reviewed
        )

    def _persist_review(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
        now: str,
    ) -> None:
        review_confidence = service._to_float(reviewed.get("confidence"))
        review_status = "complete" if (review_confidence or 0.0) >= 0.65 else "needs_review"
        document_status = "parsed" if review_status == "complete" else "needs_review"
        structured_data = reviewed.get("structured_data") or {}
        if not isinstance(structured_data, dict):
            structured_data = {}
        extracted_text = reviewed.get("extracted_text")
        resolved_source_type = str(reviewed.get("source_type") or document.source_type)
        resolved_document_type = str(reviewed.get("document_type") or document.document_type)
        account_hint = structured_data.get("account_hint")

        with service.storage.connection() as conn:
            conn.execute(
                "UPDATE household_questions SET status = 'dismissed', answered_at = %s WHERE source_document_id = %s AND status = 'open'",
                [now, document.id],
            )
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
            conn.execute(
                """
                UPDATE household_inferred_values
                SET status = CASE WHEN status = 'confirmed' THEN status ELSE 'superseded' END,
                    updated_at = %s
                WHERE source_document_id = %s
                """,
                [now, document.id],
            )
            conn.execute(
                """
                UPDATE household_questions
                SET status = CASE WHEN status = 'answered' THEN status ELSE 'dismissed' END,
                    answered_at = COALESCE(answered_at, %s)
                WHERE source_document_id = %s
                """,
                [now, document.id],
            )
            _insert_inferred_values(conn, service, document=document, reviewed=reviewed, now=now)
            _insert_questions(
                conn, service,
                document=document, reviewed=reviewed, now=now,
                resolved_source_type=resolved_source_type,
                resolved_document_type=resolved_document_type,
                structured_data=structured_data,
                account_hint=account_hint,
            )
            conn.commit()

    def upsert_document_signatures(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
    ) -> None:
        extracted_text = reviewed.get("extracted_text")
        if not isinstance(extracted_text, str) or not extracted_text:
            return

        signature_candidates = service.review_service.build_signature_candidates(
            filename=document.filename,
            extracted_text=extracted_text,
        )
        if not signature_candidates:
            return

        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict):
            structured_data = {}

        now = datetime.now(UTC).isoformat()
        with service.storage.connection() as conn:
            for signature_type, signature_key, metadata in signature_candidates:
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
                        str(reviewed.get("source_type") or document.source_type),
                        str(reviewed.get("document_type") or document.document_type),
                        structured_data.get("merchant"),
                        structured_data.get("account_hint"),
                        service._to_float(reviewed.get("confidence")),
                        document.id, json.dumps(metadata), now, now, now,
                    ],
                )
            conn.commit()

    def import_document_rows(
        self,
        service: HouseholdFinanceService,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
    ) -> None:
        dataset_type = detect_import_dataset(document=document, reviewed=reviewed)
        if dataset_type is None:
            return
        stored_path = document.metadata.get("stored_path")
        if not isinstance(stored_path, str) or not stored_path:
            return

        now = datetime.now(UTC).isoformat()
        with Path(stored_path).open("r", encoding="utf-8", errors="ignore", newline="") as fh:
            rows = list(DictReader(fh))
        inserted = 0
        duplicates = 0
        with service.storage.connection() as conn:
            for row in rows:
                row_hash = build_import_row_hash(dataset_type=dataset_type, row=row)
                if row_hash is None:
                    continue
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
                        str(uuid.uuid4()), document.id, dataset_type, row_hash,
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
                if result is not None and result[0]:
                    inserted += 1
                else:
                    duplicates += 1
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
                    document.id,
                ],
            )
            conn.commit()
