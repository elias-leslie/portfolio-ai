"""Unit tests for household document review parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

from app.services.household_document_review import (
    HouseholdDocumentReviewService,
    _baseline_review,
    _build_messages,
    _extract_csv_text,
    _extract_text,
    _parse_review_payload,
)

# Patch targets use the module where the name is looked up at runtime.
_TEXT_MODULE = "app.services._household_document_text"
_LLM_MODULE = "app.services._household_document_llm"
_REVIEW_MODULE = "app.services.household_document_review"


def test_parse_review_payload_handles_fenced_json() -> None:
    payload = _parse_review_payload(
        """
        Here is the review.

        ```json
        {
          "summary": "Checking statement",
          "document_type": "statement",
          "source_type": "bank",
          "confidence": 0.9,
          "structured_data": {},
          "inferred_values": [],
          "questions": []
        }
        ```
        """
    )

    assert payload["document_type"] == "statement"
    assert payload["source_type"] == "bank"


def test_parse_review_payload_handles_plain_text_wrapped_json() -> None:
    payload = _parse_review_payload(
        'Review result: {"summary":"Receipt","document_type":"receipt","source_type":"receipt","confidence":0.8,"structured_data":{},"inferred_values":[],"questions":[]}'
    )

    assert payload["document_type"] == "receipt"
    assert payload["source_type"] == "receipt"


def test_baseline_review_detects_walmart_order_details() -> None:
    payload = _baseline_review(
        filename="Order details - Walmart.com.pdf",
        source_type="other",
        document_type="other",
        extracted_text="Order details - Walmart.com\nFresh Whole Brussels Sprouts\nOrder total $83.21",
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["document_type"] == "receipt"
    assert payload["source_type"] == "receipt"
    assert structured_data["merchant"] == "Walmart"


def test_baseline_review_detects_amazon_order_history_csv() -> None:
    payload = _baseline_review(
        filename="Order History.csv",
        source_type="other",
        document_type="other",
        extracted_text="Order Date,Order ID,Payment Instrument Type,Website\n2026-03-01,123-1234567-1234567,VISA,Amazon.com",
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["document_type"] == "receipt"
    assert payload["source_type"] == "receipt"
    assert structured_data["merchant"] == "Amazon"


def test_baseline_review_detects_chase_activity_csv() -> None:
    payload = _baseline_review(
        filename="Chase9728_Activity20260101_20260416_20260416.CSV",
        source_type="other",
        document_type="other",
        extracted_text=(
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "04/14/2026,04/15/2026,Amazon.com*B784J4QP1,Shopping,Sale,-28.86,\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])
    financial_accounts = cast(list[dict[str, Any]], structured_data["financial_accounts"])

    assert payload["document_type"] == "statement"
    assert payload["source_type"] == "credit_card"
    assert structured_data["account_hint"] == "Chase credit card activity export"
    assert financial_accounts[0]["account_mask"] == "9728"
    assert financial_accounts[0]["account_type"] == "credit_card"


def test_extract_csv_text_preserves_amazon_price_columns(tmp_path: Path) -> None:
    csv_path = tmp_path / "Order History.csv"
    csv_path.write_text(
        (
            "ASIN,Order Date,Order ID,Original Quantity,Shipping Charge,Total Amount,Unit Price\n"
            "B001,2026-03-01T00:00:00Z,111-1111111-1111111,1,0,40.93,20.99\n"
        ),
        encoding="utf-8",
    )

    extracted = _extract_csv_text(csv_path)

    assert "Shipping Charge" in extracted
    assert "Total Amount" in extracted
    assert "Unit Price" in extracted
    assert "40.93" in extracted


def test_extract_text_reads_ofx_like_exports(tmp_path: Path) -> None:
    ofx_path = tmp_path / "transactions.ofx"
    ofx_path.write_text(
        "<OFX><BANKMSGSRSV1><STMTTRNRS><BANKTRANLIST><STMTTRN><TRNAMT>-12.34</TRNAMT></STMTTRN>",
        encoding="utf-8",
    )

    extracted = _extract_text(ofx_path, "application/x-ofx")

    assert extracted is not None
    assert "<BANKMSGSRSV1>" in extracted
    assert "<STMTTRN>" in extracted


@patch(f"{_TEXT_MODULE}._extract_pdf_image_text")
@patch(f"{_TEXT_MODULE}.PdfReader")
def test_extract_pdf_text_uses_ocr_fallback_for_low_signal_pages(
    mock_pdf_reader: MagicMock,
    pdf_image_text: MagicMock,
    tmp_path: Path,
) -> None:
    from app.services._household_document_text import _extract_pdf_text

    pdf_path = tmp_path / "walmart.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Order details - Walmart.com"
    mock_pdf_reader.return_value.pages = [mock_page]
    pdf_image_text.return_value = "Fresh Whole Brussels Sprouts\nOrder total $83.21"

    extracted = _extract_pdf_text(pdf_path)

    pdf_image_text.assert_called_once_with(pdf_path)
    assert extracted is not None
    assert "Order details - Walmart.com" in extracted
    assert "Order total $83.21" in extracted


@patch(f"{_TEXT_MODULE}.PdfReader")
def test_extract_pdf_text_keeps_later_statement_pages(
    mock_pdf_reader: MagicMock,
    tmp_path: Path,
) -> None:
    from app.services._household_document_text import _extract_pdf_text

    pdf_path = tmp_path / "statement.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    pages = []
    for index in range(6):
        page = MagicMock()
        page.extract_text.return_value = f"Page {index + 1} summary\n"
        pages.append(page)
    pages[4].extract_text.return_value = (
        "Page 5 transactions\n"
        "Date of Transaction Merchant  Name or Transaction Description $ Amount\n"
        "04/10 Amazon.com 10.77\n"
    )
    mock_pdf_reader.return_value.pages = pages

    extracted = _extract_pdf_text(pdf_path)

    assert extracted is not None
    assert "Page 5 transactions" in extracted
    assert "04/10 Amazon.com 10.77" in extracted


@patch(f"{_TEXT_MODULE}._extract_image_text")
def test_extract_text_uses_image_ocr(image_ocr: MagicMock, tmp_path: Path) -> None:
    image_ocr.return_value = "Walmart 23.41 VISA"
    image_path = tmp_path / "receipt.png"
    image_path.write_bytes(b"fake-image")

    extracted = _extract_text(image_path, "image/png")

    image_ocr.assert_called_once_with(image_path)
    assert extracted == "Walmart 23.41 VISA"


def test_baseline_review_detects_wells_fargo_checking_statement() -> None:
    payload = _baseline_review(
        filename="022726 WellsFargo.pdf",
        source_type="other",
        document_type="other",
        extracted_text="Wells Fargo Everyday Checking\nFebruary 27, 2026 Page 1 of 5",
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["document_type"] == "statement"
    assert payload["source_type"] == "bank"
    assert structured_data["account_hint"] == "Wells Fargo Everyday Checking"


def test_baseline_review_keeps_chase_statement_when_walmart_merchant_appears() -> None:
    payload = _baseline_review(
        filename="20260311-statements-9728-.pdf",
        source_type="other",
        document_type="other",
        extracted_text=(
            "AUTOPAY IS ON\n"
            "www.chase.com/amazon\n"
            "Date of\n"
            "Transaction Merchant  Name or Transaction Description $ Amount\n"
            "02/22     WAL-MART #1712 LARGO FL -83.31\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["document_type"] == "statement"
    assert payload["source_type"] == "credit_card"
    assert structured_data["account_hint"] == "Chase Amazon card"


def test_baseline_review_detects_529_college_fund_snapshot() -> None:
    payload = _baseline_review(
        filename="image.png",
        source_type="other",
        document_type="other",
        extracted_text=(
            "College Fnd - Nadia\n"
            "$3,087.29\n"
            "529 COLL-ME-Edge22Z-87861\n"
            "College Fnd - Sophia\n"
            "$3,089.15\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["document_type"] == "brokerage_statement"
    assert payload["source_type"] == "brokerage"
    assert structured_data["account_hint"] == "529 college savings snapshot (2 accounts)"
    assert "529" in payload["summary"]
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    assert len(accounts) == 2
    assert accounts[0]["account_type"] == "529"
    assert accounts[0]["account_name"] == "529 - Nadia"
    assert accounts[0]["balance"] == "3087.29"
    assert accounts[1]["account_name"] == "529 - Sophia"
    assert accounts[1]["balance"] == "3089.15"
    assert structured_data["total_amount"] == "6176.44"


def test_baseline_review_splits_collegeamerica_multi_account_snapshot() -> None:
    payload = _baseline_review(
        filename="add-anything.txt",
        source_type="other",
        document_type="other",
        extracted_text=(
            "Your Portfolio\n"
            "$26,371.00\n"
            "Total Portfolio Value as of 04/10/2026\n"
            "87595967\n"
            "VCSP/COLLEGEAMERICA MARIANA LESLIE OWNER FBO SOPHIA O LESLIE\tAccount Value\n"
            "$13,185.50\n"
            "Total Account Value\n"
            "$13,185.50\n"
            "87595982\n"
            "VCSP/COLLEGEAMERICA MARIANA LESLIE OWNER FBO NADIA R LESLIE\tAccount Value\n"
            "$13,185.50\n"
            "Total Account Value\n"
            "$13,185.50\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["document_type"] == "brokerage_statement"
    assert payload["source_type"] == "brokerage"
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    assert len(accounts) == 2
    assert accounts[0]["account_mask"] == "87595967"
    assert accounts[0]["account_name"] == "529 - Sophia O Leslie"
    assert accounts[1]["account_mask"] == "87595982"
    assert accounts[1]["account_name"] == "529 - Nadia R Leslie"
    assert structured_data["total_amount"] == "26371.00"


def test_build_signature_candidates_skips_generic_add_anything_filename() -> None:
    service = HouseholdDocumentReviewService()

    candidates = service.build_signature_candidates(
        filename="add-anything.bin",
        extracted_text="Random account text",
    )

    assert all(candidate[0] != "filename_pattern" for candidate in candidates)


def test_merge_llm_result_does_not_reintroduce_baseline_questions() -> None:
    merged = HouseholdDocumentReviewService._merge_llm_result(
        {
            "summary": "Clear brokerage snapshot",
            "source_type": "brokerage",
            "document_type": "brokerage_statement",
            "confidence": 0.96,
            "structured_data": {
                "financial_accounts": [
                    {
                        "account_name": "Individual - TOD",
                        "account_mask": "Z35217544",
                    }
                ]
            },
        },
        baseline={
            "summary": "Baseline summary",
            "source_type": "brokerage",
            "document_type": "brokerage_statement",
            "confidence": 0.7,
            "structured_data": {"account_hint": "Individual - TOD"},
            "questions": [{"question": "Old baseline ask"}],
        },
        extracted_text="Account positions as of 2026-04-13",
    )

    assert merged["questions"] == []
    assert merged["review_checks"]["expected_account_count"] == 1
    assert merged["review_checks"]["expects_transaction_activity"] is False
    assert merged["review_checks"]["ambiguity_remaining"] is False


def test_merge_llm_result_defaults_transaction_expectation_for_card_activity() -> None:
    merged = HouseholdDocumentReviewService._merge_llm_result(
        {
            "summary": "Card activity export",
            "source_type": "credit_card",
            "document_type": "statement",
            "confidence": 0.8,
            "structured_data": {
                "financial_accounts": [
                    {
                        "account_name": "Chase Amazon card",
                    }
                ]
            },
        },
        baseline={
            "summary": "Baseline",
            "source_type": "credit_card",
            "document_type": "statement",
            "confidence": 0.6,
            "structured_data": {},
            "questions": [],
        },
        extracted_text="Activity Date Description Amount Running Balance",
    )

    assert merged["review_checks"]["expected_account_count"] == 1
    assert merged["review_checks"]["expects_transaction_activity"] is True


def test_reconcile_reviewed_accounts_reuses_canonical_credit_identity() -> None:
    service = HouseholdDocumentReviewService(agent_service=MagicMock())

    reviewed = service._reconcile_reviewed_accounts(
        reviewed={
            "source_type": "credit_card",
            "document_type": "statement",
            "structured_data": {
                "financial_accounts": [
                    {
                        "account_name": "Chase Prime Visa / Amazon card",
                        "account_type": "credit_card",
                        "asset_group": "credit",
                        "institution_name": "Chase",
                        "owner_name": "Elias B Leslie",
                        "account_mask": "5313",
                        "match_key": "credit-lineage|chase|prime visa|elias b leslie|credit_card",
                    }
                ]
            },
        },
        household_context={
            "related_accounts": [
                {
                    "household_account_id": "household-chase",
                    "canonical_label": "Amazon Chase (CC)",
                    "source_type": "credit_card",
                    "asset_group": "credit",
                    "account_type": "credit_card",
                    "institution_name": "Chase",
                    "owner_name": "Elias B Leslie",
                    "account_mask": "9728",
                    "primary_identity_key": "credit-lineage|chase|prime visa|elias b leslie|credit_card",
                    "identity_examples": [
                        "credit-lineage|chase|prime visa|elias b leslie|credit_card",
                        "institution-mask::chase|9728",
                    ],
                }
            ]
        },
        filename="20260411-statements-9728-.pdf",
    )

    structured_data = cast(dict[str, Any], reviewed["structured_data"])
    account = cast(dict[str, Any], structured_data["financial_accounts"][0])
    assert account["household_account_id"] == "household-chase"
    assert account["match_key"] == "credit-lineage|chase|prime visa|elias b leslie|credit_card"
    assert account["account_mask"] == "9728"
    assert account["extracted_account_mask"] == "5313"
    assert reviewed["review_checks"]["canonical_match_count"] == 1


def test_reconcile_reviewed_accounts_links_transaction_only_export_to_known_account() -> None:
    service = HouseholdDocumentReviewService(agent_service=MagicMock())

    reviewed = service._reconcile_reviewed_accounts(
        reviewed={
            "source_type": "credit_card",
            "document_type": "statement",
            "structured_data": {
                "financial_accounts": [
                    {
                        "account_name": "Chase Amazon card",
                        "account_type": "credit_card",
                        "asset_group": "credit",
                        "institution_name": "Chase",
                        "owner_name": "Elias B Leslie",
                        "match_key": "credit-lineage|chase|prime visa|elias b leslie|credit_card",
                    }
                ]
            },
        },
        household_context={
            "related_accounts": [
                {
                    "household_account_id": "household-chase",
                    "canonical_label": "Amazon Chase (CC)",
                    "source_type": "credit_card",
                    "asset_group": "credit",
                    "account_type": "credit_card",
                    "institution_name": "Chase",
                    "owner_name": "Elias B Leslie",
                    "account_mask": "9728",
                    "primary_identity_key": "credit-lineage|chase|prime visa|elias b leslie|credit_card",
                    "identity_examples": [
                        "credit-lineage|chase|prime visa|elias b leslie|credit_card",
                    ],
                }
            ]
        },
        filename="Chasenull_Activity20260101_20260414_20260414.CSV",
    )

    structured_data = cast(dict[str, Any], reviewed["structured_data"])
    account = cast(dict[str, Any], structured_data["financial_accounts"][0])
    assert account["household_account_id"] == "household-chase"


def test_reconcile_reviewed_accounts_preserves_explicit_match_key_over_stale_primary() -> None:
    service = HouseholdDocumentReviewService(agent_service=MagicMock())

    reviewed = service._reconcile_reviewed_accounts(
        reviewed={
            "source_type": "credit_card",
            "document_type": "statement",
            "structured_data": {
                "financial_accounts": [
                    {
                        "account_name": "Chase Prime Visa / Amazon card",
                        "account_type": "credit_card",
                        "asset_group": "credit",
                        "institution_name": "Chase",
                        "owner_name": "Elias B Leslie",
                        "account_mask": "9728",
                        "match_key": "credit-lineage|chase|chase prime visa / amazon card|elias b leslie|credit_card",
                    }
                ]
            },
        },
        household_context={
            "related_accounts": [
                {
                    "household_account_id": "household-chase",
                    "canonical_label": "Amazon Chase (CC)",
                    "source_type": "credit_card",
                    "asset_group": "credit",
                    "account_type": "credit_card",
                    "institution_name": "Chase",
                    "owner_name": "Elias B Leslie",
                    "account_mask": "5313",
                    "primary_identity_key": "mask::5313|credit|credit_card",
                    "identity_examples": [
                        "credit-lineage|chase|chase prime visa / amazon card|elias b leslie|credit_card",
                        "mask::5313|credit|credit_card",
                    ],
                }
            ]
        },
        filename="20260411-statements-9728-.pdf",
    )

    structured_data = cast(dict[str, Any], reviewed["structured_data"])
    account = cast(dict[str, Any], structured_data["financial_accounts"][0])
    assert account["household_account_id"] == "household-chase"
    assert account["match_key"] == "credit-lineage|chase|chase prime visa / amazon card|elias b leslie|credit_card"
    assert account["account_mask"] == "9728"
    assert account["account_mask"] == "9728"


def test_merge_signature_pattern_with_baseline_keeps_signature_financial_accounts() -> None:
    merged = HouseholdDocumentReviewService._merge_signature_pattern_with_baseline(
        signature_review={
            "summary": "Signature",
            "document_type": "statement",
            "source_type": "credit_card",
            "confidence": 0.98,
            "structured_data": {
                "financial_accounts": [
                    {
                        "account_name": "Chase Amazon card",
                        "account_mask": "9728",
                        "balance": "2958.17",
                    }
                ]
            },
            "questions": [],
        },
        baseline={
            "summary": "Baseline",
            "document_type": "statement",
            "source_type": "credit_card",
            "confidence": 0.7,
            "structured_data": {
                "account_hint": "Chase Amazon card",
                "total_amount": "2958.17",
            },
            "questions": [{"question": "Old baseline ask"}],
            "inferred_values": [],
        },
        extracted_text="ACCOUNT SUMMARY\nNew Balance: $2,958.17",
    )

    structured_data = cast(dict[str, Any], merged["structured_data"])
    assert structured_data["financial_accounts"][0]["account_mask"] == "9728"
    assert structured_data["total_amount"] == "2958.17"
    assert merged["questions"] == []


def test_signature_review_skips_weak_money_signature_without_financial_accounts() -> None:
    service = HouseholdDocumentReviewService()
    with patch.object(
        service,
        "_find_signature",
        MagicMock(
            return_value={
                "id": "sig-1",
                "signature_type": "text_prefix",
                "source_type": "brokerage",
                "document_type": "brokerage_statement",
                "merchant": None,
                "account_hint": "529 college savings account",
                "confidence": 0.97,
                "structured_data": {},
            }
        ),
    ):
        reviewed = service._signature_review(
            filename="add-anything.bin",
            extracted_text="College Fnd - Sophia\n$3,147.46",
        )

    assert reviewed is None


@patch(f"{_REVIEW_MODULE}._extract_text")
def test_review_skips_filename_signature_only_money_doc_without_financial_accounts(
    extract_text: MagicMock,
) -> None:
    extract_text.return_value = (
        "ACCOUNT SUMMARY\n"
        "New Balance: $3,623.21\n"
        "www.chase.com/amazon\n"
    )
    service = HouseholdDocumentReviewService(agent_service=MagicMock())
    with (
        patch.object(
            service,
            "_signature_review",
            MagicMock(
                return_value={
                    "summary": "Matched learned filename pattern.",
                    "document_type": "statement",
                    "source_type": "credit_card",
                    "confidence": 0.98,
                    "structured_data": {"account_hint": "Chase Amazon card"},
                    "_signature_type": "filename_pattern",
                }
            ),
        ),
        patch.object(
            service,
            "_review_with_llm",
            MagicMock(
                return_value={
                    "summary": "Agent review",
                    "document_type": "statement",
                    "source_type": "credit_card",
                    "confidence": 0.95,
                    "structured_data": {
                        "financial_accounts": [
                            {
                                "account_name": "Chase Amazon card",
                                "account_mask": "9728",
                            }
                        ]
                    },
                    "questions": [],
                }
            ),
        ) as review_with_llm,
    ):
        reviewed = service.review(
            document_id="doc-1",
            filename="20260311-statements-9728-.pdf",
            stored_path=Path("/tmp/fake.pdf"),
            content_type="application/pdf",
            source_type="other",
            document_type="other",
        )

    assert review_with_llm.called
    assert reviewed["_review_strategy"] == "agent"
    structured_data = cast(dict[str, Any], reviewed["structured_data"])
    assert structured_data["financial_accounts"][0]["account_mask"] == "9728"


def test_baseline_review_detects_cash_management_account_text() -> None:
    payload = _baseline_review(
        filename="add-anything.txt",
        source_type="other",
        document_type="other",
        extracted_text=(
            "Cash Management (Joint WROS)\n"
            "Cash Account: Z38367298\n"
            "As of Apr-08-2026 8:29 AM ET\n"
            "Account total balance, $39,400.59\n"
            "Cash available to withdraw\n"
            "$33,400.59\n"
            "Recent activity\n"
            "Apr-08-2026\n"
            "DIRECT DEBIT DUKEENERGY BILL PAY (Cash)\n"
            "-$142.25\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["document_type"] == "brokerage_statement"
    assert payload["source_type"] == "brokerage"
    assert structured_data["account_hint"] == "Cash Management (Joint WROS)"
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    assert accounts[0]["balance"] == "39,400.59"
    assert accounts[0]["cash_balance"] == "33,400.59"
    assert accounts[0]["account_mask"] == "Z38367298"
    assert accounts[0]["as_of_date"] == "2026-04-08"
    assert accounts[0]["activity_observed_through"] == "2026-04-08"
    assert "cash management account snapshot" in payload["summary"].lower()


def test_baseline_review_detects_frs_investment_plan_statement() -> None:
    payload = _baseline_review(
        filename="Elias_FRS_Account Statement.pdf",
        source_type="other",
        document_type="other",
        extracted_text=(
            "FRS Investment Plan-Your Account\n"
            "Information\n"
            "ELIAS B. LESLIE\n"
            "3636 AVOCADO DR\n"
            "LARGO FL 33770-4553\n"
            "Total Account Balance: $42,404.62\n"
            "Account summary\n"
            "Breakdown of all your account details from 01-01-\n"
            "2026 to 04-10-2026.\n"
            "$42,332.11\n"
            "-$12.00\n"
            "$84.51\n"
            "$42,404.62\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])
    financial_accounts = cast(list[dict[str, Any]], structured_data["financial_accounts"])

    assert payload["document_type"] == "retirement_statement"
    assert payload["source_type"] == "retirement"
    assert structured_data["total_amount"] == "42404.62"
    assert structured_data["statement_period"] == "2026-01-01 to 2026-04-10"
    assert financial_accounts[0]["owner_name"] == "Elias B. Leslie"
    assert financial_accounts[0]["balance"] == "42404.62"
    assert "42404.62" in payload["summary"]


def test_baseline_review_detects_generic_statement_csv_account_snapshot() -> None:
    payload = _baseline_review(
        filename="History_for_Account_Z38367298.csv",
        source_type="other",
        document_type="other",
        extracted_text=(
            "\ufeffRun Date, Action, Symbol, Description, Type, Price ($), Quantity, Commission ($), Fees ($), "
            "Accrued Interest ($), Amount ($), Cash Balance ($), Settlement Date\n"
            "04/08/2026, DIRECT DEBIT DUKEENERGY BILL PAY (Cash), , No Description, Cash, , 0.000, , , , -142.25, 39400.59,\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["document_type"] == "brokerage_statement"
    assert payload["source_type"] == "brokerage"
    assert payload["confidence"] == 0.9
    assert structured_data["account_hint"] == "Account Z38367298"
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    assert accounts[0]["account_mask"] == "Z38367298"
    assert accounts[0]["balance"] == "39400.59"
    assert accounts[0]["as_of_date"] == "2026-04-08"
    assert accounts[0]["activity_observed_through"] == "2026-04-08"


def test_baseline_review_detects_fidelity_positions_csv_and_groups_accounts() -> None:
    payload = _baseline_review(
        filename="Portfolio_Positions_Apr-12-2026 (1).csv",
        source_type="other",
        document_type="other",
        extracted_text=(
            "Account Number,Account Name,Symbol,Description,Quantity,Last Price,Last Price Change,Current Value,Today's Gain/Loss Dollar,Today's Gain/Loss Percent,Total Gain/Loss Dollar,Total Gain/Loss Percent,Percent Of Account,Cost Basis Total,Average Cost Basis,Type\n"
            "245944181,Traditional IRA,SPAXX**,HELD IN MONEY MARKET,,,,$1971.10,,,,,0.57%,,,Cash,\n"
            "245944181,Traditional IRA,VTI,VANGUARD TOTAL STK MKT ETF,994.409,$335.05,-$0.40,$333176.73,-$397.77,-0.12%,+$78794.92,+30.97%,96.00%,$254381.81,$255.81,Cash,\n"
            "250696445,ROTH IRA,SPAXX**,HELD IN MONEY MARKET,,,,$48014.15,,,,,100.00%,,,Cash,\n"
            "Date downloaded Apr-12-2026 6:21 p.m ET\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["source_type"] == "retirement"
    assert payload["document_type"] == "retirement_statement"
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    assert len(accounts) == 2
    assert accounts[0]["account_name"] == "Traditional IRA"
    assert accounts[0]["account_mask"] == "245944181"
    assert accounts[0]["balance"] == "335147.83"
    assert accounts[0]["cash_balance"] == "1971.10"
    assert accounts[0]["holdings_value"] == "333176.73"
    assert accounts[1]["account_name"] == "ROTH IRA"
    assert accounts[1]["account_mask"] == "250696445"
    assert accounts[1]["balance"] == "48014.15"
    assert accounts[1]["cash_balance"] == "48014.15"
    assert accounts[1]["holdings_value"] == "0.00"
    assert structured_data["provider_name"] == "Fidelity"
    assert structured_data["account_hint"] == "Fidelity positions export (2 accounts)"
    assert structured_data["statement_period"] == "2026-04-12"


def test_baseline_review_parses_fidelity_position_quantities_costs_and_pending_cash() -> None:
    payload = _baseline_review(
        filename="Portfolio_Positions_May-02-2026.csv",
        source_type="other",
        document_type="other",
        extracted_text=(
            "Account Number,Account Name,Symbol,Description,Quantity,Last Price,Last Price Change,Current Value,Today's Gain/Loss Dollar,Today's Gain/Loss Percent,Total Gain/Loss Dollar,Total Gain/Loss Percent,Percent Of Account,Cost Basis Total,Average Cost Basis,Type\n"
            "245944181,Traditional IRA,SPAXX**,HELD IN MONEY MARKET,,,,$1976.42,,,,,0.54%,,,Cash,\n"
            "245944181,Traditional IRA,AMZN,AMAZON.COM INC,2,$268.26,+$3.20,$536.52,+$6.40,+1.20%,+$134.18,+33.34%,0.15%,$402.34,$201.17,Cash,\n"
            "245944181,Traditional IRA,VGT,VANGUARD WORLD FD INF TECH ETF,124,$104.85,+$1.67,$13001.40,+$68.20,+0.52%,+$68.20,+0.52%,3.53%,$12933.20,$104.30,Cash,\n"
            "245944181,Traditional IRA,Pending activity,,,,,-$1837.64,,,,,,\n"
            "Date downloaded May-02-2026 4:19 p.m ET\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])
    account = cast(list[dict[str, Any]], structured_data["financial_accounts"])[0]
    holdings = cast(list[dict[str, Any]], account["holdings"])

    assert account["balance"] == "13676.70"
    assert account["cash_balance"] == "138.78"
    assert account["holdings_value"] == "13537.92"
    assert account["position_snapshot"] is True
    assert holdings[1]["symbol"] == "AMZN"
    assert holdings[1]["quantity"] == "2"
    assert holdings[1]["cost_basis_total"] == "402.34"
    assert holdings[1]["average_cost_basis"] == "201.17"
    assert holdings[3]["symbol"] == "Pending activity"
    assert holdings[3]["market_value"] == "-1837.64"
    assert holdings[3]["cash_like"] is True


def test_baseline_review_detects_fidelity_statement_summary_csv_and_groups_accounts() -> None:
    payload = _baseline_review(
        filename="Statement3312026.csv",
        source_type="other",
        document_type="other",
        extracted_text=(
            "Account Type,Account,Beginning mkt Value,Change in Investment,Ending mkt Value,Short Balance,Ending Net Value,Dividends This Period,Dividends Year to Date,Interest This Year,Interest Year to Date,Total This Period,Total Year to Date\n"
            "ROTH IRA,250696445,47622.95,391.20,48014.15,,,,,,,391.20,391.20\n"
            "Individual - TOD,Z35217544,507160.48,-21008.66,486151.82,,,1497.11,1497.11,,,1497.11,1497.11\n"
            "Traditional IRA,245944181,346819.86,-14619.08,332200.78,,,,,,,1011.10,1011.10\n"
            "Symbol/CUSIP,Description,Quantity,Price,Beginning Value,Ending Value,Cost Basis\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["source_type"] == "brokerage"
    assert payload["document_type"] == "brokerage_statement"
    assert payload["confidence"] == 0.92
    assert payload["summary"] == (
        "Fidelity statement summary covering 3 mixed accounts totaling $866,366.75."
    )
    accounts = cast(list[dict[str, Any]], structured_data["financial_accounts"])
    assert len(accounts) == 3
    assert accounts[0]["account_name"] == "ROTH IRA"
    assert accounts[0]["account_mask"] == "250696445"
    assert accounts[0]["source_type"] == "retirement"
    assert accounts[0]["balance"] == "48014.15"
    assert accounts[0]["as_of_date"] == "2026-03-31"
    assert accounts[1]["account_name"] == "Individual - TOD"
    assert accounts[1]["account_mask"] == "Z35217544"
    assert accounts[1]["source_type"] == "brokerage"
    assert accounts[1]["balance"] == "486151.82"
    assert accounts[2]["account_name"] == "Traditional IRA"
    assert accounts[2]["account_mask"] == "245944181"
    assert accounts[2]["source_type"] == "retirement"
    assert accounts[2]["balance"] == "332200.78"
    assert structured_data["provider_name"] == "Fidelity"
    assert structured_data["account_hint"] == "Fidelity statement summary (3 accounts)"
    assert structured_data["statement_period"] == "2026-03-31"


@patch.object(HouseholdDocumentReviewService, "_touch_signature")
@patch.object(HouseholdDocumentReviewService, "_find_signature")
def test_review_uses_baseline_account_identity_for_csv_header_signature(
    find_signature: MagicMock,
    touch_signature: MagicMock,
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "Portfolio_Positions_Apr-12-2026 (1).csv"
    csv_path.write_text(
        (
            "Account Number,Account Name,Symbol,Description,Quantity,Last Price,Last Price Change,Current Value,Today's Gain/Loss Dollar,Today's Gain/Loss Percent,Total Gain/Loss Dollar,Total Gain/Loss Percent,Percent Of Account,Cost Basis Total,Average Cost Basis,Type\n"
            "245944181,Traditional IRA,SPAXX**,HELD IN MONEY MARKET,,,,$1971.10,,,,,0.57%,,,Cash,\n"
            "250696445,ROTH IRA,SPAXX**,HELD IN MONEY MARKET,,,,$48014.15,,,,,100.00%,,,Cash,\n"
            "Date downloaded Apr-12-2026 6:21 p.m ET\n"
        ),
        encoding="utf-8",
    )
    find_signature.return_value = {
        "id": "sig-1",
        "signature_type": "csv_header",
        "source_type": "brokerage",
        "document_type": "brokerage_statement",
        "merchant": None,
        "account_hint": "Z35217544",
        "confidence": 0.99,
    }
    service = HouseholdDocumentReviewService()

    payload = service.review(
        document_id="doc-1",
        filename=csv_path.name,
        stored_path=csv_path,
        content_type="text/csv",
        source_type="other",
        document_type="other",
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])

    assert payload["source_type"] == "retirement"
    assert payload["document_type"] == "retirement_statement"
    assert payload["summary"] == "Fidelity positions export covering 2 retirement accounts totaling $49,985.25."
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    assert accounts[0]["account_mask"] == "245944181"
    assert accounts[1]["account_mask"] == "250696445"
    assert structured_data["account_hint"] == "Fidelity positions export (2 accounts)"
    touch_signature.assert_called_once_with("sig-1")


@patch("app.services.household_document_review.AGENT_HUB_ENABLED", True)
@patch.object(HouseholdDocumentReviewService, "_touch_signature")
@patch.object(HouseholdDocumentReviewService, "_review_with_llm")
@patch.object(HouseholdDocumentReviewService, "_find_signature")
def test_review_does_not_short_circuit_on_weak_money_filename_signature(
    find_signature: MagicMock,
    review_with_llm: MagicMock,
    touch_signature: MagicMock,
    tmp_path: Path,
) -> None:
    statement_path = tmp_path / "20260411-statements-9728-.txt"
    statement_path.write_text(
        (
            "AUTOPAY IS ON\n"
            "www.chase.com/amazon\n"
            "ELIAS B LESLIE\n"
            "Prime Visa ending 5313\n"
            "New Balance: $2,958.17\n"
        ),
        encoding="utf-8",
    )
    find_signature.return_value = {
        "id": "sig-weak",
        "signature_type": "filename_pattern",
        "source_type": "credit_card",
        "document_type": "statement",
        "merchant": "Amazon Prime Visa",
        "account_hint": "Chase Amazon card",
        "confidence": 0.99,
        "structured_data": {
            "account_hint": "Chase Amazon card",
            "total_amount": "2,958.17",
        },
    }
    review_with_llm.return_value = {
        "summary": "Prime Visa statement.",
        "source_type": "credit_card",
        "document_type": "statement",
        "confidence": 0.99,
        "structured_data": {
            "provider_name": "Chase",
            "account_hint": "Chase Prime Visa ending 5313",
            "financial_accounts": [
                {
                    "institution_name": "Chase",
                    "account_name": "Prime Visa",
                    "account_mask": "5313",
                    "asset_group": "credit",
                    "account_type": "credit_card",
                    "balance": "2,958.17",
                    "currency": "USD",
                }
            ],
        },
        "inferred_values": [],
        "questions": [],
    }
    service = HouseholdDocumentReviewService()

    payload = service.review(
        document_id="doc-weak-signature",
        filename=statement_path.name,
        stored_path=statement_path,
        content_type="text/plain",
        source_type="other",
        document_type="other",
    )

    structured_data = cast(dict[str, Any], payload["structured_data"])
    review_with_llm.assert_called_once()
    touch_signature.assert_called_once_with("sig-weak")
    accounts = structured_data["financial_accounts"]
    assert isinstance(accounts, list)
    assert accounts[0]["account_mask"] == "5313"
    assert structured_data["provider_name"] == "Chase"


def test_baseline_review_detects_credit_card_qfx_export() -> None:
    payload = _baseline_review(
        filename="transactions.qfx",
        source_type="other",
        document_type="other",
        extracted_text="<OFX><CREDITCARDMSGSRSV1><CCSTMTTRNRS><BANKTRANLIST><STMTTRN>",
    )

    assert payload["document_type"] == "statement"
    assert payload["source_type"] == "credit_card"
    assert "machine-readable transaction activity" in payload["summary"]


def test_review_promotes_agent_financial_account_classification_and_review_checks(
    tmp_path: Path,
) -> None:
    csv_path = tmp_path / "Chase9728_Activity20260101_20260416_20260416.CSV"
    csv_path.write_text(
        (
            "Transaction Date,Post Date,Description,Category,Type,Amount,Memo\n"
            "04/14/2026,04/15/2026,Amazon.com*B784J4QP1,Shopping,Sale,-28.86,\n"
        ),
        encoding="utf-8",
    )
    service = HouseholdDocumentReviewService(agent_service=MagicMock())

    with (
        patch(f"{_REVIEW_MODULE}.AGENT_HUB_ENABLED", True),
        patch.object(HouseholdDocumentReviewService, "_signature_review", return_value=None),
        patch.object(
            HouseholdDocumentReviewService,
            "_build_household_context",
            return_value={"related_accounts": []},
        ),
        patch.object(
            HouseholdDocumentReviewService,
            "_review_with_llm",
            return_value={
                "summary": "Uploaded other from other.",
                "source_type": "other",
                "document_type": "other",
                "confidence": 0.94,
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
                            "owner_name": "Elias B Leslie",
                        }
                    ],
                },
            },
        ),
    ):
        payload = service.review(
            document_id="doc-chase-activity",
            filename=csv_path.name,
            stored_path=csv_path,
            content_type="text/csv",
            source_type="other",
            document_type="other",
        )

    review_checks = cast(dict[str, Any], payload["review_checks"])
    assert payload["source_type"] == "credit_card"
    assert payload["document_type"] == "statement"
    assert review_checks["expected_account_count"] == 1
    assert review_checks["expects_transaction_activity"] is True
    assert "activity export" in str(payload["summary"]).lower()


def test_build_signature_candidates_includes_filename_pattern() -> None:
    service = HouseholdDocumentReviewService()

    candidates = service.build_signature_candidates(
        filename="022726 WellsFargo.pdf",
        extracted_text="Wells Fargo Everyday Checking\nFebruary 27, 2026 Page 1 of 5",
    )

    signature_keys = {candidate[1] for candidate in candidates}
    assert "filename_pattern::######_wellsfargo" in signature_keys


def test_build_signature_candidates_skips_generic_image_name() -> None:
    service = HouseholdDocumentReviewService()

    candidates = service.build_signature_candidates(
        filename="image.png",
        extracted_text="College Fnd - Nadia\n529 COLL-ME-Edge22Z-87861",
    )

    signature_keys = {candidate[1] for candidate in candidates}
    assert "filename_pattern::image" not in signature_keys


@patch.object(HouseholdDocumentReviewService, "_touch_signature")
@patch.object(HouseholdDocumentReviewService, "_find_signature")
def test_signature_review_enriches_summary_and_amount(
    find_signature: MagicMock,
    touch_signature: MagicMock,
) -> None:
    service = HouseholdDocumentReviewService()
    find_signature.return_value = {
        "id": "sig-1",
        "signature_type": "filename_pattern",
        "source_type": "receipt",
        "document_type": "receipt",
        "merchant": "Walmart (Store #5831, Largo, FL)",
        "account_hint": "Visa Credit ****4635",
        "confidence": 0.95,
    }

    payload = service._signature_review(
        filename="1Order details - Walmart.com.pdf",
        extracted_text="09/03/2026\nTOTAL\n11.40\nVISA\n4635",
    )

    assert payload is not None
    assert payload["structured_data"]["merchant"] == "Walmart (Store #5831, Largo, FL)"
    assert payload["structured_data"]["total_amount"] == "11.40"
    assert "Walmart" in payload["summary"]
    assert "11.40" in payload["summary"]
    touch_signature.assert_called_once_with("sig-1")


@patch.object(HouseholdDocumentReviewService, "_find_signature")
def test_signature_review_skips_generic_image_name(
    find_signature: MagicMock,
) -> None:
    find_signature.return_value = None
    service = HouseholdDocumentReviewService()

    payload = service._signature_review(
        filename="image.png",
        extracted_text="College Fnd - Nadia\n529 COLL-ME-Edge22Z-87861",
    )

    assert payload is None
    find_signature.assert_called_once()


def test_build_messages_uses_single_text_message() -> None:
    messages = _build_messages(
        payload={
            "document_id": "doc-1",
            "filename": "statement.pdf",
            "source_type": "bank",
            "document_type": "statement",
            "content_type": "application/pdf",
        },
        stored_path=Path("/tmp/statement.pdf"),
        content_type="application/pdf",
        extracted_text="Statement text",
        baseline_review={
            "summary": "Statement",
            "document_type": "statement",
            "source_type": "bank",
            "confidence": 0.8,
            "structured_data": {},
            "inferred_values": [],
            "questions": [],
        },
    )

    assert len(messages) == 1
    assert isinstance(messages[0].content, str)
    assert "Document metadata:" in messages[0].content
    assert "Extracted text preview:" in messages[0].content


def test_build_messages_includes_context_and_prior_attempt_when_present() -> None:
    messages = _build_messages(
        payload={"document_id": "doc-2", "filename": "statement.pdf"},
        stored_path=Path("/tmp/statement.pdf"),
        content_type="application/pdf",
        extracted_text="Statement text",
        baseline_review={"summary": "Statement", "structured_data": {}},
        household_context={
            "related_accounts": [
                {"canonical_label": "Amazon Chase (CC)", "identity_examples": ["credit-lineage::chase|amazon"]}
            ]
        },
        prior_review={"summary": "Prior attempt"},
        reconciliation_summary={"issues": [{"code": "missing_accounts"}]},
    )

    assert "Current canonical household context:" in messages[0].content
    assert "Prior review attempt:" in messages[0].content
    assert "Post-apply reconciliation issues from prior attempt:" in messages[0].content


@patch("app.services.household_document_review.AGENT_HUB_ENABLED", True)
@patch("app.services.household_document_review.AgentHubAPIClient")
def test_review_with_llm_uses_dedicated_financial_document_agent(mock_client_class: MagicMock) -> None:
    agent_service = MagicMock()
    service = HouseholdDocumentReviewService(agent_service=agent_service)

    mock_sdk_client = MagicMock()
    mock_sdk_client.complete_messages.return_value.content = (
        '{"summary":"Receipt","document_type":"receipt","source_type":"receipt","confidence":0.9,'
        '"structured_data":{"merchant":"Amazon"},"inferred_values":[],"questions":[]}'
    )
    mock_client_class.return_value = mock_sdk_client

    payload = service._review_with_llm(
        payload={
            "document_id": "doc-1",
            "filename": "Order History.csv",
            "source_type": "receipt",
            "document_type": "receipt",
            "content_type": "text/csv",
        },
        stored_path=Path("/tmp/order-history.csv"),
        content_type="text/csv",
        extracted_text="Order Date,Order ID,Title",
        baseline_review={
            "summary": "Amazon order history export.",
            "document_type": "receipt",
            "source_type": "receipt",
            "confidence": 0.8,
            "structured_data": {},
            "inferred_values": [],
            "questions": [],
        },
    )

    assert payload is not None
    agent_service.ensure_agent.assert_called_once()
    mock_sdk_client.complete_messages.assert_called_once()
    kwargs = mock_sdk_client.complete_messages.call_args.kwargs
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["use_memory"] is True


def test_baseline_review_detects_defined_contribution_retirement_plan_from_raw_text() -> None:
    payload = _baseline_review(
        filename="add-anything.txt",
        source_type="other",
        document_type="other",
        extracted_text=(
            "Pinellas County Schools 457(b) Deferred Compensation Plan\n"
            "Pinellas County Schools\n"
            "Fixed Funds, as of 04/10/2026\n"
            "Variable/Mutual Funds, as of 04/10/2026\n"
            "Total: $95,961.72\n"
        ),
    )
    structured_data = cast(dict[str, Any], payload["structured_data"])
    financial_accounts = cast(list[dict[str, Any]], structured_data["financial_accounts"])

    assert payload["document_type"] == "retirement_statement"
    assert payload["source_type"] == "retirement"
    assert payload["confidence"] >= 0.9
    assert structured_data["provider_name"] == "Pinellas County Schools"
    assert financial_accounts[0]["account_name"] == "Pinellas County Schools 457(b) Deferred Compensation Plan"
    assert financial_accounts[0]["balance"] == "95961.72"
