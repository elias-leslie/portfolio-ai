# Tool Calling Protocol for CLI-Based LLM Providers

**Created**: 2025-11-17
**Status**: Design Phase
**Target**: Zero-cost tool calling via Gemini/Claude CLIs

---

## Problem Statement

Neither Gemini CLI nor Claude CLI support Anthropic-style custom tool definitions via command-line interface. They only support built-in tools (`Bash`, `Edit`, `Read`, etc.) which are designed for file system operations.

Our agents need custom tools like:
- `get_news(query)` - Fetch market news
- `get_portfolio_data()` - Get portfolio positions
- `get_price_data(symbols)` - Get stock prices & indicators
- `store_idea(title, thesis, ...)` - Save investment ideas
- And 5+ more agent tools

**We cannot use Anthropic API** - this would defeat the "zero cost" goal since tool calling is the primary use case for agents.

---

## Solution: JSON-Based Tool Calling Protocol

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Agent.run(prompt)                                       │
│  - Calls LLMClient.generate_with_tools(prompt, tools)   │
└─────────────────┬───────────────────────────────────────┘
                  │
                  v
┌─────────────────────────────────────────────────────────┐
│ LLMClient (Claude/Gemini CLI)                           │
│  1. Formats system prompt with tool definitions (JSON)  │
│  2. Sends to CLI: "You have these tools... respond      │
│     with JSON if you need to call a tool"               │
│  3. Parses response for tool calls                      │
│  4. If tool calls found:                                │
│     - Return LLMResponse(stop_reason="tool_use")        │
│  5. If no tool calls:                                   │
│     - Return LLMResponse(stop_reason="end_turn")        │
└─────────────────┬───────────────────────────────────────┘
                  │
                  v
┌─────────────────────────────────────────────────────────┐
│ Agent.run() (modified)                                  │
│  Loop:                                                  │
│   - If stop_reason == "tool_use":                       │
│     - Execute tool(s) from response.tool_calls          │
│     - Format results as "Tool Results: ..."             │
│     - Call LLMClient.generate_with_tools() again        │
│   - If stop_reason == "end_turn":                       │
│     - Return final response                             │
└─────────────────────────────────────────────────────────┘
```

---

## Protocol Specification

### 1. Tool Definition Format (in System Prompt)

```
You are an investment analysis agent. You have access to these tools:

TOOL: get_news
DESCRIPTION: Fetch recent news headlines about the market or specific topics
PARAMETERS:
  - query (string, required): News search query
  - max_results (integer, optional, default=10): Max headlines to return

TOOL: get_portfolio_data
DESCRIPTION: Fetch user's current portfolio positions and analytics
PARAMETERS: (none)

TOOL: get_price_data
DESCRIPTION: Fetch current price and technical indicators for stock symbols
PARAMETERS:
  - symbols (array of strings, required): Stock symbols like ["AAPL", "GOOGL"]

To call a tool, respond with JSON in this format:
{
  "tool_calls": [
    {
      "name": "get_news",
      "parameters": {"query": "technology stocks", "max_results": 5}
    }
  ]
}

You can call multiple tools in one response. After tools execute, you'll receive results and can call more tools or provide your final answer.

When you have enough information, respond with your final answer as plain text (NOT JSON).
```

### 2. Agent Response Patterns

**Tool Call Response:**
```json
{
  "tool_calls": [
    {
      "name": "get_price_data",
      "parameters": {"symbols": ["AAPL", "MSFT", "GOOGL"]}
    }
  ]
}
```

**Final Answer Response:**
```
Based on the current market data, I recommend the following investment ideas:

1. Technology Sector (AAPL, MSFT, GOOGL)
   - Strong technical indicators (RSI 45-55, bullish MACD)
   - Recent positive earnings
   - Risk: Moderate (beta 1.2-1.4)

...
```

### 3. Tool Result Format (sent back to agent)

```
TOOL RESULTS:
─────────────────────────────────────────────────────
Tool: get_price_data
Parameters: {"symbols": ["AAPL", "MSFT", "GOOGL"]}
Result:
{
  "AAPL": {
    "price": 150.25,
    "change_percent": 2.5,
    "rsi_14": 48.2,
    "macd": "bullish",
    ...
  },
  "MSFT": {...},
  "GOOGL": {...}
}
─────────────────────────────────────────────────────

