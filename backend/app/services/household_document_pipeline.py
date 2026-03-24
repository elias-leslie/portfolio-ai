"""Document intake, review persistence, and import helpers for household finance."""

from __future__ import annotations

import hashlib
import uuid
from csv import DictReader
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import UploadFile

from app.models.household_finance import HouseholdDocument
from app.services._household_document_pipeline_db import (
    archive_prior_document_data,
    dismiss_open_document_questions,
    fetch_duplicate_document_row,
    insert_document_db,
    insert_inferred_values,
    insert_questions,
    mark_review_failed,
    save_upload_to_disk,
    update_document_and_log_review,
    update_import_summary,
    upsert_import_row,
    upsert_signature_record,
)
from app.services._household_document_pipeline_utils import (
    build_import_row_hash,
    classify_document,
    detect_import_dataset,
    parse_decimal,
    parse_row_date,
)
from app.services.household_finance_rows import row_to_document

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService

# Re-export pure utilities at module level for any direct importers.
__all__ = [
    "HouseholdDocumentPipeline",
    "build_import_row_hash",
    "classify_document",
    "detect_import_dataset",
    "parse_decimal",
    "parse_row_date",
]


class HouseholdDocumentPipeline:
    """Persist household uploads and review outcomes."""

    # Expose pure helpers as instance attributes for backward compatibility.
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
        stored_path = save_upload_to_disk(
            content, document_id=document_id, filename=filename,
            upload_dir=service._upload_root(),
        )
        now = datetime.now(UTC).isoformat()
        metadata: dict[str, object] = {
            "original_filename": filename,
            "stored_path": str(stored_path),
            "content_sha256": content_sha256,
        }
        with service.storage.connection() as conn:
            insert_document_db(
                conn,
                document_id=document_id, filename=filename, stored_path=stored_path,
                inferred_source=inferred_source, inferred_type=inferred_type,
                account_label=account_label, content_type=upload.content_type,
                file_size=len(content), confidence=confidence, now=now, metadata=metadata,
            )

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
            row = fetch_duplicate_document_row(conn, content_sha256)
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
                mark_review_failed(conn, document_id=document_id, now=datetime.now(UTC).isoformat())

    def process_document_review(
        self, service: HouseholdFinanceService, document: HouseholdDocument
    ) -> None:
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
        planning_items = reviewed.get("planning_items")
        if isinstance(planning_items, list):
            service.merge_planning_items(
                items=[item for item in planning_items if isinstance(item, dict)],
                provenance="document_review",
                source_document_id=document.id,
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
            dismiss_open_document_questions(conn, document_id=document.id, now=now)
            update_document_and_log_review(
                conn,
                document=document,
                resolved_source_type=resolved_source_type,
                resolved_document_type=resolved_document_type,
                document_status=document_status,
                review_status=review_status,
                review_confidence=review_confidence,
                account_hint=account_hint,
                structured_data=structured_data,
                reviewed=reviewed,
                extracted_text=extracted_text,
                now=now,
            )
            insert_inferred_values(conn, service, document=document, reviewed=reviewed, now=now)
            insert_questions(
                conn, service,
                document=document, reviewed=reviewed, now=now,
                resolved_source_type=resolved_source_type,
                resolved_document_type=resolved_document_type,
                structured_data=structured_data,
                account_hint=account_hint,
            )
            archive_prior_document_data(conn, document.id, now)
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
            filename=document.filename, extracted_text=extracted_text,
        )
        if not signature_candidates:
            return
        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict):
            structured_data = {}
        shared = {
            "source_type": str(reviewed.get("source_type") or document.source_type),
            "document_type": str(reviewed.get("document_type") or document.document_type),
            "structured_data": structured_data,
            "confidence": service._to_float(reviewed.get("confidence")),
            "document_id": document.id,
            "now": datetime.now(UTC).isoformat(),
        }
        with service.storage.connection() as conn:
            for signature_type, signature_key, metadata in signature_candidates:
                upsert_signature_record(
                    conn, signature_type=signature_type, signature_key=signature_key,
                    metadata=metadata, **shared,
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
        inserted = duplicates = 0
        with service.storage.connection() as conn:
            for row in rows:
                result = upsert_import_row(
                    conn, row=row, document_id=document.id, dataset_type=dataset_type, now=now,
                )
                inserted += result is True
                duplicates += result is False
            update_import_summary(
                conn, document_id=document.id, dataset_type=dataset_type,
                inserted=inserted, duplicates=duplicates,
            )
            conn.commit()
