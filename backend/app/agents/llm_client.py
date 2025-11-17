"""LLM client abstraction for provider-agnostic agent execution.

This module provides a unified interface for calling different LLM providers
(Gemini CLI, Claude CLI) with automatic failover support.

Zero API costs - uses local CLI tools with cached credentials/OAuth.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from abc import ABC, abstractmethod
from typing import Any, Literal

from ..logging_config import get_logger

logger = get_logger(__name__)


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


class ClaudeCLIClient(LLMClient):
    """Claude Code CLI client.

    Uses local Claude CLI with OAuth authentication (no API key needed).
    Included in Claude subscription ($20/month).
    """

    def __init__(self, model: str = "sonnet") -> None:
        """Initialize Claude CLI client.

        Args:
            model: Model to use ("sonnet", "opus", or full model name)

        Raises:
            RuntimeError: If Claude CLI not found in PATH
        """
        self.cli_path = shutil.which("claude")
        if not self.cli_path:
            raise RuntimeError("Claude CLI not found in PATH")

        self.model = model
        logger.info("claude_cli_initialized", cli_path=self.cli_path, model=model)

    def is_available(self) -> bool:
        """Check if Claude CLI is available.

        Returns:
            True if CLI executable found and version command works
        """
        if not self.cli_path:
            return False

        try:
            result = subprocess.run(
                [self.cli_path, "--version"],
                check=False,
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_model_name(self) -> str:
        """Get model name.

        Returns:
            Model identifier
        """
        return f"claude-{self.model}"

    def generate(
        self,
        prompt: str,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Generate using Claude CLI.

        Args:
            prompt: User prompt
            system: System prompt (optional)
            tools: Tool definitions (not yet supported in CLI mode)
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            **kwargs: Additional options

        Returns:
            LLMResponse with Claude's response

        Raises:
            RuntimeError: If CLI call fails
        """
        if not self.cli_path:
            raise RuntimeError("Claude CLI not initialized")

        start_time = time.time()

        # Build command
        cmd = [
            self.cli_path,
            "-p",
            prompt,
            "--output-format",
            "json",
            "--model",
            self.model,
            "--permission-mode",
            "bypassPermissions",
        ]

        # Add system prompt if provided
        if system:
            cmd.extend(["--system-prompt", system])

        logger.info(
            "claude_cli_calling",
            model=self.model,
            prompt_length=len(prompt),
            has_system=system is not None,
        )

        try:
            # Execute CLI with cleared API key (critical!)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min
                check=True,
                env={**os.environ, "ANTHROPIC_API_KEY": ""},  # Use OAuth, not API key
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Parse JSON response
            response_data = json.loads(result.stdout)

            # Check for errors
            if response_data.get("is_error"):
                error_msg = str(response_data.get("result", "Unknown error"))
                logger.error("claude_cli_error", error=error_msg)
                raise RuntimeError(f"Claude CLI returned error: {error_msg}")

            # Extract response text
            content = str(response_data.get("result", ""))

            # Extract usage stats
            usage_data = response_data.get("usage", {})
            usage = {
                "prompt_tokens": usage_data.get("input_tokens", 0),
                "completion_tokens": usage_data.get("output_tokens", 0),
                "total_tokens": (
                    usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0)
                ),
                "cache_creation_tokens": usage_data.get("cache_creation_input_tokens", 0),
                "cache_read_tokens": usage_data.get("cache_read_input_tokens", 0),
            }

            logger.info(
                "claude_cli_success",
                duration_ms=duration_ms,
                tokens=usage["total_tokens"],
                response_length=len(content),
            )

            return LLMResponse(
                content=content,
                provider="claude",
                model=self.model,
                usage=usage,
                stop_reason="end_turn",
                raw_response=response_data,
            )

        except subprocess.TimeoutExpired:
            logger.error("claude_cli_timeout")
            raise RuntimeError("Claude CLI timed out after 5 minutes")

        except subprocess.CalledProcessError as e:
            logger.error(
                "claude_cli_failed",
                exit_code=e.returncode,
                stderr=e.stderr[:500] if e.stderr else None,
            )
            raise RuntimeError(f"Claude CLI failed: {e.stderr}")

        except json.JSONDecodeError as e:
            logger.error("claude_cli_json_error", error=str(e))
            raise RuntimeError(f"Failed to parse Claude CLI JSON: {e}")