What would you like to do next? You can call more tools or provide your final answer.
```

---

## Implementation Plan

### Phase 1: Update LLMClient Interface

```python
class LLMClient(ABC):
    @abstractmethod
    def generate_with_tools(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate with tool calling support.

        Args:
            prompt: User prompt (or tool results from previous turn)
            tools: Tool definitions (Anthropic API format)
            system: Base system prompt (tools will be appended)
            conversation_history: Previous turns (optional, for context)
            ...

        Returns:
            LLMResponse with:
              - stop_reason: "tool_use" or "end_turn"
              - tool_calls: List of {"name": ..., "parameters": ...}
              - content: Raw response text
        """
        pass
```

### Phase 2: Implement in GeminiCLIClient

```python
class GeminiCLIClient(LLMClient):
    def generate_with_tools(self, prompt, tools, system=None, **kwargs):
        # 1. Format system prompt with tool definitions
        system_with_tools = self._format_system_with_tools(system, tools)

        # 2. Call CLI
        result = self.generate(prompt, system=system_with_tools, **kwargs)

        # 3. Parse response for tool calls
        tool_calls = self._parse_tool_calls(result.content)

        if tool_calls:
            return LLMResponse(
                content=result.content,
                provider="gemini",
                model=self.model,
                usage=result.usage,
                stop_reason="tool_use",
                tool_calls=tool_calls,
                raw_response=result.raw_response,
            )
        else:
            return LLMResponse(
                content=result.content,
                provider="gemini",
                model=self.model,
                usage=result.usage,
                stop_reason="end_turn",
                raw_response=result.raw_response,
            )

    def _format_system_with_tools(self, system, tools):
        """Format system prompt with tool definitions."""
        tool_descriptions = []
        for tool in tools:
            schema = tool["input_schema"]
            params = []
            for param_name, param_def in schema["properties"].items():
                required = param_name in schema.get("required", [])
                params.append(
                    f"  - {param_name} ({param_def['type']}, "
                    f"{'required' if required else 'optional'}): {param_def['description']}"
                )

            tool_descriptions.append(
                f"TOOL: {tool['name']}\n"
                f"DESCRIPTION: {tool['description']}\n"
                f"PARAMETERS:\n" + "\n".join(params)
            )

        tools_section = "\n\n".join(tool_descriptions)

        return f"""{system or ''}

You have access to these tools:

{tools_section}

To call a tool, respond with JSON in this format:
{{
  "tool_calls": [
    {{
      "name": "tool_name",
      "parameters": {{"param": "value"}}
    }}
  ]
}}

You can call multiple tools in one response. After tools execute, you'll receive results and can call more tools or provide your final answer.

When you have enough information, respond with your final answer as plain text (NOT JSON).
"""

    def _parse_tool_calls(self, response_text):
        """Parse response text for tool calls.

        Returns:
            List of {"name": ..., "parameters": ...} or empty list
        """
        try:
            # Try to parse entire response as JSON
            data = json.loads(response_text.strip())
            if "tool_calls" in data:
                return data["tool_calls"]
        except json.JSONDecodeError:
            # Try to extract JSON block from markdown
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    if "tool_calls" in data:
                        return data["tool_calls"]
                except json.JSONDecodeError:
                    pass

        return []
```

### Phase 3: Implement in ClaudeCLIClient

Same as GeminiCLIClient - protocol is provider-agnostic.

### Phase 4: Update Agent.run()

```python
class Agent(ABC):
    def run(self, user_prompt: str, max_iterations: int = 10) -> AgentRunResult:
        run_id = str(uuid.uuid4())
        started_at = datetime.now(UTC)

        self._record_run_start(run_id, started_at)

        try:
            conversation_history = []
            current_prompt = user_prompt
            tool_calls_made = []

            for iteration in range(max_iterations):
                # Generate with tools
                response = self.llm_client.generate_with_tools(
                    prompt=current_prompt,
                    tools=self.get_tools(),
                    system=self.get_system_prompt(),
                    conversation_history=conversation_history,
                    max_tokens=4096,
                    temperature=1.0,
                )

                if response.stop_reason == "end_turn":
                    # Agent finished
                    return self._handle_completion(
                        run_id, started_at, tool_calls_made, iteration, response.content
                    )

                elif response.stop_reason == "tool_use":
                    # Execute tools
                    tool_results = []
                    for tool_call in response.tool_calls:
                        result = self.execute_tool(tool_call["name"], tool_call["parameters"])
                        tool_results.append({
                            "name": tool_call["name"],
                            "parameters": tool_call["parameters"],
                            "result": result,
                        })
                        tool_calls_made.append({
                            "name": tool_call["name"],
                            "input": tool_call["parameters"],
                            "result": result,
                        })

                        # Record in DB
                        self._record_tool_call(
                            run_id, tool_call["name"], tool_call["parameters"], result, 0
                        )

                    # Format tool results for next turn
                    current_prompt = self._format_tool_results(tool_results)
                    conversation_history.append({
                        "role": "assistant",
                        "content": response.content,
                        "tool_calls": response.tool_calls,
                    })
                    conversation_history.append({
                        "role": "user",
                        "content": current_prompt,
                    })

                else:
                    # Unexpected stop reason
                    return {"status": "error", "error": f"Unexpected stop: {response.stop_reason}"}

            # Max iterations
            return {"status": "max_iterations", ...}

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _format_tool_results(self, tool_results):
        """Format tool results for next turn."""
        parts = ["TOOL RESULTS:", "=" * 60]
        for tr in tool_results:
            parts.append(f"Tool: {tr['name']}")
            parts.append(f"Parameters: {json.dumps(tr['parameters'])}")
            parts.append(f"Result:\n{json.dumps(tr['result'], indent=2)}")
            parts.append("=" * 60)
        parts.append("\nWhat would you like to do next? You can call more tools or provide your final answer.")
        return "\n".join(parts)
```

---

## Testing Strategy

### 1. Unit Tests

```python
def test_format_system_with_tools():
    """Test tool definition formatting."""
    client = GeminiCLIClient()
    tools = [get_news_tool_definition(), get_portfolio_data_tool_definition()]
    system = "You are a helpful agent."

    result = client._format_system_with_tools(system, tools)

    assert "TOOL: get_news" in result
    assert "TOOL: get_portfolio_data" in result
    assert "tool_calls" in result  # Instruction format
    assert system in result

def test_parse_tool_calls_valid_json():
    """Test parsing valid JSON tool calls."""
    client = GeminiCLIClient()
    response = '{"tool_calls": [{"name": "get_news", "parameters": {"query": "tech"}}]}'

    tool_calls = client._parse_tool_calls(response)

    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "get_news"
    assert tool_calls[0]["parameters"]["query"] == "tech"

def test_parse_tool_calls_markdown_json():
    """Test parsing JSON in markdown block."""
    client = GeminiCLIClient()
    response = '''Let me fetch news for you:

```json
{
  "tool_calls": [{"name": "get_news", "parameters": {"query": "market"}}]
}
```
    '''

    tool_calls = client._parse_tool_calls(response)

    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "get_news"

def test_parse_tool_calls_no_tools():
    """Test parsing response with no tool calls."""
    client = GeminiCLIClient()
    response = "Here is my final answer: Buy AAPL."

    tool_calls = client._parse_tool_calls(response)

    assert len(tool_calls) == 0
```

### 2. Integration Tests

```python
@pytest.mark.integration
def test_discovery_agent_with_tools(storage):
    """Test Discovery agent with CLI-based tool calling."""
    llm_client = DualProviderClient(primary="gemini")
    agent = DiscoveryAgent(storage, llm_client=llm_client)

    result = agent.run("Find the best technology stocks based on current market conditions")

    assert result["status"] == "completed"
    assert len(result["tool_calls"]) > 0  # Should have called tools
    assert "get_price_data" in [tc["name"] for tc in result["tool_calls"]]
    assert result["response"]  # Should have final answer

@pytest.mark.integration
def test_portfolio_analyzer_with_tools(storage):
    """Test Portfolio Analyzer agent with CLI-based tool calling."""
    llm_client = DualProviderClient(primary="gemini")
    agent = PortfolioAnalyzerAgent(storage, llm_client=llm_client)

    result = agent.run("Analyze my portfolio and suggest improvements")

    assert result["status"] == "completed"
    assert "get_portfolio_data" in [tc["name"] for tc in result["tool_calls"]]
    assert result["response"]
```

---

## Benefits

1. **Zero Cost**: Uses CLI providers with cached credentials (no API costs)
2. **Provider Agnostic**: Same protocol works for Gemini and Claude CLIs
3. **Full Tool Support**: All 9 agent tools continue to work
4. **Backward Compatible**: Existing tool definitions unchanged
5. **Simple**: Just reformats prompts and parses responses - no complex infrastructure

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent doesn't follow JSON format | High | Add format examples in prompt, retry with clarification |
| Agent calls non-existent tools | Medium | Validate tool names, return error result |
| Tool parsing fails on edge cases | Medium | Comprehensive regex + JSON parsing fallbacks |
| Long conversations exceed context | Medium | Track token usage, truncate history if needed |

---

## Implementation Estimate

- Phase 1 (Interface updates): 30 min
- Phase 2 (Gemini implementation): 1 hour
- Phase 3 (Claude implementation): 45 min
- Phase 4 (Agent.run() refactor): 1 hour
- Testing & Debugging: 2 hours
- **Total: ~5-6 hours**

---

## Success Criteria

- [ ] GeminiCLIClient.generate_with_tools() implemented
- [ ] ClaudeCLIClient.generate_with_tools() implemented
- [ ] Agent.run() refactored to use new protocol
- [ ] All 9 agent tools work via CLI (no Anthropic API)
- [ ] Discovery agent test passes with 2+ tool calls
- [ ] Portfolio Analyzer test passes with 3+ tool calls
- [ ] Zero API costs confirmed (only CLI execution)
- [ ] Documentation updated with architecture
