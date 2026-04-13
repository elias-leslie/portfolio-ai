"""Unit tests for the household review agent integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.household_review_agent_service import (
    HOUSEHOLD_REVIEW_AGENT_SLUG,
    HouseholdReviewAgentService,
)


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_ensure_agent_checks_financial_document_reviewer_by_slug(
    mock_sdk_class: MagicMock,
) -> None:
    mock_sdk = MagicMock()
    mock_http = MagicMock()
    mock_sdk._get_client.return_value = mock_http
    mock_sdk._inject_tracking_headers.return_value = {"X-Tool-Name": "test"}
    mock_http.get.return_value.status_code = 200
    mock_http.get.return_value.json.return_value = {"slug": HOUSEHOLD_REVIEW_AGENT_SLUG, "is_active": True}
    mock_sdk_class.return_value = mock_sdk

    service = HouseholdReviewAgentService()
    service.ensure_agent()

    mock_http.get.assert_called_once()
    mock_http.post.assert_not_called()
    mock_http.put.assert_not_called()
