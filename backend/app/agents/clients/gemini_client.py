"""Gemini CLI client."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from typing import Any

from ...logging_config import get_logger
from .base_client import LLMClient, LLMResponse

logger = get_logger(__name__)


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

        # Build command (Gemini CLI uses positional argument for prompt)
        # Note: -p/--prompt flag is deprecated, use positional prompt instead
        cmd = [
            self.cli_path,
            "--output-format",
            "json",
            "-m",
            self.model,
            "--",  # End of options, prompt follows as positional
            full_prompt,
        ]

        logger.info(
            "gemini_cli_calling",
            model=self.model,
            prompt_length=len(full_prompt),
            has_system=system is not None,
        )

        try:
            # Execute CLI (prompt is passed as positional argument)
            result = subprocess.run(
                cmd,
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
            raise RuntimeError("Gemini CLI timed out after 5 minutes")  # noqa: B904

        except subprocess.CalledProcessError as e:
            logger.error(
                "gemini_cli_failed",
                exit_code=e.returncode,
                stderr=e.stderr.decode()[:500] if e.stderr else None,
            )
            raise RuntimeError(f"Gemini CLI failed: {e.stderr}")  # noqa: B904

        except json.JSONDecodeError as e:
            stdout_preview = result.stdout.decode()[:1000] if result.stdout else "(empty)"
            stderr_preview = result.stderr.decode()[:1000] if result.stderr else "(empty)"
            logger.error(
                "gemini_cli_json_error",
                error=str(e),
                stdout_preview=stdout_preview,
                stderr_preview=stderr_preview,
            )
            raise RuntimeError(
                f"Failed to parse Gemini CLI JSON: {e}. "
                f"Stdout: {stdout_preview[:200]}, Stderr: {stderr_preview[:200]}"
            ) from None
