"""Claude CLI client."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any

from ...logging_config import get_logger
from .base_client import LLMClient, LLMResponse

logger = get_logger(__name__)


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
            raise RuntimeError("Claude CLI timed out after 5 minutes")  # noqa: B904

        except subprocess.CalledProcessError as e:
            logger.error(
                "claude_cli_failed",
                exit_code=e.returncode,
                stderr=e.stderr[:500] if e.stderr else None,
            )
            raise RuntimeError(f"Claude CLI failed: {e.stderr}")  # noqa: B904

        except json.JSONDecodeError as e:
            logger.error("claude_cli_json_error", error=str(e))
            raise RuntimeError(f"Failed to parse Claude CLI JSON: {e}")  # noqa: B904
