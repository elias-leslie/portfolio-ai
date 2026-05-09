"""Unit tests for household document pipeline helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from app.models.household_finance import HouseholdDocument
from app.services.household_document_pipeline import (
    HouseholdDocumentPipeline,
    _apply_upload_account_binding,
    _is_duplicate_import_validation,
    _receipt_line_item_rows,
    _signature_structured_data,
    build_import_row_hash,
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


def test_receipt_line_item_rows_preserve_product_detail() -> None:
    document = HouseholdDocument(
        id="doc-receipt",
        filename="receipt.jpg",
        source_type="receipt",
        document_type="receipt",
        status="parsed",
        account_label=None,
        content_type="image/jpeg",
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-05-04T00:00:00+00:00",
        metadata={},
    )

    rows = _receipt_line_item_rows(
        document=document,
        reviewed={
            "source_type": "receipt",
            "structured_data": {
                "account_hint": "Visa ending 9728",
                "transactions": [
                    {
                        "date": "2026-05-04",
                        "merchant": "Target",
                        "amount": "19.99",
                        "currency": "USD",
                        "payment_method": "Visa credit",
                        "account_mask": "9728",
                        "line_items": [
                            {"description": "Crest 3D White", "amount": "19.99"},
                        ],
                    }
                ],
            },
        },
    )

    assert rows == [
        {
            "Document ID": "doc-receipt",
            "External Row ID": "doc-receipt:0:0",
            "Receipt Index": "0",
            "Line Index": "0",
            "Order Date": "2026-05-04",
            "Merchant": "Target",
            "Product Name": "Crest 3D White",
            "Description": "Crest 3D White",
            "Total Amount": "19.99",
            "Unit Price": "19.99",
            "Original Quantity": "1",
            "Currency": "USD",
            "Payment Method": "Visa credit",
            "Account Mask": "9728",
            "Account Label": "Visa ending 9728",
            "Receipt Total": "19.99",
            "Source": "receipt_line_item",
        }
    ]
    assert build_import_row_hash(dataset_type="receipt_line_items", row=rows[0]) is not None


def test_receipt_line_item_rows_reject_unreconciled_product_detail() -> None:
    document = HouseholdDocument(
        id="doc-receipt",
        filename="receipt.jpg",
        source_type="receipt",
        document_type="receipt",
        status="parsed",
        account_label=None,
        content_type="image/jpeg",
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-05-04T00:00:00+00:00",
        metadata={},
    )

    rows = _receipt_line_item_rows(
        document=document,
        reviewed={
            "source_type": "receipt",
            "structured_data": {
                "transactions": [
                    {
                        "date": "2026-05-04",
                        "merchant": "Target",
                        "amount": "72.89",
                        "line_items": [{"description": "Crest 3D White", "amount": "19.99"}],
                    }
                ],
            },
        },
    )

    assert rows == []


def test_receipt_line_item_rows_accept_subtotal_reconciliation() -> None:
    document = HouseholdDocument(
        id="doc-receipt",
        filename="receipt.jpg",
        source_type="receipt",
        document_type="receipt",
        status="parsed",
        account_label=None,
        content_type="image/jpeg",
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-05-04T00:00:00+00:00",
        metadata={},
    )

    rows = _receipt_line_item_rows(
        document=document,
        reviewed={
            "source_type": "receipt",
            "structured_data": {
                "transactions": [
                    {
                        "date": "2026-05-04",
                        "merchant": "Target",
                        "amount": "21.39",
                        "subtotal": "19.99",
                        "tax_amount": "1.40",
                        "line_items": [{"description": "Crest 3D White", "amount": "19.99"}],
                    }
                ],
            },
        },
    )

    assert len(rows) == 1
    assert rows[0]["Product Name"] == "Crest 3D White"


def test_receipt_line_item_rows_reject_declared_item_count_mismatch() -> None:
    document = HouseholdDocument(
        id="doc-receipt",
        filename="receipt.jpg",
        source_type="receipt",
        document_type="receipt",
        status="parsed",
        account_label=None,
        content_type="image/jpeg",
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-05-04T00:00:00+00:00",
        metadata={},
    )

    rows = _receipt_line_item_rows(
        document=document,
        reviewed={
            "source_type": "receipt",
            "review_checks": {"itemization": {"declared_items_sold": 3}},
            "structured_data": {
                "transactions": [
                    {
                        "date": "2026-05-04",
                        "merchant": "Target",
                        "amount": "10.00",
                        "line_items": [
                            {"description": "Apples", "amount": "4.00"},
                            {"description": "Bread", "amount": "6.00"},
                        ],
                    }
                ],
            },
        },
    )

    assert rows == []


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


def test_describe_application_state_preserves_portfolio_position_snapshot_impact() -> None:
    pipeline = HouseholdDocumentPipeline()
    document = HouseholdDocument(
        id="doc-positions",
        filename="positions.csv",
        source_type="retirement",
        document_type="retirement_statement",
        status="parsed",
        account_label="Traditional IRA",
        content_type="text/csv",
        file_size_bytes=10,
        classification_confidence=0.95,
        uploaded_at="2026-05-02T00:00:00+00:00",
        metadata={
            "application_summary": {
                "status": "applied",
                "impacts": ["accounts", "portfolio_positions"],
                "account_registry": {"evidence_linked": 1},
                "portfolio_positions": {
                    "accounts_scanned": 1,
                    "accounts_linked": 1,
                    "cash_updated": 1,
                    "positions_seen": 4,
                    "positions_inserted": 0,
                    "positions_updated": 0,
                    "positions_unchanged": 4,
                    "positions_deleted": 0,
                },
            }
        },
    )
    connection = MagicMock()
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    context_manager.__exit__.return_value = None
    service = SimpleNamespace(storage=SimpleNamespace(connection=Mock(return_value=context_manager)))

    with patch(
        "app.services.household_document_pipeline.fetch_document_application_counts",
        return_value={
            "import_count": 0,
            "transaction_count": 0,
            "evidence_account_count": 1,
            "inferred_count": 0,
            "dataset_type": None,
        },
    ):
        summary = pipeline.describe_application_state(service, document=document)

    assert summary["status"] == "applied"
    assert summary["impacts"] == ["accounts", "portfolio_positions"]
    assert summary["account_registry"] == {"evidence_linked": 1}
    assert summary["portfolio_positions"] == {
        "accounts_scanned": 1,
        "accounts_linked": 1,
        "cash_updated": 1,
        "positions_seen": 4,
        "positions_inserted": 0,
        "positions_updated": 0,
        "positions_unchanged": 4,
        "positions_deleted": 0,
    }


async def test_duplicate_upload_rebinds_existing_document_to_selected_account() -> None:
    pipeline = HouseholdDocumentPipeline()
    existing = HouseholdDocument(
        id="doc-existing",
        filename="positions.csv",
        source_type="retirement",
        document_type="retirement_statement",
        status="parsed",
        account_label=None,
        content_type="text/csv",
        file_size_bytes=10,
        classification_confidence=0.95,
        uploaded_at="2026-05-02T00:00:00+00:00",
        metadata={"content_sha256": "existing-hash"},
    )
    refreshed = existing.model_copy(
        update={
            "account_label": "Traditional IRA",
            "metadata": {
                "content_sha256": "existing-hash",
                "upload_household_account_id": "household-ira",
                "duplicate_rebound": True,
            },
        }
    )
    connection = MagicMock()
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    context_manager.__exit__.return_value = None
    service = SimpleNamespace(
        get_document=Mock(return_value=refreshed),
        storage=SimpleNamespace(connection=Mock(return_value=context_manager)),
    )
    pipeline.find_duplicate_document_by_hash = Mock(return_value=existing)  # type: ignore[method-assign]
    upload = SimpleNamespace(
        filename="positions.csv",
        content_type="text/csv",
        read=AsyncMock(side_effect=[b"same bytes", b""]),
    )

    result = await pipeline.ingest_document(
        service,
        upload=upload,
        account_label="Traditional IRA",
        household_account_id="household-ira",
    )

    connection.execute.assert_called_once()
    assert "metadata = COALESCE" in connection.execute.call_args.args[0]
    assert result.id == "doc-existing"
    assert result.account_label == "Traditional IRA"
    assert result.metadata["upload_household_account_id"] == "household-ira"
    assert result.metadata["duplicate_detected"] is True
    assert result.metadata["duplicate_rebound"] is True


def test_upload_account_binding_attaches_single_account_to_selected_household_account() -> None:
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (
        "household-ira",
        "Traditional IRA",
        "retirement",
        "retirement",
        "ira",
        "Fidelity",
        None,
        "245944181",
        "institution-mask::fidelity|245944181",
    )
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    context_manager.__exit__.return_value = None
    service = SimpleNamespace(storage=SimpleNamespace(connection=Mock(return_value=context_manager)))
    document = HouseholdDocument(
        id="doc-positions",
        filename="Portfolio_Positions_May-02-2026.csv",
        source_type="retirement",
        document_type="retirement_statement",
        status="parsed",
        account_label="Traditional IRA",
        content_type="text/csv",
        file_size_bytes=10,
        classification_confidence=0.95,
        uploaded_at="2026-05-02T00:00:00+00:00",
        metadata={"upload_household_account_id": "household-ira"},
    )

    reviewed = _apply_upload_account_binding(
        service,
        document=document,
        reviewed={
            "source_type": "retirement",
            "document_type": "retirement_statement",
            "structured_data": {
                "financial_accounts": [
                    {
                        "account_name": "Traditional IRA",
                        "institution_name": "Fidelity",
                        "account_mask": "245944181",
                        "balance": "372006.79",
                    }
                ]
            },
        },
    )

    structured_data = reviewed["structured_data"]
    assert isinstance(structured_data, dict)
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    account = accounts[0]
    assert isinstance(account, dict)
    assert account["household_account_id"] == "household-ira"
    assert account["match_key"] == "institution-mask::fidelity|245944181"
    assert reviewed.get("questions") == []
    assert reviewed.get("review_checks") == {"ambiguity_remaining": False}


def test_upload_account_binding_accepts_provider_prefixed_matching_mask() -> None:
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (
        "household-chase",
        "Amazon Chase (CC)",
        "credit_card",
        "credit",
        "credit_card",
        "Chase",
        "Elias B Leslie",
        "9728",
        "credit-lineage|chase|chase prime visa / amazon card|elias b leslie|credit_card",
    )
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    context_manager.__exit__.return_value = None
    service = SimpleNamespace(storage=SimpleNamespace(connection=Mock(return_value=context_manager)))
    document = HouseholdDocument(
        id="doc-chase-activity",
        filename="Chase9728_Activity20260101_20260502_20260502.CSV",
        source_type="credit_card",
        document_type="statement",
        status="parsed",
        account_label="Chase Prime Visa / Amazon card",
        content_type="text/csv",
        file_size_bytes=10,
        classification_confidence=0.95,
        uploaded_at="2026-05-02T00:00:00+00:00",
        metadata={"upload_household_account_id": "household-chase"},
    )

    reviewed = _apply_upload_account_binding(
        service,
        document=document,
        reviewed={
            "source_type": "credit_card",
            "document_type": "statement",
            "structured_data": {
                "financial_accounts": [
                    {
                        "account_name": "Chase credit card activity export",
                        "institution_name": "Chase",
                        "account_mask": "Chase9728",
                        "extracted_account_mask": "9728",
                        "account_type": "credit_card",
                    }
                ]
            },
            "review_checks": {"ambiguity_remaining": True},
        },
    )

    structured_data = reviewed["structured_data"]
    assert isinstance(structured_data, dict)
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    account = accounts[0]
    assert isinstance(account, dict)
    assert account["household_account_id"] == "household-chase"
    assert reviewed.get("questions") == []
    assert reviewed.get("review_checks") == {"ambiguity_remaining": False}


def test_upload_account_binding_asks_when_selected_account_conflicts() -> None:
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (
        "household-ira",
        "Traditional IRA",
        "retirement",
        "retirement",
        "ira",
        "Fidelity",
        None,
        "245944181",
        "institution-mask::fidelity|245944181",
    )
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    context_manager.__exit__.return_value = None
    service = SimpleNamespace(storage=SimpleNamespace(connection=Mock(return_value=context_manager)))
    document = HouseholdDocument(
        id="doc-wrong",
        filename="wrong.csv",
        source_type="retirement",
        document_type="retirement_statement",
        status="parsed",
        account_label="Traditional IRA",
        content_type="text/csv",
        file_size_bytes=10,
        classification_confidence=0.95,
        uploaded_at="2026-05-02T00:00:00+00:00",
        metadata={"upload_household_account_id": "household-ira"},
    )

    reviewed = _apply_upload_account_binding(
        service,
        document=document,
        reviewed={
            "source_type": "retirement",
            "document_type": "retirement_statement",
            "structured_data": {
                "financial_accounts": [
                    {
                        "account_name": "ROTH IRA",
                        "institution_name": "Fidelity",
                        "account_mask": "250696445",
                        "balance": "48014.15",
                    }
                ]
            },
        },
    )

    structured_data = reviewed["structured_data"]
    assert isinstance(structured_data, dict)
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    account = accounts[0]
    assert isinstance(account, dict)
    assert "household_account_id" not in account
    review_checks = reviewed["review_checks"]
    assert isinstance(review_checks, dict)
    assert review_checks["ambiguity_remaining"] is True
    questions = reviewed["questions"]
    assert isinstance(questions, list)
    question = questions[0]
    assert isinstance(question, dict)
    assert "Which account should this evidence update?" in str(question["question"])


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


def test_apply_review_outputs_promotes_transaction_export_from_financial_accounts() -> None:
    pipeline = _PipelineStub()
    captured: dict[str, object] = {}

    def _import_document_transactions(*, document: HouseholdDocument, reviewed: dict[str, object]) -> dict[str, int]:
        captured.update(reviewed)
        return {"inserted": 3, "updated": 0}

    service = SimpleNamespace(
        transaction_service=SimpleNamespace(
            import_document_transactions=Mock(side_effect=_import_document_transactions)
        ),
        evidence_service=SimpleNamespace(
            replace_document_accounts=Mock(return_value=1)
        ),
        merge_planning_items=Mock(),
    )
    document = HouseholdDocument(
        id="doc-chase",
        filename="Chase9728_Activity20260101_20260416_20260416.CSV",
        source_type="other",
        document_type="other",
        status="parsed",
        account_label=None,
        content_type="text/csv",
        file_size_bytes=10,
        classification_confidence=0.55,
        uploaded_at="2026-04-16T00:00:00+00:00",
        metadata={},
    )

    summary = pipeline.apply_review_outputs(
        service,
        document=document,
        reviewed={
            "source_type": "other",
            "document_type": "other",
            "summary": "Uploaded other from other.",
            "extracted_text": (
                "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
                "04/14/2026,04/15/2026,Amazon.com*B784J4QP1,Shopping,Sale,-28.86,\n"
            ),
            "structured_data": {
                "provider_name": "Chase",
                "account_hint": "Chase credit card activity export",
                "financial_accounts": [
                    {
                        "asset_group": "credit",
                        "account_type": "credit_card",
                        "institution_name": "Chase",
                        "account_name": "Chase Amazon card",
                        "account_mask": "9728",
                    }
                ],
            },
        },
    )

    assert captured["source_type"] == "credit_card"
    assert captured["document_type"] == "statement"
    assert summary["status"] == "applied"
    assert "transactions" in summary["impacts"]


def test_process_document_review_skips_missing_source_file() -> None:
    pipeline = HouseholdDocumentPipeline()
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = None
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    context_manager.__exit__.return_value = None
    service = SimpleNamespace(
        review_service=SimpleNamespace(review=Mock()),
        storage=SimpleNamespace(connection=Mock(return_value=context_manager)),
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
    assert not connection.commit.called


@patch("app.services.household_document_pipeline.update_document_application_summary")
def test_process_document_review_reapplies_latest_review_when_source_missing(
    update_application_summary: Mock,
) -> None:
    pipeline = _PipelineStub()
    connection = MagicMock()
    connection.execute.return_value.fetchone.return_value = (
        "Recovered statement",
        0.94,
        "Transaction history",
        {
            "financial_accounts": [
                {"account_name": "Wells Fargo Everyday Checking"}
            ]
        },
    )
    context_manager = MagicMock()
    context_manager.__enter__.return_value = connection
    context_manager.__exit__.return_value = None
    service = SimpleNamespace(
        review_service=SimpleNamespace(review=Mock()),
        storage=SimpleNamespace(connection=Mock(return_value=context_manager)),
        transaction_service=SimpleNamespace(
            import_document_transactions=Mock(return_value={"inserted": 2, "updated": 1, "deleted": 3})
        ),
        evidence_service=SimpleNamespace(
            replace_document_accounts=Mock(return_value=1)
        ),
        merge_planning_items=Mock(),
    )
    document = HouseholdDocument(
        id="doc-3a",
        filename="missing.pdf",
        source_type="bank",
        document_type="statement",
        status="parsed",
        account_label="Wells Fargo Everyday Checking",
        content_type="application/pdf",
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-04-13T00:00:00+00:00",
        metadata={"stored_path": "/tmp/does-not-exist.pdf"},
    )

    pipeline.process_document_review(service, document)

    service.review_service.review.assert_not_called()
    service.transaction_service.import_document_transactions.assert_called_once()
    service.evidence_service.replace_document_accounts.assert_called_once()
    assert connection.commit.called
    update_application_summary.assert_called_once()
    application_summary = update_application_summary.call_args.kwargs["application_summary"]
    transactions = application_summary["transactions"]
    assert transactions["deleted"] == 3


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


def _reconciliation_document(content_type: str) -> HouseholdDocument:
    return HouseholdDocument(
        id="doc-recon",
        filename="snapshot",
        source_type="credit_card",
        document_type="statement",
        status="parsed",
        account_label=None,
        content_type=content_type,
        file_size_bytes=10,
        classification_confidence=0.9,
        uploaded_at="2026-05-08T00:00:00+00:00",
        metadata={},
    )


def _reconciliation_application_summary() -> dict[str, object]:
    return {
        "status": "applied",
        "impacts": ["accounts"],
        "imports": {"inserted": 0, "duplicates": 0},
        "transactions": {"inserted": 0, "updated": 0, "held_for_date_review": 0},
        "evidence_accounts": 1,
    }


def _reconciliation_review_payload() -> dict[str, object]:
    return {
        "source_type": "credit_card",
        "document_type": "statement",
        "structured_data": {"financial_accounts": [{"account_name": "Chase Prime Visa"}]},
    }


def test_reconciliation_image_statement_does_not_flag_missing_transactions() -> None:
    pipeline = HouseholdDocumentPipeline()

    summary = pipeline._build_reconciliation_summary(
        document=_reconciliation_document("image/jpeg"),
        reviewed=_reconciliation_review_payload(),
        application_summary=_reconciliation_application_summary(),
    )

    assert summary["status"] == "clear"
    assert summary["issues"] == []


def test_reconciliation_text_statement_still_flags_missing_transactions() -> None:
    pipeline = HouseholdDocumentPipeline()

    summary = pipeline._build_reconciliation_summary(
        document=_reconciliation_document("application/pdf"),
        reviewed=_reconciliation_review_payload(),
        application_summary=_reconciliation_application_summary(),
    )

    assert summary["status"] == "needs_retry"
    issues = summary["issues"]
    assert isinstance(issues, list)
    assert any(
        isinstance(issue, dict) and issue.get("code") == "missing_transactions"
        for issue in issues
    )
