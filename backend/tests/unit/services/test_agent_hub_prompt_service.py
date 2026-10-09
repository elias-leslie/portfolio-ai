"""Prompt lookup goes through the public Agent Hub SDK."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import pytest
from agent_hub.exceptions import AgentHubError

from app.services import agent_hub_prompt_service as prompts


@pytest.fixture
def sdk() -> Iterator[MagicMock]:
    prompts.require_agent_hub_prompt.cache_clear()
    with (
        patch.object(prompts, "AGENT_HUB_ENABLED", True),
        patch.object(prompts, "_sdk") as mock_sdk,
    ):
        yield mock_sdk
    prompts.require_agent_hub_prompt.cache_clear()


def test_prompt_is_fetched_by_slug(sdk: MagicMock) -> None:
    sdk.get_prompt.return_value = {"slug": "p", "content": "Hello {name}"}

    assert prompts.render_agent_hub_prompt("p", name="Jenny") == "Hello Jenny"
    sdk.get_prompt.assert_called_once_with("p")


def test_missing_prompt_names_the_slug(sdk: MagicMock) -> None:
    sdk.get_prompt.side_effect = AgentHubError("Request failed: not found", status_code=404)

    with pytest.raises(RuntimeError, match="'p' is missing"):
        prompts.require_agent_hub_prompt("p")


def test_server_errors_are_not_reported_as_missing(sdk: MagicMock) -> None:
    sdk.get_prompt.side_effect = AgentHubError("Server error", status_code=500)

    with pytest.raises(AgentHubError):
        prompts.require_agent_hub_prompt("p")
