"""Unit tests for household document review parsing."""

from __future__ import annotations

from pathlib import Path
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

    assert payload["document_type"] == "receipt"
    assert payload["source_type"] == "receipt"
    assert payload["structured_data"]["merchant"] == "Walmart"


def test_baseline_review_detects_amazon_order_history_csv() -> None:
    payload = _baseline_review(
        filename="Order History.csv",
        source_type="other",
        document_type="other",
        extracted_text="Order Date,Order ID,Payment Instrument Type,Website\n2026-03-01,123-1234567-1234567,VISA,Amazon.com",
    )

    assert payload["document_type"] == "receipt"
    assert payload["source_type"] == "receipt"
    assert payload["structured_data"]["merchant"] == "Amazon"


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

    assert payload["document_type"] == "statement"
    assert payload["source_type"] == "bank"
    assert payload["structured_data"]["account_hint"] == "Wells Fargo Everyday Checking"


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

    assert payload["document_type"] == "brokerage_statement"
    assert payload["source_type"] == "brokerage"
    assert payload["structured_data"]["account_hint"] == "529 college savings account"
    assert "529" in payload["summary"]


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
