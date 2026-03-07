"""Unit tests for DualProviderClient (Agent Hub wrapper).

Tests the simplified DualProviderClient that uses Agent Hub API exclusively.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agents.llm_client import DualProviderClient, LLMResponse
from app.constants import CLAUDE_OPUS, CLAUDE_SONNET


class TestDualProviderClient:
    """Tests for DualProviderClient using Agent Hub."""

    @pytest.fixture
    def mock_response(self) -> LLMResponse:
        """Create a mock LLM response."""
        return LLMResponse(
            content="Test analysis result",
            provider="claude",
            model=CLAUDE_SONNET,
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    def test_initialization_default(self) -> None:
        """Test default initialization uses Agent Hub."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            client = DualProviderClient()
            mock_client.assert_called_once()
            assert client.primary == "agent_hub"

    def test_initialization_claude_primary(self) -> None:
        """Test initialization with Claude as primary."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            client = DualProviderClient(primary="claude")
            assert client.primary == "claude"
            # Should use Claude model
            call_kwargs = mock_client.call_args.kwargs
            assert "claude" in call_kwargs.get("model", "")

    def test_initialization_gemini_primary(self) -> None:
        """Test initialization with Gemini as primary."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            client = DualProviderClient(primary="gemini")
            assert client.primary == "gemini"
            # Should use Gemini model
            call_kwargs = mock_client.call_args.kwargs
            assert "gemini" in call_kwargs.get("model", "")

    def test_initialization_passes_agent_slug(self) -> None:
        """Specialist workflows should be able to choose a routed Agent Hub agent."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            DualProviderClient(primary="gemini", agent_slug="equity-analyst")
            call_kwargs = mock_client.call_args.kwargs
            assert call_kwargs["agent_slug"] == "equity-analyst"

    def test_is_available_delegates_to_client(self) -> None:
        """Test that is_available delegates to Agent Hub client."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            mock_client.return_value.is_available.return_value = True
            client = DualProviderClient()
            assert client.is_available() is True
            mock_client.return_value.is_available.assert_called_once()

    def test_get_model_name_delegates_to_client(self) -> None:
        """Test that get_model_name delegates to Agent Hub client."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            mock_client.return_value.get_model_name.return_value = "claude-sonnet-4-5"
            client = DualProviderClient()
            assert client.get_model_name() == "claude-sonnet-4-5"

    def test_generate_delegates_to_client(self, mock_response: LLMResponse) -> None:
        """Test that generate delegates to Agent Hub client."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            mock_client.return_value.generate.return_value = mock_response
            client = DualProviderClient()
            response = client.generate(prompt="Test prompt")
            assert response.content == "Test analysis result"
            mock_client.return_value.generate.assert_called_once()

    def test_generate_passes_all_parameters(self, mock_response: LLMResponse) -> None:
        """Test that generate passes all parameters to client."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            mock_client.return_value.generate.return_value = mock_response
            client = DualProviderClient()
            client.generate(
                prompt="Test prompt",
                system="System prompt",
                tools=[{"name": "test_tool"}],
                max_tokens=2048,
                temperature=0.7,
            )

            call_kwargs = mock_client.return_value.generate.call_args.kwargs
            assert call_kwargs["prompt"] == "Test prompt"
            assert call_kwargs["system"] == "System prompt"
            assert call_kwargs["tools"] == [{"name": "test_tool"}]
            assert call_kwargs["max_tokens"] == 2048
            assert call_kwargs["temperature"] == 0.7

    def test_custom_models_passed_to_client(self) -> None:
        """Test that custom model names are used correctly."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            DualProviderClient(
                primary="claude",
                claude_model=CLAUDE_OPUS,
            )
            call_kwargs = mock_client.call_args.kwargs
            assert call_kwargs["model"] == "claude-opus-4-5"

    def test_close_delegates_to_client(self) -> None:
        """Test that close delegates to Agent Hub client."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            client = DualProviderClient()
            client.close()
            mock_client.return_value.close.assert_called_once()

    def test_use_agent_hub_parameter_ignored(self) -> None:
        """Test that use_agent_hub parameter is ignored (always True)."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            # Even with use_agent_hub=False, should still use Agent Hub
            client = DualProviderClient(use_agent_hub=False)
            mock_client.assert_called_once()

    def test_usage_tracking_from_response(self, mock_response: LLMResponse) -> None:
        """Test that usage data is correctly passed through from response."""
        with patch("app.agents.llm_client.AgentHubAPIClient") as mock_client:
            mock_client.return_value.generate.return_value = mock_response
            client = DualProviderClient()
            response = client.generate(prompt="Test prompt")

            assert response.usage["prompt_tokens"] == 100
            assert response.usage["completion_tokens"] == 50
            assert response.usage["total_tokens"] == 150
