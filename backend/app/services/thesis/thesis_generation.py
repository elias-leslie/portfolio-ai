"""Thesis Generation - LLM-powered thesis generation logic."""

from __future__ import annotations

import json
from typing import Any

from ...agents.llm_client import DualProviderClient
from ...logging_config import get_logger
from .thesis_prompts import THESIS_GENERATION_PROMPT

logger = get_logger(__name__)


class ThesisGenerator:
    """Handles LLM-based thesis generation."""

    def __init__(self, llm_client: DualProviderClient | None = None) -> None:
        """Initialize generator.

        Args:
            llm_client: Dual-provider LLM client (Gemini + Claude)
        """
        self._llm_client = llm_client

    def _ensure_llm_client(self) -> DualProviderClient:
        """Lazy-initialize LLM client."""
        if self._llm_client is None:
            self._llm_client = DualProviderClient(primary="gemini", agent_slug="equity-analyst")
            logger.info("thesis_llm_client_initialized")
        return self._llm_client

    def parse_json_response(self, content: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown blocks.

        Args:
            content: LLM response content

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        # Try to extract JSON from markdown blocks
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            elif "{" in content:
                # Find JSON object boundaries
                start = content.index("{")
                end = content.rindex("}") + 1
                json_str = content[start:end]
            else:
                raise ValueError("No JSON found in response")

            parsed: dict[str, Any] = json.loads(json_str)
            return parsed

        except (json.JSONDecodeError, ValueError, IndexError) as e:
            logger.error("json_parse_failed", content_preview=content[:500], error=str(e))
            raise ValueError(f"Failed to parse JSON from LLM response: {e}") from e

    def generate_with_gemini(self, intelligence: dict[str, Any]) -> dict[str, Any]:
        """Generate thesis using Gemini.

        Args:
            intelligence: Intelligence data

        Returns:
            Parsed thesis JSON

        Raises:
            RuntimeError: If generation fails
        """
        llm = self._ensure_llm_client()

        # Build prompt
        intelligence_json = json.dumps(intelligence, indent=2)
        prompt = THESIS_GENERATION_PROMPT.format(intelligence_json=intelligence_json)

        logger.info("gemini_thesis_generation_started", prompt_length=len(prompt))

        try:
            response = llm.generate(
                prompt=prompt,
                system="You are an expert equity analyst. Always respond with valid JSON.",
                temperature=0.7,  # Allow some creativity in reasoning
                purpose="thesis_generation",
            )

            thesis_data = self.parse_json_response(response.content)
            logger.info("gemini_thesis_generated", keys=list(thesis_data.keys()))
            return thesis_data

        except Exception as e:
            logger.error("gemini_thesis_generation_failed", error=str(e))
            raise RuntimeError(f"Gemini thesis generation failed: {e}") from e
