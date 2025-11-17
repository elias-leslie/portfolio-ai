"""Unit tests for LLM client tool calling protocol.

Tests the JSON-based tool calling protocol implementation:
- _parse_tool_calls() with various response formats
- _format_system_with_tools() for system prompt formatting
"""

from __future__ import annotations

import pytest

from app.agents.llm_client import DualProviderClient, GeminiCLIClient


class TestParseToolCalls:
    """Test _parse_tool_calls() with various JSON formats."""

    @pytest.fixture
    def client(self) -> GeminiCLIClient:
        """Create a Gemini client for testing (doesn't make actual calls)."""
        return GeminiCLIClient()

    def test_parse_simple_json(self, client: GeminiCLIClient) -> None:
        """Test parsing simple JSON response."""
        response = """{"tool_calls": [{"name": "get_news", "parameters": {"ticker": "AAPL"}}]}"""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["name"] == "get_news"
        assert result[0]["parameters"] == {"ticker": "AAPL"}

    def test_parse_multiple_tool_calls(self, client: GeminiCLIClient) -> None:
        """Test parsing multiple tool calls in one response."""
        response = """{
            "tool_calls": [
                {"name": "get_news", "parameters": {"ticker": "AAPL"}},
                {"name": "get_price", "parameters": {"ticker": "GOOGL", "date": "2024-11-15"}}
            ]
        }"""

        result = client._parse_tool_calls(response)

        assert len(result) == 2
        assert result[0]["name"] == "get_news"
        assert result[1]["name"] == "get_price"
        assert result[1]["parameters"]["ticker"] == "GOOGL"

    def test_parse_json_in_markdown_code_block(self, client: GeminiCLIClient) -> None:
        """Test parsing JSON wrapped in markdown code block."""
        response = """Here's my tool call:

```json
{
    "tool_calls": [
        {"name": "get_economic_data", "parameters": {"indicator": "GDP"}}
    ]
}
```

This should work."""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["name"] == "get_economic_data"
        assert result[0]["parameters"] == {"indicator": "GDP"}

    def test_parse_json_in_generic_code_block(self, client: GeminiCLIClient) -> None:
        """Test parsing JSON wrapped in generic code block (no language specified)."""
        response = """Let me call this tool:

```
{"tool_calls": [{"name": "store_trade_idea", "parameters": {"ticker": "TSLA", "rationale": "Strong momentum"}}]}
```"""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["name"] == "store_trade_idea"
        assert result[0]["parameters"]["ticker"] == "TSLA"

    def test_parse_json_at_end_of_response(self, client: GeminiCLIClient) -> None:
        """Test parsing JSON at end of response (common pattern)."""
        response = """I need to get the news first.

{"tool_calls": [{"name": "get_news", "parameters": {"ticker": "NVDA", "limit": 10}}]}"""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["name"] == "get_news"
        assert result[0]["parameters"]["limit"] == 10

    def test_parse_json_with_whitespace(self, client: GeminiCLIClient) -> None:
        """Test parsing JSON with extra whitespace."""
        response = """

        {
            "tool_calls": [
                {
                    "name": "get_portfolio_data",
                    "parameters": {
                        "account_id": "default"
                    }
                }
            ]
        }

        """

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["name"] == "get_portfolio_data"

    def test_parse_no_tool_calls_text_response(self, client: GeminiCLIClient) -> None:
        """Test parsing plain text response (no tool calls)."""
        response = """Based on the data you provided, AAPL shows strong momentum with RSI at 68."""

        result = client._parse_tool_calls(response)

        assert result == []

    def test_parse_no_tool_calls_json_without_tool_calls_key(self, client: GeminiCLIClient) -> None:
        """Test parsing JSON that doesn't have 'tool_calls' key."""
        response = """{"answer": "The price is $150.25", "confidence": 0.95}"""

        result = client._parse_tool_calls(response)

        assert result == []

    def test_parse_empty_tool_calls_array(self, client: GeminiCLIClient) -> None:
        """Test parsing empty tool_calls array."""
        response = """{"tool_calls": []}"""

        result = client._parse_tool_calls(response)

        assert result == []

    def test_parse_malformed_json(self, client: GeminiCLIClient) -> None:
        """Test parsing malformed JSON (should return empty list)."""
        response = """{tool_calls: [{"name": "get_news"}]}"""  # Missing quotes around key

        result = client._parse_tool_calls(response)

        assert result == []

    def test_parse_nested_json_in_text(self, client: GeminiCLIClient) -> None:
        """Test parsing JSON embedded in explanatory text."""
        response = """I'll need to call the get_news tool first. Here's the call:

```json
{
    "tool_calls": [
        {
            "name": "get_news",
            "parameters": {
                "ticker": "AAPL",
                "limit": 5,
                "sources": ["reuters", "bloomberg"]
            }
        }
    ]
}
```

After getting the news, I'll analyze the sentiment."""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["name"] == "get_news"
        assert result[0]["parameters"]["sources"] == ["reuters", "bloomberg"]

    def test_parse_tool_call_with_complex_parameters(self, client: GeminiCLIClient) -> None:
        """Test parsing tool call with nested object parameters."""
        response = """{
            "tool_calls": [{
                "name": "backtest_strategy",
                "parameters": {
                    "ticker": "AAPL",
                    "period": {"start": "2024-01-01", "end": "2024-12-31"},
                    "rules": {
                        "entry": {"rsi_below": 30},
                        "exit": {"rsi_above": 70}
                    }
                }
            }]
        }"""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["name"] == "backtest_strategy"
        assert result[0]["parameters"]["period"]["start"] == "2024-01-01"
        assert result[0]["parameters"]["rules"]["entry"]["rsi_below"] == 30

    def test_parse_tool_call_with_array_parameters(self, client: GeminiCLIClient) -> None:
        """Test parsing tool call with array parameters."""
        response = """{
            "tool_calls": [{
                "name": "analyze_tickers",
                "parameters": {
                    "tickers": ["AAPL", "GOOGL", "MSFT", "TSLA"],
                    "metrics": ["price", "volume", "rsi"]
                }
            }]
        }"""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["parameters"]["tickers"] == ["AAPL", "GOOGL", "MSFT", "TSLA"]
        assert len(result[0]["parameters"]["metrics"]) == 3


