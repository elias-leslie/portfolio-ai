from __future__ import annotations

from types import SimpleNamespace

from app.models.household_finance import HouseholdDocument
from app.services._household_finance_document_methods import _HFDocumentMethods


class _DocumentService(_HFDocumentMethods):
    def __init__(self) -> None:
        self.document_pipeline = SimpleNamespace(describe_application_state=lambda *_args, **_kwargs: {})


def _document(*, source_type: str, document_type: str, metadata: dict[str, object]) -> HouseholdDocument:
    return HouseholdDocument(
        id="doc-1",
        filename="Plaid - Chase",
        source_type=source_type,
        document_type=document_type,
        status="parsed",
        account_label="Chase",
        file_size_bytes=0,
        content_type=None,
        classification_confidence=None,
        review_status=None,
        review_summary=None,
        review_confidence=None,
        statement_start=None,
        statement_end=None,
        uploaded_at="2026-07-01T00:00:00+00:00",
        parsed_at="2026-07-01T00:00:00+00:00",
        metadata=metadata,
    )


def test_annotate_document_does_not_mark_api_sync_source_file_missing() -> None:
    document = _document(
        source_type="plaid",
        document_type="api_sync",
        metadata={"source": "plaid"},
    )

    annotated = _DocumentService()._annotate_document(document)

    assert "file_available" not in annotated.metadata


def test_annotate_document_marks_uploaded_missing_source_file() -> None:
    document = _document(
        source_type="receipt",
        document_type="receipt",
        metadata={"stored_path": "/tmp/not-here.pdf"},
    )

    annotated = _DocumentService()._annotate_document(document)

    assert annotated.metadata["file_available"] is False
