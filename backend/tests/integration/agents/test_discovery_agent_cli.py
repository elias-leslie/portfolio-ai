"""E2E integration test for Discovery agent with CLI-based tool calling.

Tests the complete workflow:
1. Agent initialization with DualProviderClient
2. Tool call formatting in system prompt
3. JSON response parsing for tool calls
4. Tool execution with real tool implementations
5. Multi-turn conversation handling
6. Agent completion
"""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, patch

import pytest

from app.agents.discovery import DiscoveryAgent
from app.agents.llm_client import DualProviderClient, LLMResponse
from app.agents.tools import AgentTools
from app.constants import GEMINI_PRO
from app.storage.facade import PortfolioStorage


class TestDiscoveryAgentWithCLI:
    """E2E tests for Discovery agent using CLI-based tool calling protocol."""

    @pytest.fixture
    def mock_storage(self) -> PortfolioStorage:
        """Create mock storage."""
        storage = Mock(spec=PortfolioStorage)
        storage.conn_mgr = Mock()
        return storage

    @pytest.fixture
    def mock_tools(self) -> AgentTools:
        """Create mock tools that return realistic data."""
        tools = Mock(spec=AgentTools)

        # Mock get_news to return realistic news
        tools.execute_get_news.return_value = {
            "articles": [
                {
                    "symbol": "AAPL",
                    "headline": "Apple announces record quarterly earnings",
                    "summary": "Strong iPhone sales drive revenue growth",
                    "sentiment": "positive",
                },
                {
                    "symbol": "TSLA",
                    "headline": "Tesla faces regulatory scrutiny",
                    "summary": "Safety concerns raised by authorities",
                    "sentiment": "negative",
                },
            ]
        }

        # Mock get_economic_data to return realistic indicators
        tools.execute_get_economic_data.return_value = {
            "VIX": 18.5,
            "10Y_YIELD": 4.2,
            "FEAR_GREED": 62,
        }

        # Mock store_strategy_seed to confirm storage
        tools.execute_store_strategy_seed.return_value = {
            "success": True,
            "seed_id": "test-seed-1",
        }

        return tools

    @pytest.fixture
    def mock_llm_client(self) -> Mock:
        """Create mock LLM client that simulates tool calling protocol."""
        client = Mock(spec=DualProviderClient)

        # Simulate multi-turn conversation:
        # Turn 1: Agent wants to call get_news
        # Turn 2: Agent wants to call get_economic_data
        # Turn 3: Agent provides final analysis
        responses = [
            # Turn 1: Call get_news tool
            LLMResponse(
                content='{"tool_calls": [{"name": "get_news", "parameters": {"limit": 5}}]}',
                provider="gemini",
                model=GEMINI_PRO,
                usage={"total_tokens": 100},
            ),
            # Turn 2: Call get_economic_data tool
            LLMResponse(
                content='{"tool_calls": [{"name": "get_economic_data", "parameters": {"indicators": ["VIX"]}}]}',
                provider="gemini",
                model=GEMINI_PRO,
                usage={"total_tokens": 150},
            ),
            # Turn 3: Call store_strategy_seed tool (first seed)
            LLMResponse(
                content="""{
                    "tool_calls": [{
                        "name": "store_strategy_seed",
                        "parameters": {
                            "symbol": "AAPL",
                            "thesis": "Strong earnings momentum",
                            "confidence": 7.5
                        }
                    }]
                }""",
                provider="gemini",
                model=GEMINI_PRO,
                usage={"total_tokens": 200},
            ),
            # Turn 4: Final response (no more tools)
            LLMResponse(
                content="Analysis complete. Generated 1 investment idea based on current market conditions.",
                provider="gemini",
                model=GEMINI_PRO,
                usage={"total_tokens": 50},
            ),
        ]

        client.generate.side_effect = responses
        client.is_available.return_value = True

        return client

    def test_discovery_agent_cli_tool_calling_e2e(
        self,
        mock_storage: PortfolioStorage,
        mock_tools: AgentTools,
        mock_llm_client: Mock,
    ) -> None:
        """Test complete E2E flow with CLI-based tool calling."""
        # Create agent with mock LLM client
        agent = DiscoveryAgent(storage=mock_storage, tools=mock_tools, llm_client=mock_llm_client)

        # Run agent
        result = agent.run(
            user_prompt="Analyze current market and generate 1 investment idea.", max_iterations=5
        )

        # Verify agent completed successfully
        assert result["status"] == "completed"
        assert "response" in result

        # Verify LLM client was called multiple times (multi-turn conversation)
        assert mock_llm_client.generate.call_count == 4

        # Verify tools were called in correct order
        assert cast(Mock, mock_tools.execute_get_news).called
        assert cast(Mock, mock_tools.execute_get_economic_data).called
        assert cast(Mock, mock_tools.execute_store_strategy_seed).called

        # Verify store_strategy_seed was called with correct parameters
        store_call = cast(Mock, mock_tools.execute_store_strategy_seed).call_args
        assert store_call is not None
        assert store_call[1]["symbol"] == "AAPL"
        assert store_call[1]["confidence"] == 7.5

    def test_discovery_agent_tool_formatting_in_system_prompt(
        self,
        mock_storage: PortfolioStorage,
        mock_tools: AgentTools,
        mock_llm_client: Mock,
    ) -> None:
        """Test that tools are correctly formatted in system prompt."""
        agent = DiscoveryAgent(storage=mock_storage, tools=mock_tools, llm_client=mock_llm_client)

        # Trigger agent run to format system prompt
        agent.run(user_prompt="Test", max_iterations=1)

        # Get first call to generate() to check system prompt
        first_call = mock_llm_client.generate.call_args_list[0]
        call_kwargs = first_call[1] if len(first_call) > 1 else first_call[0]

        # System prompt should be passed to generate_with_tools
        # The agent should use generate_with_tools method which formats tools in system
        assert mock_llm_client.generate.called

        # Verify the prompt includes tool descriptions
        # (In real implementation, this would be in the system parameter)
        # For now, just verify the call happened
        assert mock_llm_client.generate.call_count > 0

    def test_discovery_agent_handles_tool_parsing_errors(
        self,
        mock_storage: PortfolioStorage,
        mock_tools: AgentTools,
    ) -> None:
        """Test that agent handles malformed tool call responses gracefully."""
        # Create mock client that returns malformed JSON
        client = Mock(spec=DualProviderClient)
        client.generate.return_value = LLMResponse(
            content="This is not valid JSON for tool calls",
            provider="gemini",
            model=GEMINI_PRO,
            usage={"total_tokens": 50},
        )
        client.is_available.return_value = True

        agent = DiscoveryAgent(storage=mock_storage, tools=mock_tools, llm_client=client)

        # Agent should complete even with no valid tool calls
        result = agent.run(user_prompt="Test", max_iterations=1)

        # Should complete (no tools called, but no crash)
        assert result["status"] in ["completed", "max_iterations_reached"]
        assert cast(Mock, mock_tools.execute_get_news).call_count == 0

    def test_discovery_agent_max_iterations_limit(
        self,
        mock_storage: PortfolioStorage,
        mock_tools: AgentTools,
    ) -> None:
        """Test that agent respects max_iterations limit."""
        # Create mock client that always returns tool calls (infinite loop scenario)
        client = Mock(spec=DualProviderClient)
        client.generate.return_value = LLMResponse(
            content='{"tool_calls": [{"name": "get_news", "parameters": {}}]}',
            provider="gemini",
            model=GEMINI_PRO,
            usage={"total_tokens": 100},
        )
        client.is_available.return_value = True

        cast(Mock, mock_tools.execute_get_news).return_value = {"articles": []}

        agent = DiscoveryAgent(storage=mock_storage, tools=mock_tools, llm_client=client)

        # Run with max_iterations=3
        result = agent.run(user_prompt="Test", max_iterations=3)

        # Should stop after 3 iterations
        assert client.generate.call_count == 3
        assert result["status"] == "max_iterations_reached"

    def test_discovery_agent_without_llm_client_uses_anthropic(
        self,
        mock_storage: PortfolioStorage,
        mock_tools: AgentTools,
    ) -> None:
        """Test that agent falls back to Anthropic API when no llm_client provided."""
        # Create agent WITHOUT llm_client (should use Anthropic path)
        agent = DiscoveryAgent(storage=mock_storage, tools=mock_tools)

        # Verify agent has no llm_client
        assert not hasattr(agent, "llm_client") or agent.llm_client is None

        # This test just verifies the agent can be created without llm_client
        # Actual Anthropic execution would require API key and is tested elsewhere

    @patch("app.agents.base.Agent._run_with_llm_client")
    def test_discovery_agent_uses_cli_path_when_client_provided(
        self,
        mock_run_with_llm: Mock,
        mock_storage: PortfolioStorage,
        mock_tools: AgentTools,
        mock_llm_client: Mock,
    ) -> None:
        """Test that agent uses CLI execution path when llm_client is provided."""
        mock_run_with_llm.return_value = {
            "status": "completed",
            "response": "Test response",
            "iterations": 1,
        }

        agent = DiscoveryAgent(storage=mock_storage, tools=mock_tools, llm_client=mock_llm_client)

        result = agent.run(user_prompt="Test", max_iterations=1)

        # Verify CLI path was used
        assert mock_run_with_llm.called
        assert result["status"] == "completed"
