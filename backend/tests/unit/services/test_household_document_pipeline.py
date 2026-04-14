"""Unit tests for household document pipeline helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, Mock, patch

from app.models.household_finance import HouseholdDocument
from app.services.household_document_pipeline import (
    HouseholdDocumentPipeline,
    _is_duplicate_import_validation,
    _signature_structured_data,
)


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


def test_signature_structured_data_strips_volatile_money_fields() -> None:
    document = HouseholdDocument(
        id="doc-sig",
        filename="20260411-statements-9728-.pdf",
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

    sanitized = _signature_structured_data(
        {
            "source_type": "credit_card",
            "document_type": "statement",
            "structured_data": {
                "account_hint": "Chase Amazon card",
                "provider_name": "Chase",
                "total_amount": "2958.17",
                "statement_period": "2026-03-12 to 2026-04-11",
                "text_preview": "ACCOUNT SUMMARY",
                "financial_accounts": [
                    {
                        "account_name": "Chase Prime Visa / Amazon card",
                        "account_type": "credit_card",
                        "asset_group": "credit",
                        "institution_name": "Chase",
                        "owner_name": "Elias B Leslie",
                        "account_mask": "9728",
                        "match_key": "credit-lineage|chase|prime visa|elias b leslie|credit_card",
                        "balance": "2958.17",
                        "as_of_date": "2026-04-11",
                    }
                ],
            },
        },
        document,
    )

    assert sanitized["account_hint"] == "Chase Amazon card"
    assert "total_amount" not in sanitized
    assert "statement_period" not in sanitized
    financial_accounts = sanitized["financial_accounts"]
    assert isinstance(financial_accounts, list)
    account = financial_accounts[0]
    assert isinstance(account, dict)
    assert account["account_mask"] == "9728"
    assert "balance" not in account
    assert "as_of_date" not in account


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


def test_duplicate_import_validation_requires_known_dataset_and_no_other_changes() -> None:
    assert _is_duplicate_import_validation(
        import_summary={
            "dataset_type": "amazon_order_history",
            "inserted": 0,
            "duplicates": 12,
        },
        transaction_summary={"inserted": 0, "updated": 0},
        evidence_account_count=0,
        planning_count=0,
        inferred_count=0,
    )
    assert not _is_duplicate_import_validation(
        import_summary={
            "dataset_type": "amazon_order_history",
            "inserted": 0,
            "duplicates": 12,
        },
        transaction_summary={"inserted": 1, "updated": 0},
        evidence_account_count=0,
        planning_count=0,
        inferred_count=0,
    )


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


class _RetryPipeline(HouseholdDocumentPipeline):
    def __init__(self) -> None:
        super().__init__()
        self.apply_calls = 0

    def _persist_review(
        self,
        service: Any,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
        now: str,
    ) -> None:
        return None

    def apply_review_outputs(
        self,
        service: Any,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
    ) -> dict[str, object]:
        self.apply_calls += 1
        if self.apply_calls == 1:
            return {
                "status": "incomplete",
                "impacts": [],
                "imports": {"inserted": 0, "duplicates": 0},
                "transactions": {"inserted": 0, "updated": 0, "held_for_date_review": 0},
                "evidence_accounts": 0,
                "planning_items": 0,
                "planning_items_skipped": 0,
                "planning_error": None,
                "inferred_values": 0,
                "needs_follow_up": True,
            }
        return {
            "status": "applied",
            "impacts": ["accounts"],
            "imports": {"inserted": 0, "duplicates": 0},
            "transactions": {"inserted": 0, "updated": 0, "held_for_date_review": 0},
            "evidence_accounts": 1,
            "planning_items": 0,
            "planning_items_skipped": 0,
            "planning_error": None,
            "inferred_values": 0,
            "needs_follow_up": False,
        }

    def upsert_document_signatures(
        self,
        service: Any,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
        application_summary: dict[str, object] | None = None,
        reconciliation_summary: dict[str, object] | None = None,
    ) -> None:
        return None


@patch("app.services.household_document_pipeline.update_document_application_summary")
def test_process_document_review_retries_once_for_retryable_reconciliation(
    update_application_summary: Mock,
    tmp_path: Any,
) -> None:
    statement_path = tmp_path / "statement.txt"
    statement_path.write_text("statement text", encoding="utf-8")
    pipeline = _RetryPipeline()
    connection = MagicMock()
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    context_manager.__exit__.return_value = None
    storage = SimpleNamespace(connection=Mock(return_value=context_manager))
    review_service = SimpleNamespace(
        review=Mock(
            side_effect=[
                {
                    "source_type": "credit_card",
                    "document_type": "statement",
                    "confidence": 0.9,
                    "structured_data": {
                        "financial_accounts": [{"account_name": "Amazon Chase (CC)"}]
                    },
                    "review_checks": {"expected_account_count": 1},
                },
                {
                    "source_type": "credit_card",
                    "document_type": "statement",
                    "confidence": 0.95,
                    "structured_data": {
                        "financial_accounts": [{"account_name": "Amazon Chase (CC)"}]
                    },
                    "review_checks": {"expected_account_count": 1},
                },
            ]
        )
    )
    service = SimpleNamespace(review_service=review_service, storage=storage)
    document = HouseholdDocument(
        id="doc-4",
        filename="statement.txt",
        source_type="credit_card",
        document_type="statement",
        status="parsed",
        account_label=None,
        content_type="text/plain",
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-04-14T00:00:00+00:00",
        metadata={"stored_path": str(statement_path)},
    )

    pipeline.process_document_review(service, document)

    assert review_service.review.call_count == 2
    second_call = review_service.review.call_args_list[1].kwargs
    assert second_call["prior_review"]["review_checks"]["expected_account_count"] == 1
    assert second_call["reconciliation_summary"]["status"] == "needs_retry"
    assert connection.commit.called
    update_application_summary.assert_called_once()
