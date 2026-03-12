"""Agent Hub API client.

Implements LLMClient interface for Agent Hub service.
Uses either explicit model overrides or the agent's configured defaults.
"""

from __future__ import annotations

import time
from typing import Any

from agent_hub import AgentHubClient as SDKClient
from agent_hub.exceptions import AgentHubError

from ...config import settings
from ...logging_config import get_logger
from .base_client import LLMClient, LLMResponse

logger = get_logger(__name__)

# Default Agent Hub URL
DEFAULT_AGENT_HUB_URL = "http://localhost:8003"
DEFAULT_AGENT_SLUG = "chat"

# Portfolio-AI client credentials from centralized settings
PORTFOLIO_CLIENT_ID = settings.portfolio_client_id or None
PORTFOLIO_REQUEST_SOURCE = settings.portfolio_request_source

# Feature flag to enable/disable Agent Hub calls
AGENT_HUB_ENABLED = settings.agent_hub_enabled


class AgentHubAPIClient(LLMClient):
    """Agent Hub API client.

    Uses Agent Hub service for LLM completions.
    Supports both Claude and Gemini models via unified API.
    """

    def __init__(
        self,
        agent_slug: str | None = None,
        model: str | None = None,
        base_url: str = DEFAULT_AGENT_HUB_URL,
        api_key: str | None = None,
        timeout: float = 300.0,
        use_memory: bool | None = None,
    ) -> None:
        """Initialize Agent Hub client.

        Args:
            agent_slug: Preferred Agent Hub agent slug for routed completions
            model: Optional explicit model override. If omitted, Agent Hub
                chooses the agent's configured primary/fallback models.
            base_url: Agent Hub API base URL
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            use_memory: Explicit memory override. ``None`` defers to the agent's
                configured memory settings in Agent Hub.

        Raises:
            RuntimeError: If Agent Hub is disabled or service is not reachable
        """
        if not AGENT_HUB_ENABLED:
            raise RuntimeError(
                "Agent Hub is disabled. Set AGENT_HUB_ENABLED=true to enable agentic calls."
            )

        self.agent_slug = agent_slug or DEFAULT_AGENT_SLUG
        self._preferred_agent_slug = agent_slug
        self.model = model
        self.base_url = base_url
        self.timeout = timeout
        self.use_memory = use_memory
        self._client = SDKClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            client_name="portfolio-ai",  # Usage tracking
            client_id=PORTFOLIO_CLIENT_ID,
            request_source=PORTFOLIO_REQUEST_SOURCE,
        )

        # Determine provider from model name when explicitly overridden.
        if model is None:
            self.provider = "agent_hub"
        elif "claude" in model.lower():
            self.provider = "claude"
        elif "gemini" in model.lower():
            self.provider = "gemini"
        else:
            self.provider = "claude"  # Default to claude

        logger.info(
            "agent_hub_client_initialized",
            base_url=base_url,
            model=model,
            agent_slug=self.agent_slug,
            provider=self.provider,
        )

    def is_available(self) -> bool:
        """Check if Agent Hub service is available.

        Returns:
            True if service is reachable
        """
        try:
            # Simple health check - try to list models
            response = self._client._get_client().get("/health")
            return bool(response.is_success)
        except Exception as e:
            logger.debug("agent_hub_health_check_failed", error=str(e))
            return False

    def get_model_name(self) -> str:
        """Get model name.

        Returns:
            Model identifier
        """
        return self._preferred_agent_slug or self.model or DEFAULT_AGENT_SLUG

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
        purpose: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion using Agent Hub API.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            tools: Tool definitions for function calling
            temperature: Sampling temperature
            purpose: Purpose of this request for session tracking
            **kwargs: Additional options

        Returns:
            LLMResponse with completion

        Raises:
            RuntimeError: If API call fails
        """
        start_time = time.time()

        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

        logger.info(
            "agent_hub_calling",
            model=self.model,
            prompt_length=len(prompt),
            has_system=system is not None,
            has_tools=tools is not None,
            purpose=purpose,
        )

        try:
            response = self.complete_messages(
                messages=messages,
                temperature=temperature,
                tools=tools,
                purpose=purpose,
                system_prompt=system,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            usage = {
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens,
            }

            # Add cache info if available
            if response.usage.cache:
                usage["cache_creation_tokens"] = response.usage.cache.cache_creation_input_tokens
                usage["cache_read_tokens"] = response.usage.cache.cache_read_input_tokens

            logger.info(
                "agent_hub_success",
                duration_ms=duration_ms,
                tokens=usage["total_tokens"],
                response_length=len(response.content),
                provider=response.provider,
            )

            # Extract tool calls if present
            tool_calls = None
            if hasattr(response, "tool_calls") and response.tool_calls:
                tool_calls = [
                    {"name": tc.name, "parameters": tc.input, "id": tc.id}
                    for tc in response.tool_calls
                ]

            return LLMResponse(
                content=response.content,
                provider=response.provider,
                model=response.model,
                usage=usage,
                stop_reason=response.finish_reason or "end_turn",
                tool_calls=tool_calls,
                raw_response={
                    "session_id": response.session_id,
                    "from_cache": response.from_cache,
                    "finish_reason": response.finish_reason,
                },
            )

        except AgentHubError as e:
            logger.error("agent_hub_error", error=str(e), exc_info=True)
            raise RuntimeError(f"Agent Hub API error: {e}") from e

        except Exception as e:
            logger.error("agent_hub_unexpected_error", error=str(e), exc_info=True)
            raise RuntimeError(f"Unexpected Agent Hub error: {e}") from e

    def complete_messages(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
        purpose: str | None = None,
        session_id: str | None = None,
        max_turns: int = 1,
        thinking_level: str | None = None,
        response_format: dict[str, Any] | None = None,
        system_prompt: str | None = None,
        use_memory: bool | None = None,
        execute_tools: bool = False,
        enable_programmatic_tools: bool = False,
    ) -> Any:
        request_kwargs: dict[str, Any] = {
            "agent_slug": self.agent_slug,
            "messages": messages,
            "temperature": temperature,
            "project_id": "portfolio-ai",
            "purpose": purpose,
            "timeout_seconds": self.timeout,
        }
        if self.model is not None:
            request_kwargs["model"] = self.model
        if tools is not None:
            request_kwargs["tools"] = tools
        resolved_memory = self.use_memory if use_memory is None else use_memory
        if resolved_memory is not None:
            request_kwargs["use_memory"] = resolved_memory
        if session_id is not None:
            request_kwargs["session_id"] = session_id
        if max_turns != 1:
            request_kwargs["max_turns"] = max_turns
        if thinking_level is not None:
            request_kwargs["thinking_level"] = thinking_level
        if response_format is not None:
            request_kwargs["response_format"] = response_format
        if system_prompt is not None:
            request_kwargs["system_prompt"] = system_prompt
        if execute_tools:
            request_kwargs["execute_tools"] = True
        if enable_programmatic_tools:
            request_kwargs["enable_programmatic_tools"] = True
        return self._client.complete(**request_kwargs)

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> AgentHubAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
