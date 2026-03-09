"""Unit tests for the household review agent integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.household_review_agent_service import (
    HOUSEHOLD_REVIEW_AGENT_SLUG,
    HouseholdReviewAgentService,
)


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_ensure_agent_creates_financial_document_reviewer_when_missing(
    mock_sdk_class: MagicMock,
) -> None:
    mock_sdk = MagicMock()
    mock_http = MagicMock()
    mock_sdk._get_client.return_value = mock_http
    mock_sdk._inject_tracking_headers.return_value = {"X-Tool-Name": "test"}
    mock_http.get.return_value.status_code = 404
    mock_http.post.return_value.raise_for_status.return_value = None
    mock_sdk_class.return_value = mock_sdk

    service = HouseholdReviewAgentService()
    service.ensure_agent()

    mock_http.get.assert_called_once()
    mock_http.post.assert_called_once()
    assert mock_http.post.call_args.kwargs["json"]["slug"] == HOUSEHOLD_REVIEW_AGENT_SLUG


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_save_learning_tags_project_scoped_household_memory(
    mock_sdk_class: MagicMock,
) -> None:
    mock_sdk = MagicMock()
    mock_http = MagicMock()
    mock_sdk._get_client.return_value = mock_http
    mock_sdk._inject_tracking_headers.return_value = {"X-Tool-Name": "test"}
    mock_sdk._build_memory_headers.side_effect = lambda headers, **_: headers
    mock_sdk.save_learning.return_value = {"uuid": "memory-1"}
    mock_http.put.return_value.raise_for_status.return_value = None
    mock_sdk_class.return_value = mock_sdk

    service = HouseholdReviewAgentService()
    memory_id = service.save_learning(
        content="Confirmed this is the primary checking account.",
        summary="Confirmed checking",
        confidence=95,
        tags=["household-finance", "financial-doc-review"],
        context="household_question_confirmation",
    )

    assert memory_id == "memory-1"
    mock_sdk.save_learning.assert_called_once_with(
        "**Confirmed checking**: Confirmed this is the primary checking account.",
        injection_tier="reference",
        confidence=95,
        context="household_question_confirmation",
        scope="project",
        scope_id="portfolio-ai",
        summary="Confirmed checking",
    )
    mock_http.put.assert_called_once_with(
        "/api/memory/episodes/memory-1/tags",
        json={"tags": ["financial-doc-review", "household-finance"]},
        headers={"X-Tool-Name": "test"},
    )


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_save_learning_truncates_summary_for_agent_hub(
    mock_sdk_class: MagicMock,
) -> None:
    mock_sdk = MagicMock()
    mock_sdk.save_learning.return_value = {"uuid": "memory-1"}
    mock_sdk_class.return_value = mock_sdk

    service = HouseholdReviewAgentService()
    service._set_memory_tags = MagicMock()  # type: ignore[method-assign]
    service.save_learning(
        content="Detailed learning body.",
        summary="Pattern Rollover IRA #267328698 100 percent cash held in money market",
        confidence=95,
        tags=["finance-relevant"],
        context="household_document_review",
    )

    assert mock_sdk.save_learning.call_args.kwargs["summary"] == (
        "Pattern Rollover IRA #267328698 100 percent cash h"
    )
