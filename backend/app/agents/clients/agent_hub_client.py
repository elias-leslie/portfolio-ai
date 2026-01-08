"""Agent Hub API client.

Implements LLMClient interface for Agent Hub service.
Provides unified access to Claude and Gemini models via Agent Hub API.
"""

from __future__ import annotations

import time
from typing import Any

from agent_hub import AgentHubClient as SDKClient  # type: ignore[import-not-found]
from agent_hub.exceptions import AgentHubError  # type: ignore[import-not-found]

from ...logging_config import get_logger
from .base_client import LLMClient, LLMResponse

logger = get_logger(__name__)

# Default Agent Hub URL
DEFAULT_AGENT_HUB_URL = "http://localhost:8003"


class AgentHubAPIClient(LLMClient):
    """Agent Hub API client.

    Uses Agent Hub service for LLM completions.
    Supports both Claude and Gemini models via unified API.
    """

    def __init__(
        self,
        model: str = "claude-sonnet-4-5-20250514",
        base_url: str = DEFAULT_AGENT_HUB_URL,
        api_key: str | None = None,
        timeout: float = 300.0,
    ) -> None:
        """Initialize Agent Hub client.

        Args:
            model: Model to use (e.g., claude-sonnet-4-5-20250514, gemini-3-flash-preview)
            base_url: Agent Hub API base URL
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds

        Raises:
            RuntimeError: If Agent Hub service is not reachable
        """
        self.model = model
        self.base_url = base_url
        self._client = SDKClient(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
        )

        # Determine provider from model name
        if "claude" in model.lower():
            self.provider = "claude"
        elif "gemini" in model.lower():
            self.provider = "gemini"
        else:
            self.provider = "claude"  # Default to claude

        logger.info(
            "agent_hub_client_initialized",
            base_url=base_url,
            model=model,
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
        except Exception:
            return False

    def get_model_name(self) -> str:
        """Get model name.

        Returns:
            Model identifier
        """
        return self.model

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate completion using Agent Hub API.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            tools: Tool definitions (ignored - use generate_with_tools)
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            **kwargs: Additional options

        Returns:
            LLMResponse with completion

        Raises:
            RuntimeError: If API call fails
        """
        start_time = time.time()

        # Build messages
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        logger.info(
            "agent_hub_calling",
            model=self.model,
            prompt_length=len(prompt),
            has_system=system is not None,
        )

        try:
            response = self._client.complete(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                persist_session=False,  # Don't persist for CLI-style usage
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

            return LLMResponse(
                content=response.content,
                provider=response.provider,
                model=response.model,
                usage=usage,
                stop_reason=response.finish_reason or "end_turn",
            )

        except AgentHubError as e:
            logger.error("agent_hub_error", error=str(e))
            raise RuntimeError(f"Agent Hub API error: {e}") from e

        except Exception as e:
            logger.error("agent_hub_unexpected_error", error=str(e))
            raise RuntimeError(f"Unexpected Agent Hub error: {e}") from e

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> AgentHubAPIClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