class TestFormatSystemWithTools:
    """Test _format_system_with_tools() for system prompt formatting."""

    @pytest.fixture
    def client(self) -> GeminiCLIClient:
        """Create a Gemini client for testing."""
        return GeminiCLIClient()

    def test_format_with_single_simple_tool(self, client: GeminiCLIClient) -> None:
        """Test formatting system prompt with single simple tool."""
        system = "You are a helpful assistant."
        tools = [
            {
                "name": "get_price",
                "description": "Get current price for a ticker",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"}
                    },
                    "required": ["ticker"],
                },
            }
        ]

        result = client._format_system_with_tools(system, tools)

        assert "You are a helpful assistant." in result
        assert "TOOL: get_price" in result
        assert "Get current price for a ticker" in result
        assert "ticker (string, required): Stock ticker symbol" in result
        assert '"tool_calls"' in result  # JSON format instructions
        assert "NEVER make up data or hallucinate information" in result

    def test_format_with_multiple_tools(self, client: GeminiCLIClient) -> None:
        """Test formatting system prompt with multiple tools."""
        system = "You are a trading assistant."
        tools = [
            {
                "name": "get_news",
                "description": "Fetch news articles",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Ticker symbol"},
                        "limit": {"type": "integer", "description": "Max articles"},
                    },
                    "required": ["ticker"],
                },
            },
            {
                "name": "get_price",
                "description": "Get current price",
                "input_schema": {
                    "type": "object",
                    "properties": {"ticker": {"type": "string", "description": "Ticker symbol"}},
                    "required": ["ticker"],
                },
            },
        ]

        result = client._format_system_with_tools(system, tools)

        assert "TOOL: get_news" in result
        assert "TOOL: get_price" in result
        assert "Fetch news articles" in result
        assert "Get current price" in result

    def test_format_with_optional_parameters(self, client: GeminiCLIClient) -> None:
        """Test formatting tool with optional parameters."""
        system = "Assistant"
        tools = [
            {
                "name": "get_news",
                "description": "Fetch news",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Ticker"},
                        "limit": {"type": "integer", "description": "Limit", "default": 10},
                        "source": {"type": "string", "description": "Source"},
                    },
                    "required": ["ticker"],
                },
            }
        ]

        result = client._format_system_with_tools(system, tools)

        assert "ticker (string, required)" in result
        assert "limit (integer, optional, default=10)" in result
        assert "source (string, optional)" in result

    def test_format_with_no_parameters(self, client: GeminiCLIClient) -> None:
        """Test formatting tool with no parameters."""
        system = "Assistant"
        tools = [
            {
                "name": "get_market_status",
                "description": "Check if market is open",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        result = client._format_system_with_tools(system, tools)

        assert "TOOL: get_market_status" in result
        assert "Check if market is open" in result
        assert "(no parameters)" in result

    def test_format_includes_anti_hallucination_rules(self, client: GeminiCLIClient) -> None:
        """Test that formatted prompt includes anti-hallucination safeguards."""
        system = "Assistant"
        tools = [
            {
                "name": "get_data",
                "description": "Get data",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        result = client._format_system_with_tools(system, tools)

        # Check for key anti-hallucination rules
        assert "NEVER make up data or hallucinate information" in result
        assert "ALWAYS use tools to get real factual data" in result
        assert "DO NOT guess or estimate" in result
        assert "analyze that data ONLY" in result

    def test_format_includes_json_format_instructions(self, client: GeminiCLIClient) -> None:
        """Test that formatted prompt includes JSON format instructions."""
        system = "Assistant"
        tools = [
            {
                "name": "tool1",
                "description": "Tool",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        result = client._format_system_with_tools(system, tools)

        # Check for JSON format instructions
        assert '"tool_calls"' in result
        assert '"name": "tool_name"' in result
        assert '"parameters": {"param": "value"}' in result
        assert "EXACT format" in result

    def test_format_with_none_system(self, client: GeminiCLIClient) -> None:
        """Test formatting with no custom system prompt."""
        tools = [
            {
                "name": "test_tool",
                "description": "Test",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        result = client._format_system_with_tools(None, tools)

        assert "You are a helpful AI assistant." in result
        assert "TOOL: test_tool" in result

    def test_format_with_complex_parameter_types(self, client: GeminiCLIClient) -> None:
        """Test formatting with various parameter types."""
        system = "Assistant"
        tools = [
            {
                "name": "complex_tool",
                "description": "Tool with various types",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name"},
                        "count": {"type": "integer", "description": "Count"},
                        "price": {"type": "number", "description": "Price"},
                        "active": {"type": "boolean", "description": "Active flag"},
                        "items": {"type": "array", "description": "Items list"},
                        "config": {"type": "object", "description": "Config object"},
                    },
                    "required": ["name", "count"],
                },
            }
        ]

        result = client._format_system_with_tools(system, tools)

        assert "name (string, required)" in result
        assert "count (integer, required)" in result
        assert "price (number, optional)" in result
        assert "active (boolean, optional)" in result
        assert "items (array, optional)" in result
        assert "config (object, optional)" in result


class TestDualProviderToolProtocol:
    """Test tool protocol integration with DualProviderClient."""

    def test_dual_provider_has_tool_parsing_methods(self) -> None:
        """Test that DualProviderClient inherits tool parsing methods."""
        client = DualProviderClient(primary="gemini")

        # Should have inherited methods from base class
        assert hasattr(client, "_parse_tool_calls")
        assert hasattr(client, "_format_system_with_tools")

    def test_dual_provider_parse_tool_calls(self) -> None:
        """Test tool call parsing works through DualProviderClient."""
        client = DualProviderClient(primary="gemini")

        response = """{"tool_calls": [{"name": "get_news", "parameters": {"ticker": "AAPL"}}]}"""
        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["name"] == "get_news"

    def test_dual_provider_format_system_with_tools(self) -> None:
        """Test system formatting works through DualProviderClient."""
        client = DualProviderClient(primary="gemini")

        tools = [
            {
                "name": "test",
                "description": "Test tool",
                "input_schema": {"type": "object", "properties": {}},
            }
        ]

        result = client._format_system_with_tools("Test", tools)

        assert "TOOL: test" in result
        assert "Test tool" in result


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def client(self) -> GeminiCLIClient:
        """Create a Gemini client for testing."""
        return GeminiCLIClient()

    def test_parse_tool_calls_with_unicode(self, client: GeminiCLIClient) -> None:
        """Test parsing tool calls with Unicode characters."""
        response = """{
            "tool_calls": [{
                "name": "get_news",
                "parameters": {
                    "ticker": "AAPL",
                    "query": "Apple's latest 🚀 product"
                }
            }]
        }"""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert "🚀" in result[0]["parameters"]["query"]

    def test_parse_tool_calls_with_escaped_quotes(self, client: GeminiCLIClient) -> None:
        """Test parsing tool calls with escaped quotes in parameters."""
        response = r"""{
            "tool_calls": [{
                "name": "analyze",
                "parameters": {
                    "text": "The CEO said \"we're bullish\""
                }
            }]
        }"""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert (
            '"' in result[0]["parameters"]["text"]
            or "we're bullish" in result[0]["parameters"]["text"]
        )

    def test_parse_tool_calls_with_null_parameters(self, client: GeminiCLIClient) -> None:
        """Test parsing tool calls with null parameter values."""
        response = """{
            "tool_calls": [{
                "name": "get_data",
                "parameters": {
                    "ticker": "AAPL",
                    "date": null
                }
            }]
        }"""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["parameters"]["date"] is None

    def test_format_system_with_empty_tools_list(self, client: GeminiCLIClient) -> None:
        """Test formatting with empty tools list."""
        result = client._format_system_with_tools("Test", [])

        # Should still include base instructions even with no tools
        assert "Test" in result
        assert "You have access to these tools:" in result

    def test_parse_tool_calls_very_long_response(self, client: GeminiCLIClient) -> None:
        """Test parsing tool calls from very long response."""
        # Simulate a long response with tool call at the end
        long_text = "Here's my analysis. " * 100  # 2000+ characters
        response = f"""{long_text}

{{"tool_calls": [{{"name": "get_news", "parameters": {{"ticker": "AAPL"}}}}]}}"""

        result = client._parse_tool_calls(response)

        assert len(result) == 1
        assert result[0]["name"] == "get_news"
