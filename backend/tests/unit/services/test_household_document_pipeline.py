"""Unit tests for household document pipeline helpers."""

from __future__ import annotations

from app.services.household_document_pipeline import HouseholdDocumentPipeline


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
