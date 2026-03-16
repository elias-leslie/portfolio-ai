"""LLM client abstraction for provider-agnostic agent execution.

MIGRATED TO AGENT HUB: All LLM requests now go through Agent Hub service.
Native Claude/Gemini CLI clients have been removed.

Uses Agent Hub API which provides unified access to all providers
with session management, caching, and cost tracking.
"""

from __future__ import annotations

from typing import Any, Literal

from ..config import settings
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
    """Agent Hub client wrapper.

    Uses Agent Hub API exclusively. For new code, prefer AgentHubAPIClient directly.
    """

    def __init__(
        self,
        primary: Literal["claude", "gemini", "agent_hub"] = "agent_hub",
        claude_model: str = CLAUDE_SONNET,
        gemini_model: str = GEMINI_FLASH,
        agent_slug: str | None = None,
        agent_hub_url: str | None = None,
    ) -> None:
        """Initialize Agent Hub client.

        Args:
            primary: Which provider to use ("claude", "gemini", or "agent_hub")
            claude_model: Claude model to use (if primary="claude" or "agent_hub")
            gemini_model: Gemini model to use (if primary="gemini")
            agent_slug: Preferred Agent Hub agent slug for routed completions
            agent_hub_url: Agent Hub API base URL
        """

        resolved_url = agent_hub_url or settings.agent_hub_url
        self.primary = primary

        # Only force a model when the caller explicitly chooses a provider lane.
        if primary == "gemini":
            model: str | None = gemini_model
        elif primary == "claude":
            model = claude_model
        else:
            model = None

        self._client = AgentHubAPIClient(
            agent_slug=agent_slug,
            model=model,
            base_url=resolved_url,
        )

        logger.info(
            "agent_hub_client_initialized",
            primary=primary,
            model=model,
            url=resolved_url,
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
