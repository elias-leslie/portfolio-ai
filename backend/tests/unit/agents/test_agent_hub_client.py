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
        client = AgentHubAPIClient(agent_slug="persona")
        response = client.generate(prompt="Review AAPL")

    init_kwargs = mock_sdk.call_args.kwargs
    call_kwargs = mock_sdk.return_value.complete.call_args.kwargs
    assert "client_secret" not in init_kwargs
    assert init_kwargs["client_name"] == "portfolio-ai"
    assert call_kwargs["agent_slug"] == "persona"
    assert "model" not in call_kwargs
    assert response.raw_response["session_id"] == "session-123"
    assert client.get_model_name() == "persona"


@patch("app.agents.clients.agent_hub_client.SDKClient")
def test_agent_hub_client_defaults_to_chat_agent_for_generic_calls(mock_sdk: Mock) -> None:
    """Model-only callers should still route through a valid Agent Hub agent."""
    mock_sdk.return_value.complete.return_value = _mock_response()

    with patch("app.agents.clients.agent_hub_client.AGENT_HUB_ENABLED", True):
        client = AgentHubAPIClient(model="gemini-3-flash-preview")
        response = client.generate(prompt="Review NVDA")

    call_kwargs = mock_sdk.return_value.complete.call_args.kwargs
    assert call_kwargs["agent_slug"] == "chat"
    assert call_kwargs["model"] == "gemini-3-flash-preview"
    assert response.raw_response["session_id"] == "session-123"
    assert client.get_model_name() == "gemini-3-flash-preview"
