"""Unit tests for the household review agent integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

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


def _sdk_with_agents(mock_sdk_class: MagicMock, *, missing: set[str] | None = None) -> MagicMock:
    """Agent Hub stub that 404s the slugs named in ``missing``."""
    missing = missing or set()
    mock_sdk = MagicMock()
    mock_http = MagicMock()
    mock_sdk._get_client.return_value = mock_http
    mock_sdk._inject_tracking_headers.return_value = {"X-Tool-Name": "test"}

    def _get(path: str, headers: dict[str, str] | None = None) -> MagicMock:
        slug = path.rsplit("/", 1)[-1]
        response = MagicMock()
        response.status_code = 404 if slug in missing else 200
        response.json.return_value = {"slug": slug, "is_active": True}
        return response

    mock_http.get.side_effect = _get
    mock_sdk_class.return_value = mock_sdk
    return mock_http


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
    mock_http = _sdk_with_agents(mock_sdk_class)
    service = HouseholdReviewAgentService()

    service.resolve_review_agent_slug(include_image=True)
    service.resolve_review_agent_slug(include_image=True)

    checked = [call.args[0].rsplit("/", 1)[-1] for call in mock_http.get.call_args_list]
    assert sorted(checked) == sorted(
        [HOUSEHOLD_REVIEW_AGENT_SLUG, HOUSEHOLD_RECEIPT_VISION_AGENT_SLUG]
    )
