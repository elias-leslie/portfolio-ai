"""Unit tests for the household review agent integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from agent_hub.exceptions import AgentHubError

from app.services.household_review_agent_service import (
    HOUSEHOLD_RECEIPT_VISION_AGENT_SLUG,
    HOUSEHOLD_REVIEW_AGENT_SLUG,
    HouseholdReviewAgentService,
)


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_ensure_agent_checks_financial_document_reviewer_by_slug(
    mock_sdk_class: MagicMock,
) -> None:
    mock_sdk = MagicMock()
    mock_sdk.get_agent.return_value = {"slug": HOUSEHOLD_REVIEW_AGENT_SLUG, "is_active": True}
    mock_sdk_class.return_value = mock_sdk

    service = HouseholdReviewAgentService()
    service.ensure_agent()

    mock_sdk.get_agent.assert_called_once_with(HOUSEHOLD_REVIEW_AGENT_SLUG)


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_inactive_reviewer_raises(mock_sdk_class: MagicMock) -> None:
    mock_sdk_class.return_value.get_agent.return_value = {"is_active": False}

    with pytest.raises(RuntimeError, match="inactive"):
        HouseholdReviewAgentService().ensure_agent()


def _sdk_with_agents(mock_sdk_class: MagicMock, *, missing: set[str] | None = None) -> MagicMock:
    """Agent Hub stub that 404s the slugs named in ``missing``."""
    missing = missing or set()
    mock_sdk = MagicMock()

    def _get_agent(slug: str) -> dict[str, object]:
        if slug in missing:
            raise AgentHubError("Request failed: Agent not found", status_code=404)
        return {"slug": slug, "is_active": True}

    mock_sdk.get_agent.side_effect = _get_agent
    mock_sdk_class.return_value = mock_sdk
    return mock_sdk


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_receipt_images_route_to_the_local_vision_agent(mock_sdk_class: MagicMock) -> None:
    """Receipt photos go to the local-first agent; other documents do not."""
    _sdk_with_agents(mock_sdk_class)
    service = HouseholdReviewAgentService()

    assert (
        service.resolve_review_agent_slug(include_image=True)
        == HOUSEHOLD_RECEIPT_VISION_AGENT_SLUG
    )
    assert (
        service.resolve_review_agent_slug(include_image=False) == HOUSEHOLD_REVIEW_AGENT_SLUG
    )


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_missing_receipt_agent_falls_back_instead_of_failing_review(
    mock_sdk_class: MagicMock,
) -> None:
    """A missing receipt agent must not take the receipt path down with it."""
    _sdk_with_agents(mock_sdk_class, missing={HOUSEHOLD_RECEIPT_VISION_AGENT_SLUG})
    service = HouseholdReviewAgentService()

    assert (
        service.resolve_review_agent_slug(include_image=True) == HOUSEHOLD_REVIEW_AGENT_SLUG
    )


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_missing_general_reviewer_still_raises(mock_sdk_class: MagicMock) -> None:
    """The general reviewer is required; only the receipt agent is optional."""
    _sdk_with_agents(mock_sdk_class, missing={HOUSEHOLD_REVIEW_AGENT_SLUG})
    service = HouseholdReviewAgentService()

    with pytest.raises(RuntimeError, match=HOUSEHOLD_REVIEW_AGENT_SLUG):
        service.resolve_review_agent_slug(include_image=True)


@patch("app.services.household_review_agent_service.AGENT_HUB_ENABLED", True)
@patch("app.services.household_review_agent_service.SDKClient")
def test_agent_verification_is_cached_per_slug(mock_sdk_class: MagicMock) -> None:
    """Each slug is verified once, and verifying one must not mark the other ready."""
    mock_sdk = _sdk_with_agents(mock_sdk_class)
    service = HouseholdReviewAgentService()

    service.resolve_review_agent_slug(include_image=True)
    service.resolve_review_agent_slug(include_image=True)

    checked = [call.args[0] for call in mock_sdk.get_agent.call_args_list]
    assert sorted(checked) == sorted(
        [HOUSEHOLD_REVIEW_AGENT_SLUG, HOUSEHOLD_RECEIPT_VISION_AGENT_SLUG]
    )
