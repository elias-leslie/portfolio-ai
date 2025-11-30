"""LLM client abstraction for provider-agnostic agent execution.

This module provides a unified interface for calling different LLM providers
(Gemini CLI, Claude CLI) with automatic failover support.

Zero API costs - uses local CLI tools with cached credentials/OAuth.
"""

from __future__ import annotations

from typing import Any, Literal

from ..logging_config import get_logger
from .clients.base_client import LLMClient, LLMResponse
from .clients.claude_client import ClaudeCLIClient
from .clients.gemini_client import GeminiCLIClient

__all__ = [
    "ClaudeCLIClient",
    "DualProviderClient",
    "GeminiCLIClient",
    "LLMClient",
    "LLMResponse",
]

logger = get_logger(__name__)


class DualProviderClient(LLMClient):
    """Dual provider client with automatic failover.

    Tries primary provider first, falls back to secondary on failure.
    Supports both Claude and Gemini CLIs.
    """

    def __init__(
        self,
        primary: Literal["claude", "gemini"] = "gemini",
        claude_model: str = "sonnet",
        gemini_model: str = "gemini-2.5-pro",
    ) -> None:
        """Initialize dual provider client.

        Args:
            primary: Which provider to try first ("claude" or "gemini")
            claude_model: Claude model to use
            gemini_model: Gemini model to use
        """
        self.primary = primary
        self.providers: dict[str, LLMClient] = {}

        # Initialize Claude CLI
        try:
            self.providers["claude"] = ClaudeCLIClient(model=claude_model)
            logger.info("claude_provider_initialized")
        except RuntimeError as e:
            logger.warning("claude_provider_unavailable", error=str(e))

        # Initialize Gemini CLI
        try:
            self.providers["gemini"] = GeminiCLIClient(model=gemini_model)
            logger.info("gemini_provider_initialized")
        except RuntimeError as e:
            logger.warning("gemini_provider_unavailable", error=str(e))

        if not self.providers:
            raise RuntimeError("No LLM providers available")

        logger.info(
            "dual_provider_initialized",
            primary=primary,
            available_providers=list(self.providers.keys()),
        )

    def is_available(self) -> bool:
        """Check if at least one provider is available.

        Returns:
            True if any provider is operational
        """
        return any(p.is_available() for p in self.providers.values())

    def get_model_name(self) -> str:
        """Get primary provider's model name.

        Returns:
            Model identifier
        """
        if self.primary in self.providers:
            return self.providers[self.primary].get_model_name()
        # Fallback to first available
        return next(iter(self.providers.values())).get_model_name()

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate with automatic failover.

        Tries primary provider first, falls back to secondary on error.

        Args:
            prompt: User prompt
            system: System prompt
            tools: Tool definitions
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            **kwargs: Additional options

        Returns:
            LLMResponse from whichever provider succeeded

        Raises:
            RuntimeError: If all providers fail
        """
        # Determine provider order
        if self.primary == "claude":
            order = ["claude", "gemini"]
        else:
            order = ["gemini", "claude"]

        # Filter to only available providers
        order = [p for p in order if p in self.providers]

        if not order:
            raise RuntimeError("No providers available")

        last_error = None

        for provider_name in order:
            provider = self.providers[provider_name]

            try:
                logger.info("attempting_generation", provider=provider_name)
                response = provider.generate(
                    prompt=prompt,
                    system=system,
                    tools=tools,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs,
                )

                # Success!
                fallback_used = provider_name != order[0]
                logger.info(
                    "generation_success",
                    provider=provider_name,
                    model=response.model,
                    tokens=response.usage.get("total_tokens", 0),
                    fallback_used=fallback_used,
                )

                return response

            except RuntimeError as e:
                logger.warning(
                    "generation_failed",
                    provider=provider_name,
                    error=str(e),
                )
                last_error = e
                continue

        # All providers failed
        raise RuntimeError(f"All providers failed. Last error: {last_error}")
