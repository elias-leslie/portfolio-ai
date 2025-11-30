"Base classes for LLM clients."

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Any


class LLMResponse:
    """Standardized LLM response across all providers."""

    def __init__(
        self,
        content: str,
        provider: str,
        model: str,
        usage: dict[str, int],
        stop_reason: str = "end_turn",
        tool_calls: list[dict[str, Any]] | None = None,
        raw_response: dict[str, Any] | None = None,
    ) -> None:
        """Initialize LLM response.

        Args:
            content: Response text content
            provider: Provider name ("claude" or "gemini")
            model: Model identifier used
            usage: Token usage stats {prompt_tokens, completion_tokens, total_tokens}
            stop_reason: Why generation stopped ("end_turn", "tool_use", "max_tokens")
            tool_calls: List of tool call dicts (if any)
            raw_response: Original provider response for debugging
        """
        self.content = content
        self.provider = provider
        self.model = model
        self.usage = usage
        self.stop_reason = stop_reason
        self.tool_calls = tool_calls or []
        self.raw_response = raw_response or {}


class LLMClient(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion with optional tool use.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            tools: Tool definitions (optional)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Provider-specific options

        Returns:
            LLMResponse with content and metadata

        Raises:
            RuntimeError: If generation fails
        """
        pass

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
        """Generate with tool calling support (JSON-based protocol).

        This method implements a JSON-based tool calling protocol that works
        with CLI providers that don't support native tool calling.

        The protocol:
        1. Formats tool definitions into system prompt
        2. Instructs model to respond with JSON when calling tools
        3. Parses response for tool calls
        4. Returns LLMResponse with stop_reason="tool_use" or "end_turn"

        Args:
            prompt: User prompt or tool results from previous turn
            tools: Tool definitions in Anthropic API format
            system: Base system prompt (tools will be appended)
            conversation_history: Previous turns (optional, for context)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Provider-specific options

        Returns:
            LLMResponse with:
              - stop_reason: "tool_use" if tools called, "end_turn" if done
              - tool_calls: List of {"name": ..., "parameters": ...}
              - content: Raw response text

        Raises:
            RuntimeError: If generation fails
        """
        # Format system prompt with tool definitions
        system_with_tools = self._format_system_with_tools(system, tools)

        # Add conversation history context if provided
        full_prompt = prompt
        if conversation_history:
            history_parts = []
            for turn in conversation_history[-5:]:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                history_parts.append(f"[{role.upper()}]: {content[:500]}")
            full_prompt = "\n".join(history_parts) + f"\n\n[USER]: {prompt}"

        # Generate response
        response = self.generate(
            prompt=full_prompt,
            system=system_with_tools,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs,
        )

        # Parse for tool calls
        tool_calls = self._parse_tool_calls(response.content)

        if tool_calls:
            # Agent wants to call tools
            return LLMResponse(
                content=response.content,
                provider=response.provider,
                model=response.model,
                usage=response.usage,
                stop_reason="tool_use",
                tool_calls=tool_calls,
                raw_response=response.raw_response,
            )
        # Agent finished (final answer)
        return LLMResponse(
            content=response.content,
            provider=response.provider,
            model=response.model,
            usage=response.usage,
            stop_reason="end_turn",
            tool_calls=[],
            raw_response=response.raw_response,
        )

    def _format_system_with_tools(self, system: str | None, tools: list[dict[str, Any]]) -> str:
        """Format system prompt with tool definitions.

        Args:
            system: Base system prompt (can be None)
            tools: Tool definitions in Anthropic API format

        Returns:
            System prompt with tool definitions and calling instructions
        """
        tool_descriptions = []
        for tool in tools:
            schema = tool.get("input_schema", {})
            properties = schema.get("properties", {})
            required = schema.get("required", [])

            params = []
            if properties:
                for param_name, param_def in properties.items():
                    is_required = param_name in required
                    param_type = param_def.get("type", "any")
                    param_desc = param_def.get("description", "")
                    default = param_def.get("default", "")
                    default_str = f", default={default}" if default else ""

                    params.append(
                        f"  - {param_name} ({param_type}, "
                        f"{'required' if is_required else 'optional'}{default_str}): {param_desc}"
                    )
            else:
                params.append("  (no parameters)")

            tool_descriptions.append(
                f"TOOL: {tool['name']}\n"
                f"DESCRIPTION: {tool.get('description', '')}\n"
                f"PARAMETERS:\n" + "\n".join(params)
            )

        tools_section = "\n\n".join(tool_descriptions)

        return f"""{system or "You are a helpful AI assistant."} 

You have access to these tools:

{tools_section}

To call a tool, respond with JSON in this EXACT format:
{{
  "tool_calls": [
    {{
      "name": "tool_name",
      "parameters": {{"param": "value"}}
    }}
  ]
}}

CRITICAL RULES - DO NOT VIOLATE:
1. NEVER make up data or hallucinate information
2. ALWAYS use tools to get real factual data - DO NOT guess or estimate
3. If you need information, call the appropriate tool - NEVER fake results
4. You can call multiple tools in one response by adding more objects to the array
5. After tools execute, you'll receive REAL data - analyze that data ONLY
6. When you have enough REAL information from tools, provide your final answer as PLAIN TEXT (not JSON)
7. Only call tools that are defined above
8. Make sure all required parameters are provided
9. If no tool can provide needed data, say "I don't have access to that information" instead of guessing

Think step by step:
1. What FACTUAL information do I need?
2. Which tools can provide that REAL data?
3. Call the tools with correct parameters
4. Wait for REAL results from tools
5. Analyze ONLY the factual data returned by tools
6. Either call more tools for additional data OR provide final answer based ONLY on tool results
7. NEVER supplement tool data with made-up information
"""

    def _parse_tool_calls(self, response_text: str) -> list[dict[str, Any]]:
        """Parse response text for tool calls.

        Tries multiple strategies:
        1. Parse entire response as JSON
        2. Extract JSON from markdown code blocks
        3. Extract JSON with regex patterns

        Args:
            response_text: Raw response from LLM

        Returns:
            List of {"name": ..., "parameters": ...} dicts, or empty list
        """
        # Strategy 1: Try to parse entire response as JSON
        try:
            data = json.loads(response_text.strip())
            if isinstance(data, dict) and "tool_calls" in data:
                tool_calls = data["tool_calls"]
                if isinstance(tool_calls, list):
                    return tool_calls
        except json.JSONDecodeError:
            pass

        # Strategy 2: Extract JSON from markdown code blocks
        json_patterns = [
            r"```json\s*(.*?)\s*```",  # ```json ... ```
            r"```\s*({\s*\"tool_calls\".*?})\s*```",  # ``` {...} ```
        ]

        for pattern in json_patterns:
            match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    data = json.loads(match.group(1))
                    if isinstance(data, dict) and "tool_calls" in data:
                        tool_calls = data["tool_calls"]
                        if isinstance(tool_calls, list):
                            return tool_calls
                except json.JSONDecodeError:
                    continue

        # Strategy 3: Direct JSON object search
        json_match = re.search(r"(\{\s*\"tool_calls\".*?\}\s*)\s*$", response_text, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if isinstance(data, dict) and "tool_calls" in data:
                    tool_calls = data["tool_calls"]
                    if isinstance(tool_calls, list):
                        return tool_calls
            except json.JSONDecodeError:
                pass

        # No tool calls found
        return []

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available and operational.

        Returns:
            True if provider can be used, False otherwise
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Get the model identifier used by this client.

        Returns:
            Model name string
        """
        pass
