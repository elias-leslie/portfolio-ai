"""Unit tests for DualProviderClient (FEAT-127 LLM Dual-Provider)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agents.llm_client import DualProviderClient, LLMResponse


class TestDualProviderClient:
    """Tests for DualProviderClient with automatic failover."""

    @pytest.fixture
    def mock_gemini_response(self) -> LLMResponse:
        """Create a mock Gemini response."""
        return LLMResponse(
            content="Gemini analysis result",
            provider="gemini",
            model="gemini-2.5-pro",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    @pytest.fixture
    def mock_claude_response(self) -> LLMResponse:
        """Create a mock Claude response."""
        return LLMResponse(
            content="Claude analysis result",
            provider="claude",
            model="claude-sonnet-4.5",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        )

    def test_initialization_with_both_providers(self) -> None:
        """Test that DualProviderClient initializes with both providers."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ) as mock_claude:
            client = DualProviderClient(primary="gemini")

            assert "gemini" in client.providers
            assert "claude" in client.providers
            assert client.primary == "gemini"

    def test_initialization_primary_claude(self) -> None:
        """Test initialization with Claude as primary."""
        with patch("app.agents.llm_client.GeminiCLIClient"), patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ):
            client = DualProviderClient(primary="claude")
            assert client.primary == "claude"

    def test_initialization_fails_when_no_providers_available(self) -> None:
        """Test that initialization raises error when no providers are available."""
        with patch(
            "app.agents.llm_client.GeminiCLIClient", side_effect=RuntimeError("Gemini unavailable")
        ), patch("app.agents.llm_client.ClaudeCLIClient", side_effect=RuntimeError("Claude unavailable")):
            with pytest.raises(RuntimeError, match="No LLM providers available"):
                DualProviderClient()

    def test_is_available_returns_true_when_providers_exist(self) -> None:
        """Test that is_available returns True when at least one provider is available."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ) as mock_claude:
            mock_gemini.return_value.is_available.return_value = True
            mock_claude.return_value.is_available.return_value = True

            client = DualProviderClient()
            assert client.is_available() is True

    def test_is_available_returns_true_with_one_provider(self) -> None:
        """Test that is_available returns True with only one provider operational."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient", side_effect=RuntimeError("Claude unavailable")
        ):
            mock_gemini.return_value.is_available.return_value = True

            client = DualProviderClient()
            assert client.is_available() is True

    def test_get_model_name_returns_primary_model(self) -> None:
        """Test that get_model_name returns primary provider's model."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ) as mock_claude:
            mock_gemini.return_value.get_model_name.return_value = "gemini-2.5-pro"
            mock_claude.return_value.get_model_name.return_value = "claude-sonnet-4.5"

            client = DualProviderClient(primary="gemini")
            assert client.get_model_name() == "gemini-2.5-pro"

    def test_generate_uses_primary_provider_first(
        self, mock_gemini_response: LLMResponse
    ) -> None:
        """Test that generate uses primary provider first."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ):
            mock_gemini.return_value.generate.return_value = mock_gemini_response

            client = DualProviderClient(primary="gemini")
            response = client.generate(prompt="Test prompt")

            assert response.content == "Gemini analysis result"
            assert response.model == "gemini-2.5-pro"
            mock_gemini.return_value.generate.assert_called_once()

    def test_generate_failover_to_secondary_on_error(
        self, mock_claude_response: LLMResponse
    ) -> None:
        """Test that generate fails over to secondary provider on primary error."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ) as mock_claude:
            # Gemini fails, Claude succeeds
            mock_gemini.return_value.generate.side_effect = RuntimeError("Gemini API error")
            mock_claude.return_value.generate.return_value = mock_claude_response

            client = DualProviderClient(primary="gemini")
            response = client.generate(prompt="Test prompt")

            # Should get Claude's response
            assert response.content == "Claude analysis result"
            assert response.model == "claude-sonnet-4.5"

            # Both providers should have been attempted
            mock_gemini.return_value.generate.assert_called_once()
            mock_claude.return_value.generate.assert_called_once()

    def test_generate_raises_when_all_providers_fail(self) -> None:
        """Test that generate raises error when all providers fail."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ) as mock_claude:
            mock_gemini.return_value.generate.side_effect = RuntimeError("Gemini failed")
            mock_claude.return_value.generate.side_effect = RuntimeError("Claude failed")

            client = DualProviderClient(primary="gemini")

            with pytest.raises(RuntimeError, match="All providers failed"):
                client.generate(prompt="Test prompt")

    def test_generate_passes_all_parameters(self, mock_gemini_response: LLMResponse) -> None:
        """Test that generate passes all parameters to provider."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ):
            mock_gemini.return_value.generate.return_value = mock_gemini_response

            client = DualProviderClient(primary="gemini")
            client.generate(
                prompt="Test prompt",
                system="System prompt",
                tools=[{"name": "test_tool"}],
                max_tokens=2048,
                temperature=0.7,
            )

            call_args = mock_gemini.return_value.generate.call_args
            assert call_args.kwargs["prompt"] == "Test prompt"
            assert call_args.kwargs["system"] == "System prompt"
            assert call_args.kwargs["tools"] == [{"name": "test_tool"}]
            assert call_args.kwargs["max_tokens"] == 2048
            assert call_args.kwargs["temperature"] == 0.7

    def test_generate_respects_provider_order_claude_primary(
        self, mock_claude_response: LLMResponse
    ) -> None:
        """Test that generate respects provider order when Claude is primary."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ) as mock_claude:
            mock_claude.return_value.generate.return_value = mock_claude_response

            client = DualProviderClient(primary="claude")
            response = client.generate(prompt="Test prompt")

            # Should use Claude first
            assert response.model == "claude-sonnet-4.5"
            mock_claude.return_value.generate.assert_called_once()
            mock_gemini.return_value.generate.assert_not_called()

    def test_generate_failover_order_claude_to_gemini(
        self, mock_gemini_response: LLMResponse
    ) -> None:
        """Test failover order from Claude to Gemini."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ) as mock_claude:
            mock_claude.return_value.generate.side_effect = RuntimeError("Claude failed")
            mock_gemini.return_value.generate.return_value = mock_gemini_response

            client = DualProviderClient(primary="claude")
            response = client.generate(prompt="Test prompt")

            assert response.model == "gemini-2.5-pro"
            mock_claude.return_value.generate.assert_called_once()
            mock_gemini.return_value.generate.assert_called_once()

    def test_partial_initialization_gemini_only(
        self, mock_gemini_response: LLMResponse
    ) -> None:
        """Test that client works with only Gemini available."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient", side_effect=RuntimeError("Claude unavailable")
        ):
            mock_gemini.return_value.generate.return_value = mock_gemini_response

            client = DualProviderClient(primary="gemini")
            assert "gemini" in client.providers
            assert "claude" not in client.providers

            # Should still work with just Gemini
            response = client.generate(prompt="Test prompt")
            assert response.model == "gemini-2.5-pro"

    def test_partial_initialization_claude_only(
        self, mock_claude_response: LLMResponse
    ) -> None:
        """Test that client works with only Claude available."""
        with patch(
            "app.agents.llm_client.GeminiCLIClient", side_effect=RuntimeError("Gemini unavailable")
        ), patch("app.agents.llm_client.ClaudeCLIClient") as mock_claude:
            mock_claude.return_value.generate.return_value = mock_claude_response

            client = DualProviderClient(primary="claude")
            assert "claude" in client.providers
            assert "gemini" not in client.providers

            # Should still work with just Claude
            response = client.generate(prompt="Test prompt")
            assert response.model == "claude-sonnet-4.5"

    def test_custom_model_names(self) -> None:
        """Test that custom model names are passed to providers."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ) as mock_claude:
            client = DualProviderClient(
                primary="gemini",
                claude_model="opus",
                gemini_model="gemini-2.0-flash",
            )

            # Verify model names were passed to constructors
            mock_gemini.assert_called_once_with(model="gemini-2.0-flash")
            mock_claude.assert_called_once_with(model="opus")

    def test_generate_with_no_available_providers_raises(self) -> None:
        """Test that generate raises when no providers are in available list."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ):
            client = DualProviderClient(primary="gemini")
            # Manually clear providers to simulate runtime failure
            client.providers = {}

            with pytest.raises(RuntimeError, match="No providers available"):
                client.generate(prompt="Test prompt")

    def test_usage_tracking_from_response(self, mock_gemini_response: LLMResponse) -> None:
        """Test that usage data is correctly passed through from response."""
        with patch("app.agents.llm_client.GeminiCLIClient") as mock_gemini, patch(
            "app.agents.llm_client.ClaudeCLIClient"
        ):
            mock_gemini.return_value.generate.return_value = mock_gemini_response

            client = DualProviderClient(primary="gemini")
            response = client.generate(prompt="Test prompt")

            assert response.usage["prompt_tokens"] == 100
            assert response.usage["completion_tokens"] == 50
            assert response.usage["total_tokens"] == 150
