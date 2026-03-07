"""LLM client abstraction for provider-agnostic agent execution.

MIGRATED TO AGENT HUB: All LLM requests now go through Agent Hub service.
Native Claude/Gemini CLI clients have been removed.

Uses Agent Hub API which provides unified access to all providers
with session management, caching, and cost tracking.
"""

from __future__ import annotations

from typing import Any, Literal

from ..constants import CLAUDE_SONNET, GEMINI_FLASH
from ..logging_config import get_logger
from .clients.agent_hub_client import AgentHubAPIClient
from .clients.base_client import LLMClient, LLMResponse

__all__ = [
    "AgentHubAPIClient",
    "DualProviderClient",
    "LLMClient",
    "LLMResponse",
]

logger = get_logger(__name__)


class DualProviderClient(LLMClient):
    """Single provider client using Agent Hub.

    DEPRECATED: Named 'DualProviderClient' for backwards compatibility only.
    Fallback logic has been removed - uses Agent Hub API exclusively.
    For new code, use AgentHubAPIClient directly.
    """

    def __init__(
        self,
        primary: Literal["claude", "gemini", "agent_hub"] = "agent_hub",
        claude_model: str = CLAUDE_SONNET,
        gemini_model: str = GEMINI_FLASH,
        agent_slug: str | None = None,
        use_agent_hub: bool = True,  # Kept for API compatibility, always True
        agent_hub_url: str = "http://localhost:8003",
    ) -> None:
        """Initialize Agent Hub client.

        Args:
            primary: Which provider to use ("claude", "gemini", or "agent_hub")
            claude_model: Claude model to use (if primary="claude" or "agent_hub")
            gemini_model: Gemini model to use (if primary="gemini")
            agent_slug: Preferred Agent Hub agent slug for routed completions
            use_agent_hub: Deprecated - always uses Agent Hub
            agent_hub_url: Agent Hub API base URL
        """
        del use_agent_hub  # Always uses Agent Hub now

        self.primary = primary

        # Determine model based on primary provider
        if primary == "gemini":
            model = gemini_model
        else:
            model = claude_model

        self._client = AgentHubAPIClient(
            agent_slug=agent_slug,
            model=model,
            base_url=agent_hub_url,
        )

        logger.info(
            "agent_hub_client_initialized",
            primary=primary,
            model=model,
            url=agent_hub_url,
        )

    def is_available(self) -> bool:
        """Check if Agent Hub is available.

        Returns:
            True if Agent Hub service is reachable
        """
        return self._client.is_available()

    def get_model_name(self) -> str:
        """Get model name.

        Returns:
            Model identifier
        """
        return self._client.get_model_name()

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate using Agent Hub API.

        No fallback - if Agent Hub fails, error is raised.

        Args:
            prompt: User prompt
            system: System prompt
            tools: Tool definitions
            temperature: Sampling temperature
            **kwargs: Additional options

        Returns:
            LLMResponse from Agent Hub

        Raises:
            RuntimeError: If generation fails
        """
        return self._client.generate(
            prompt=prompt,
            system=system,
            tools=tools,
            temperature=temperature,
            **kwargs,
        )

    def close(self) -> None:
        """Close the client connection."""
        self._client.close()