class GeminiCLIClient(LLMClient):
    """Gemini CLI client.

    Uses local Gemini CLI with cached credentials (completely free).
    """

    def __init__(self, model: str = "gemini-2.5-pro") -> None:
        """Initialize Gemini CLI client.

        Args:
            model: Model to use (gemini-2.5-pro, gemini-2.5-flash, gemini-1.5-pro)

        Raises:
            RuntimeError: If Gemini CLI not found in PATH
        """
        self.cli_path = shutil.which("gemini")
        if not self.cli_path:
            raise RuntimeError("Gemini CLI not found in PATH")

        self.model = model
        logger.info("gemini_cli_initialized", cli_path=self.cli_path, model=model)

    def is_available(self) -> bool:
        """Check if Gemini CLI is available.

        Returns:
            True if CLI executable found and accessible
        """
        if not self.cli_path:
            return False

        try:
            result = subprocess.run(
                [self.cli_path, "--version"],
                check=False,
                capture_output=True,
                timeout=5,
            )
            # Gemini CLI returns 0 or 1 depending on version
            return result.returncode in [0, 1]
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
        """Generate using Gemini CLI.

        Args:
            prompt: User prompt
            system: System prompt (will be prepended to prompt)
            tools: Tool definitions (not yet supported in CLI mode)
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            **kwargs: Additional options

        Returns:
            LLMResponse with Gemini's response

        Raises:
            RuntimeError: If CLI call fails
        """
        if not self.cli_path:
            raise RuntimeError("Gemini CLI not initialized")

        start_time = time.time()

        # Combine system and user prompt
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"

        # Build command
        cmd = [
            self.cli_path,
            "-p",
            "--output-format",
            "json",
            "-m",
            self.model,
        ]

        logger.info(
            "gemini_cli_calling",
            model=self.model,
            prompt_length=len(full_prompt),
            has_system=system is not None,
        )

        try:
            # Execute CLI
            result = subprocess.run(
                cmd,
                input=full_prompt.encode(),
                capture_output=True,
                timeout=300,  # 5 min
                check=True,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Parse JSON response
            response_data = json.loads(result.stdout.decode())

            # Extract response text
            content = str(response_data.get("response", ""))

            # Extract usage stats
            stats = response_data.get("stats", {}).get("models", {})
            tokens = stats.get("tokens", {})
            usage = {
                "prompt_tokens": tokens.get("prompt", 0),
                "completion_tokens": tokens.get("candidates", 0),
                "total_tokens": tokens.get("total", 0),
                "cached_tokens": tokens.get("cached", 0),
            }

            logger.info(
                "gemini_cli_success",
                duration_ms=duration_ms,
                tokens=usage["total_tokens"],
                response_length=len(content),
            )

            return LLMResponse(
                content=content,
                provider="gemini",
                model=self.model,
                usage=usage,
                stop_reason="end_turn",
                raw_response=response_data,
            )

        except subprocess.TimeoutExpired:
            logger.error("gemini_cli_timeout")
            raise RuntimeError("Gemini CLI timed out after 5 minutes")

        except subprocess.CalledProcessError as e:
            logger.error(
                "gemini_cli_failed",
                exit_code=e.returncode,
                stderr=e.stderr.decode()[:500] if e.stderr else None,
            )
            raise RuntimeError(f"Gemini CLI failed: {e.stderr}")

        except json.JSONDecodeError as e:
            logger.error("gemini_cli_json_error", error=str(e))
            raise RuntimeError(f"Failed to parse Gemini CLI JSON: {e}")


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
