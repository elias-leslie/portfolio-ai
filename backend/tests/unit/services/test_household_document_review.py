"""Unit tests for household document review parsing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from agent_hub.models.content import ImageContent

from app.services.household_document_review import HouseholdDocumentReviewService
from app.services.household_review_agent_service import HOUSEHOLD_REVIEW_AGENT_SLUG


def test_parse_review_payload_handles_fenced_json() -> None:
    service = HouseholdDocumentReviewService()

    payload = service._parse_review_payload(
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
    service = HouseholdDocumentReviewService()

    payload = service._parse_review_payload(
        'Review result: {"summary":"Receipt","document_type":"receipt","source_type":"receipt","confidence":0.8,"structured_data":{},"inferred_values":[],"questions":[]}'
    )

    assert payload["document_type"] == "receipt"
    assert payload["source_type"] == "receipt"


def test_baseline_review_detects_walmart_order_details() -> None:
    service = HouseholdDocumentReviewService()

    payload = service._baseline_review(
        filename="Order details - Walmart.com.pdf",
        source_type="other",
        document_type="other",
        extracted_text="Order details - Walmart.com\nFresh Whole Brussels Sprouts\nOrder total $83.21",
    )

    assert payload["document_type"] == "receipt"
    assert payload["source_type"] == "receipt"
    assert payload["structured_data"]["merchant"] == "Walmart"


def test_baseline_review_detects_amazon_order_history_csv() -> None:
    service = HouseholdDocumentReviewService()

    payload = service._baseline_review(
        filename="Order History.csv",
        source_type="other",
        document_type="other",
        extracted_text="Order Date,Order ID,Payment Instrument Type,Website\n2026-03-01,123-1234567-1234567,VISA,Amazon.com",
    )

    assert payload["document_type"] == "receipt"
    assert payload["source_type"] == "receipt"
    assert payload["structured_data"]["merchant"] == "Amazon"


def test_baseline_review_detects_wells_fargo_checking_statement() -> None:
    service = HouseholdDocumentReviewService()

    payload = service._baseline_review(
        filename="022726 WellsFargo.pdf",
        source_type="other",
        document_type="other",
        extracted_text="Wells Fargo Everyday Checking\nFebruary 27, 2026 Page 1 of 5",
    )

    assert payload["document_type"] == "statement"
    assert payload["source_type"] == "bank"
    assert payload["structured_data"]["account_hint"] == "Wells Fargo Everyday Checking"


def test_build_signature_candidates_includes_filename_pattern() -> None:
    service = HouseholdDocumentReviewService()

    candidates = service.build_signature_candidates(
        filename="022726 WellsFargo.pdf",
        extracted_text="Wells Fargo Everyday Checking\nFebruary 27, 2026 Page 1 of 5",
    )

    signature_keys = {candidate[1] for candidate in candidates}
    assert "filename_pattern::######_wellsfargo" in signature_keys


@patch.object(HouseholdDocumentReviewService, "_pdf_image_blocks")
def test_build_messages_includes_pdf_preview_images(pdf_image_blocks: MagicMock) -> None:
    service = HouseholdDocumentReviewService()
    pdf_image_blocks.return_value = [ImageContent.from_base64("ZmFrZQ==", media_type="image/png")]

    messages = service._build_messages(
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
