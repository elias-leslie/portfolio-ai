"""Document-related methods mixed into HouseholdFinanceService."""

from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import Any
from uuid import UUID

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


_PENDING_DOCUMENT_SQL = """(
    COALESCE(status,'') <> 'rejected'
    AND COALESCE(metadata->'review_proposal'->>'status','') <> 'rejected'
    AND (
        COALESCE(status,'') NOT IN ('parsed','rejected') OR review_status IN ('needs_review','failed')
        OR metadata->'review_proposal'->>'status' IN ('pending','applying','failed','stale')
        OR metadata->'application_summary'->>'needs_follow_up' = 'true'
        OR metadata->'application_summary'->>'status' IN ('needs_review','incomplete','needs_date_review')
    )
)"""


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
            self,
            upload=upload,
            source_type=source_type,
            document_type=document_type,
            account_label=account_label,
            household_account_id=household_account_id,
            review_session_id=review_session_id,
        )

    def _annotate_document(self, document: HouseholdDocument, *, refresh_application_state: bool = True) -> HouseholdDocument:
        metadata = document.metadata if isinstance(document.metadata, dict) else {}
        expects_file = document.document_type not in {
            "api_sync",
            "manual_entry",
        } and document.source_type not in {"plaid", "snaptrade", "soft_charge", "manual_entry"}
        if expects_file:
            metadata["file_available"] = (
                resolve_document_upload(metadata, self._upload_root()) is not None
            )
        else:
            metadata.pop("file_available", None)
            # Earlier maintenance treated API and manual records as lost files.
            # Correct the read view without rewriting their original audit data.
            if (document.review_summary or "").startswith("The original file is no longer on disk"):
                document.review_summary = (
                    "Recorded from API or manual evidence; no uploaded file is expected."
                )
            metadata.pop("source_missing", None)
            metadata.pop("recovered_without_source", None)
        existing_summary = metadata.get("application_summary")
        if refresh_application_state and (document.review_status or document.parsed_at or isinstance(existing_summary, dict)):
            metadata["application_summary"] = self.document_pipeline.describe_application_state(
                self,
                document=document,
            )
        document.metadata = metadata
        return document

    def list_documents(
        self, limit: int = 20, *, offset: int = 0, view: str = "recent", refresh_application_state: bool = True
    ) -> HouseholdDocumentList:
        page_limit = max(1, min(limit, 1000))
        page_offset = max(0, offset)
        clause = _PENDING_DOCUMENT_SQL if view == "pending" else "TRUE"
        with self.storage.connection() as conn:
            counts = conn.execute(
                f"SELECT COUNT(*), COUNT(*) FILTER (WHERE {_PENDING_DOCUMENT_SQL}) FROM household_documents"
            ).fetchone()
            rows = conn.execute(
                f"{_DOC_SQL} WHERE {clause} ORDER BY uploaded_at DESC, id DESC LIMIT %s OFFSET %s",
                [page_limit, page_offset],
            ).fetchall()
        total, pending = (int(counts[0]), int(counts[1])) if counts else (0, 0)
        documents = [
            self._annotate_document(
                row_to_document(row, to_float=to_float, iso=iso, iso_or_none=iso_or_none),
                refresh_application_state=refresh_application_state,
            ) for row in rows
        ]
        if refresh_application_state:
            self._attach_review_questions(documents)
        return HouseholdDocumentList(
            items=documents,
            total_count=pending if view == "pending" else total,
            pending_count=pending,
            offset=page_offset,
            limit=page_limit,
        )

    def get_document(self, document_id: str) -> HouseholdDocument | None:
        with self.storage.connection() as conn:
            row = conn.execute(f"{_DOC_SQL} WHERE id = %s", [document_id]).fetchone()
        if row is None:
            return None
        document = self._annotate_document(
            row_to_document(row, to_float=to_float, iso=iso, iso_or_none=iso_or_none)
        )
        self._attach_review_questions([document])
        return document

    def _attach_review_questions(self, documents: list[HouseholdDocument]) -> None:
        """One batch reads question text bound to the displayed proposals.

        Presentation context stays separate from the immutable approval payload.
        Historical questions are not asserted to remain unanswered.
        """
        bound: dict[str, HouseholdDocument] = {}
        for document in documents:
            proposal = document.metadata.get("review_proposal")
            if not isinstance(proposal, dict):
                continue
            try:
                review_id = str(UUID(str(proposal.get("review_id"))))
            except ValueError:
                continue
            bound[review_id] = document
        if not bound:
            return
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT id::text, document_id::text, review_payload->'questions' FROM household_document_reviews WHERE id=ANY(%s::uuid[])",
                [list(bound)],
            ).fetchall()
        for review_id, document_id, questions in rows:
            document = bound[review_id]
            if document.id != document_id or not isinstance(questions, list):
                continue
            document.metadata["review_questions"] = [
                str(question["question"]) for question in questions
                if isinstance(question, dict) and question.get("question")
            ]

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
