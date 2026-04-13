"""Unit tests for household document review parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

from agent_hub.models.content import ImageContent

from app.services.household_document_review import (
    HouseholdDocumentReviewService,
    _baseline_review,
    _build_messages,
    _extract_csv_text,
    _extract_text,
    _parse_review_payload,
)
from app.services.household_review_agent_service import HOUSEHOLD_REVIEW_AGENT_SLUG

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
    assert structured_data["account_hint"] == "529 college savings account"
    assert "529" in payload["summary"]


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
    service = HouseholdDocumentReviewService()

    payload = service._signature_review(
        filename="image.png",
        extracted_text="College Fnd - Nadia\n529 COLL-ME-Edge22Z-87861",
    )

    assert payload is None
    find_signature.assert_not_called()


@patch(f"{_LLM_MODULE}._pdf_image_blocks")
def test_build_messages_includes_pdf_preview_images(pdf_image_blocks: MagicMock) -> None:
    pdf_image_blocks.return_value = [ImageContent.from_base64("ZmFrZQ==", media_type="image/png")]

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

    pdf_image_blocks.assert_called_once_with(Path("/tmp/statement.pdf"))
    assert len(messages) == 1
    assert len(messages[0].content) == 3


@patch("app.services.household_document_review.AGENT_HUB_ENABLED", True)
@patch("app.services.household_document_review.AgentHubAPIClient")
def test_review_with_llm_uses_dedicated_financial_document_agent(mock_client_class: MagicMock) -> None:
    agent_service = MagicMock()
    service = HouseholdDocumentReviewService(agent_service=agent_service)

    mock_sdk_client = MagicMock()
    mock_sdk_client._client.complete.return_value.content = (
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
    mock_sdk_client._client.complete.assert_called_once()
    kwargs = mock_sdk_client._client.complete.call_args.kwargs
    assert kwargs["agent_slug"] == HOUSEHOLD_REVIEW_AGENT_SLUG
    assert kwargs["use_memory"] is True
