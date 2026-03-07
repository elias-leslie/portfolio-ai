"""Unit tests for AgentHubAPIClient routing behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.agents.clients.agent_hub_client import AgentHubAPIClient


def _mock_response() -> SimpleNamespace:
    usage = SimpleNamespace(
        input_tokens=120,
        output_tokens=40,
        total_tokens=160,
        cache=None,
    )
    return SimpleNamespace(
        content='{"verdict":"buy"}',
        provider="anthropic",
        model="claude-sonnet-4-5",
        usage=usage,
        finish_reason="end_turn",
        tool_calls=None,
        session_id="session-123",
        from_cache=False,
    )


@patch("app.agents.clients.agent_hub_client.SDKClient")
def test_agent_hub_client_uses_agent_slug_when_present(mock_sdk: Mock) -> None:
    """Jenny should be able to route through real Agent Hub agents."""
    mock_sdk.return_value.complete.return_value = _mock_response()

    with patch("app.agents.clients.agent_hub_client.AGENT_HUB_ENABLED", True):
        client = AgentHubAPIClient(agent_slug="persona", model="claude-sonnet-4-5")
        response = client.generate(prompt="Review AAPL")

    call_kwargs = mock_sdk.return_value.complete.call_args.kwargs
    assert call_kwargs["agent_slug"] == "persona"
    assert call_kwargs["model"] == "claude-sonnet-4-5"
    assert response.raw_response["session_id"] == "session-123"
    assert client.get_model_name() == "persona"
