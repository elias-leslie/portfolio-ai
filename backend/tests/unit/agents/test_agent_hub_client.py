"""Unit tests for AgentHubAPIClient routing behavior."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from app.agents.clients.agent_hub_client import AgentHubAPIClient


def _mock_response(content: str = '{"verdict":"buy"}') -> SimpleNamespace:
    usage = SimpleNamespace(
        input_tokens=120,
        output_tokens=40,
        total_tokens=160,
        cache=None,
    )
    return SimpleNamespace(
        content=content,
        provider="served-provider",
        model="served-model",
        usage=usage,
        finish_reason="end_turn",
        tool_calls=None,
        session_id="session-123",
        from_cache=False,
    )


@patch("app.agents.clients.agent_hub_client.SDKClient")
def test_agent_hub_client_uses_agent_slug_when_present(mock_sdk: Mock) -> None:
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
    assert "use_memory" not in call_kwargs
    assert "execute_tools" not in call_kwargs
    assert response.raw_response["session_id"] == "session-123"
    assert client.get_model_name() == "persona"


@patch("app.agents.clients.agent_hub_client.SDKClient")
def test_agent_hub_client_rejects_direct_model_override(mock_sdk: Mock) -> None:
    with (
        patch("app.agents.clients.agent_hub_client.AGENT_HUB_ENABLED", True),
        pytest.raises(ValueError, match="agent_slug"),
    ):
        AgentHubAPIClient(model="legacy-direct-model")

    mock_sdk.assert_not_called()


@patch("app.agents.clients.agent_hub_client.SDKClient")
def test_agent_hub_client_keeps_timeouts_out_of_completion_payload(mock_sdk: Mock) -> None:
    mock_sdk.return_value.complete.return_value = _mock_response()

    with patch("app.agents.clients.agent_hub_client.AGENT_HUB_ENABLED", True):
        client = AgentHubAPIClient(agent_slug="equity-analyst", timeout=45.0)
        client.generate(prompt="Review AMZN")

    init_kwargs = mock_sdk.call_args.kwargs
    call_kwargs = mock_sdk.return_value.complete.call_args.kwargs
    assert init_kwargs["timeout"] == 45.0
    assert "timeout_seconds" not in call_kwargs


