"""Document-related methods mixed into HouseholdFinanceService."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from app.models.household_finance import HouseholdDocument, HouseholdDocumentList
from app.services._household_document_pipeline_db import delete_document_row
from app.services._household_finance_utils import iso, iso_or_none, to_float
from app.services.household_document_review_contracts import (
    HouseholdDocumentReviewDecisionResult,
)
from app.services.household_document_storage import (
    resolve_document_upload,
    resolve_upload_path,
)
from app.services.household_finance_rows import row_to_document

_DOC_COLS = (
    "id, filename, source_type, document_type, status, account_label, "
    "file_size_bytes, content_type, classification_confidence, "
    "review_status, review_summary, review_confidence, "
    "statement_start, statement_end, uploaded_at, parsed_at, metadata"
)
_DOC_SQL = f"SELECT {_DOC_COLS} FROM household_documents"


class _HFDocumentMethods:
    """Document query and pipeline methods."""

    storage: Any
    document_pipeline: Any

    def _upload_root(self) -> Path:
        raise NotImplementedError

    async def ingest_document(
        self,
        *,
        upload: UploadFile,
        source_type: str | None = None,
        document_type: str | None = None,
        account_label: str | None = None,
        household_account_id: str | None = None,
        review_session_id: str | None = None,
    ) -> HouseholdDocument:
        return await self.document_pipeline.ingest_document(
            self, upload=upload, source_type=source_type,
            document_type=document_type, account_label=account_label,
            household_account_id=household_account_id,
            review_session_id=review_session_id,
        )

    def _annotate_document(self, document: HouseholdDocument) -> HouseholdDocument:
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        expects_file = document.document_type != "api_sync" and document.source_type not in {"plaid", "snaptrade"}
        if expects_file:
            metadata["file_available"] = (
                resolve_document_upload(metadata, self._upload_root()) is not None
            )
        else:
            metadata.pop("file_available", None)
        existing_summary = metadata.get("application_summary")
        if document.review_status or document.parsed_at or isinstance(existing_summary, dict):
            metadata["application_summary"] = self.document_pipeline.describe_application_state(
                self,
                document=document,
            )
        document.metadata = metadata
        return document

    def list_documents(self, limit: int = 20) -> HouseholdDocumentList:
        with self.storage.connection() as conn:
            rows = conn.execute(
                f"{_DOC_SQL} ORDER BY uploaded_at DESC LIMIT %s", [limit]
            ).fetchall()
        return HouseholdDocumentList(
            items=[
                self._annotate_document(
                    row_to_document(row, to_float=to_float, iso=iso, iso_or_none=iso_or_none)
                )
                for row in rows
            ]
        )

    def get_document(self, document_id: str) -> HouseholdDocument | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                f"{_DOC_SQL} WHERE id = %s", [document_id]
            ).fetchone()
        if row is None:
            return None
        return self._annotate_document(
            row_to_document(row, to_float=to_float, iso=iso, iso_or_none=iso_or_none)
        )

    def delete_document(self, document_id: str) -> bool:
        """Remove a household document by id, including its stored file."""
        with self.storage.connection() as conn:
            deleted, stored_path = delete_document_row(conn, document_id=document_id)
            conn.commit()
        resolved_path = resolve_upload_path(
            stored_path,
            self._upload_root(),
            require_exists=False,
        )
        if deleted and resolved_path is not None:
            with suppress(OSError):
                resolved_path.unlink(missing_ok=True)
        return deleted

    def review_document(self, document_id: str) -> None:
        self.document_pipeline.review_document(self, document_id)

    def review_documents(
        self,
        document_ids: list[str],
        review_session_id: str | None = None,
    ) -> None:
        self.document_pipeline.review_documents(
            self,
            document_ids,
            review_session_id=review_session_id,
        )

    def decide_document_review(
        self,
        document_id: str,
        *,
        review_id: str,
        proposal_hash: str,
        proposal_preview: dict[str, object],
        decision: str,
        reason: str | None = None,
    ) -> HouseholdDocumentReviewDecisionResult:
        return self.document_pipeline.decide_document_review(
            self,
            document_id=document_id,
            review_id=review_id,
            proposal_hash=proposal_hash,
            proposal_preview=proposal_preview,
            decision=decision,
            reason=reason,
        )
