"""Thesis generation logic."""

from __future__ import annotations

import copy
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
            llm_client: Routed LLM client
        """
        self._llm_client = llm_client

    def _ensure_llm_client(self) -> DualProviderClient:
        """Lazy-initialize LLM client."""
        if self._llm_client is None:
            self._llm_client = DualProviderClient(agent_slug="equity-analyst")
            logger.info("thesis_llm_client_initialized", agent_slug="equity-analyst")
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

    @staticmethod
    def _parse_float_str(value: str) -> float | None:
        """Parse a float from a stripped non-empty string, returning None on failure."""
        stripped = value.strip()
        if not stripped:
            return None
        try:
            return float(stripped)
        except ValueError:
            return None

    def _coerce_float(self, value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str):
            return self._parse_float_str(value)
        return None

    def _sanitize_intelligence_for_prompt(self, intelligence: dict[str, Any]) -> dict[str, Any]:
        sanitized = copy.deepcopy(intelligence)
        constraints: list[str] = ["Ignore unavailable trading guidance fields."]

        trading = sanitized.get("trading")
        if not isinstance(trading, dict):
            sanitized["analysis_constraints"] = constraints
            return sanitized

        entry_price = self._coerce_float(trading.get("entry_price"))
        stop_loss = self._coerce_float(trading.get("stop_loss"))
        profit_target = self._coerce_float(trading.get("profit_target"))

        if entry_price is None or entry_price <= 0:
            trading["entry_price"] = None
            constraints.append("Entry price was unavailable or invalid in the source intelligence.")
        stop_too_close = (
            stop_loss is not None
            and entry_price is not None
            and abs(entry_price - stop_loss) / entry_price < 0.005
        )
        if stop_loss is None or entry_price is None or stop_loss <= 0 or stop_loss >= entry_price or stop_too_close:
            trading["stop_loss"] = None
            constraints.append("Stop loss was unavailable or failed risk validation.")
        if (
            profit_target is None
            or entry_price is None
            or profit_target <= entry_price
        ):
            trading["profit_target"] = None
            constraints.append("Profit target was unavailable or failed reward validation.")

        portfolio = sanitized.get("portfolio") or {}
        context = portfolio.get("context") if isinstance(portfolio, dict) else {}
        total_value = self._coerce_float(context.get("total_value")) if isinstance(context, dict) else None
        position_size_shares = trading.get("position_size_shares")
        position_size_dollars = self._coerce_float(trading.get("position_size_dollars"))
        invalid_sizing = (
            position_size_shares is not None
            or position_size_dollars is not None
        ) and (
            total_value is None
            or total_value <= 0
            or position_size_dollars is None
            or position_size_dollars <= 0
            or position_size_dollars > total_value
        )
        if invalid_sizing:
            trading["position_size_shares"] = None
            trading["position_size_dollars"] = None
            constraints.append("Position sizing was unavailable because the source sizing exceeded portfolio context or had no usable portfolio value.")

        sanitized["analysis_constraints"] = constraints
        return sanitized

    def generate_thesis(self, intelligence: dict[str, Any]) -> dict[str, Any]:
        """Generate thesis using the configured finance analyst agent.

        Args:
            intelligence: Intelligence data

        Returns:
            Parsed thesis JSON

        Raises:
            RuntimeError: If generation fails
        """
        llm = self._ensure_llm_client()

        # Build prompt
        intelligence_json = json.dumps(self._sanitize_intelligence_for_prompt(intelligence), indent=2)
        prompt = THESIS_GENERATION_PROMPT.format(intelligence_json=intelligence_json)

        logger.info("thesis_generation_started", prompt_length=len(prompt))

        try:
            response = llm.generate(
                prompt=prompt,
                system="You are an expert equity analyst. Always respond with valid JSON.",
                temperature=0.7,  # Allow some creativity in reasoning
                purpose="thesis_generation",
            )

            thesis_data = self.parse_json_response(response.content)
            logger.info("thesis_generated", keys=list(thesis_data.keys()))
            return thesis_data

        except Exception as e:
            logger.error("thesis_generation_failed", error=str(e))
            raise RuntimeError(f"Thesis generation failed: {e}") from e
