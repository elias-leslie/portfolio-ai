"""Document-related methods mixed into HouseholdFinanceService."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import UploadFile

from app.models.household_finance import HouseholdDocument, HouseholdDocumentList
from app.services._household_finance_utils import iso, iso_or_none, to_float
from app.services.household_finance_rows import row_to_document

if TYPE_CHECKING:
    pass

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

    async def ingest_document(
        self,
        *,
        upload: UploadFile,
        source_type: str | None = None,
        document_type: str | None = None,
        account_label: str | None = None,
    ) -> HouseholdDocument:
        return await self.document_pipeline.ingest_document(
            self, upload=upload, source_type=source_type,
            document_type=document_type, account_label=account_label,
        )

    def list_documents(self, limit: int = 20) -> HouseholdDocumentList:
        with self.storage.connection() as conn:
            rows = conn.execute(
                f"{_DOC_SQL} ORDER BY uploaded_at DESC LIMIT %s", [limit]
            ).fetchall()
        return HouseholdDocumentList(
            items=[row_to_document(row, to_float=to_float, iso=iso, iso_or_none=iso_or_none) for row in rows]
        )

    def get_document(self, document_id: str) -> HouseholdDocument | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                f"{_DOC_SQL} WHERE id = %s", [document_id]
            ).fetchone()
        return row_to_document(row, to_float=to_float, iso=iso, iso_or_none=iso_or_none) if row is not None else None

    def review_document(self, document_id: str) -> None:
        self.document_pipeline.review_document(self, document_id)
