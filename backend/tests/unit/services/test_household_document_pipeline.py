"""Unit tests for household document pipeline helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

from app.models.household_finance import HouseholdDocument
from app.services.household_document_pipeline import HouseholdDocumentPipeline


class _PipelineStub(HouseholdDocumentPipeline):
    def import_document_rows(
        self,
        service: Any,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
    ) -> dict[str, object]:
        return {"inserted": 0, "duplicates": 0}


def test_classify_document_detects_retirement_statement() -> None:
    pipeline = HouseholdDocumentPipeline()

    source_type, document_type, confidence = pipeline.classify_document(
        filename="Vanguard Roth IRA March.pdf",
        content_type="application/pdf",
        source_type=None,
        document_type=None,
    )

    assert source_type == "retirement"
    assert document_type == "retirement_statement"
    assert confidence >= 0.9


def test_parse_decimal_handles_parenthetical_negatives() -> None:
    pipeline = HouseholdDocumentPipeline()

    parsed = pipeline.parse_decimal("($123.45)")

    assert parsed == "-123.45"


def test_build_import_row_hash_requires_amazon_identity_fields() -> None:
    pipeline = HouseholdDocumentPipeline()

    row_hash = pipeline.build_import_row_hash(
        dataset_type="amazon_order_history",
        row={
            "Order ID": "123-456",
            "ASIN": "B001",
            "Order Date": "2026-03-01",
            "Original Quantity": "2",
        },
    )

    assert isinstance(row_hash, str)
    assert len(row_hash) == 64


def test_apply_review_outputs_skips_planning_merge_for_account_statement() -> None:
    pipeline = _PipelineStub()
    service = SimpleNamespace(
        transaction_service=SimpleNamespace(
            import_document_transactions=Mock(return_value={"inserted": 0, "updated": 0})
        ),
        evidence_service=SimpleNamespace(
            replace_document_accounts=Mock(return_value=1)
        ),
        merge_planning_items=Mock(),
    )
    document = HouseholdDocument(
        id="doc-1",
        filename="statement.pdf",
        source_type="credit_card",
        document_type="statement",
        status="parsed",
        account_label=None,
        content_type="application/pdf",
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-04-13T00:00:00+00:00",
        metadata={},
    )

    summary = pipeline.apply_review_outputs(
        service,
        document=document,
        reviewed={
            "source_type": "credit_card",
            "document_type": "statement",
            "structured_data": {
                "financial_accounts": [
                    {"account_name": "Amazon Chase (CC)", "balance": "2958.17"}
                ]
            },
            "planning_items": [{"section": "debt_obligations", "label": "Card"}],
        },
    )

    service.merge_planning_items.assert_not_called()
    assert summary["status"] == "applied"
    assert summary["planning_items"] == 0
    assert summary["planning_items_skipped"] == 1
    assert summary["evidence_accounts"] == 1


def test_apply_review_outputs_keeps_account_ingestion_when_planning_merge_fails() -> None:
    pipeline = _PipelineStub()
    service = SimpleNamespace(
        transaction_service=SimpleNamespace(
            import_document_transactions=Mock(return_value={"inserted": 2, "updated": 0})
        ),
        evidence_service=SimpleNamespace(
            replace_document_accounts=Mock(return_value=1)
        ),
        merge_planning_items=Mock(side_effect=RuntimeError("bad planning row")),
    )
    document = HouseholdDocument(
        id="doc-2",
        filename="benefits.pdf",
        source_type="benefits",
        document_type="benefits_summary",
        status="parsed",
        account_label=None,
        content_type="application/pdf",
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-04-13T00:00:00+00:00",
        metadata={},
    )

    summary = pipeline.apply_review_outputs(
        service,
        document=document,
        reviewed={
            "source_type": "benefits",
            "document_type": "benefits_summary",
            "structured_data": {},
            "planning_items": [{"section": "retirement_income_sources", "label": "Pension"}],
        },
    )

    service.merge_planning_items.assert_called_once()
    assert summary["status"] == "applied"
    assert summary["planning_items"] == 0
    assert summary["planning_items_skipped"] == 1
    assert summary["planning_error"] == "bad planning row"
    transactions = summary["transactions"]
    assert isinstance(transactions, dict)
    assert transactions["inserted"] == 2
    assert summary["evidence_accounts"] == 1


def test_process_document_review_skips_missing_source_file() -> None:
    pipeline = HouseholdDocumentPipeline()
    service = SimpleNamespace(
        review_service=SimpleNamespace(review=Mock()),
    )
    document = HouseholdDocument(
        id="doc-3",
        filename="missing.png",
        source_type="brokerage",
        document_type="brokerage_statement",
        status="parsed",
        account_label=None,
        content_type="image/png",
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-04-13T00:00:00+00:00",
        metadata={"stored_path": "/tmp/does-not-exist.png"},
    )

    pipeline.process_document_review(service, document)

    service.review_service.review.assert_not_called()
