"""Thesis Validation - LLM-powered thesis validation logic."""

from __future__ import annotations

import json
from typing import Any

from ...constants import CLAUDE_SONNET
from ...logging_config import get_logger
from ...models.thesis import ThesisValidation
from .thesis_generation import ThesisGenerator
from .thesis_prompts import THESIS_VALIDATION_PROMPT

logger = get_logger(__name__)


class ThesisValidator:
    """Handles LLM-based thesis validation."""

    def __init__(self) -> None:
        """Initialize validator."""
        self._generator = ThesisGenerator()

    def validate_with_claude(
        self, intelligence: dict[str, Any], thesis_data: dict[str, Any]
    ) -> ThesisValidation:
        """Validate thesis using Claude.

        Args:
            intelligence: Original intelligence data
            thesis_data: Generated thesis data

        Returns:
            ThesisValidation object
        """
        from ...agents.clients.agent_hub_client import AgentHubAPIClient  # noqa: PLC0415

        try:
            claude = AgentHubAPIClient(agent_slug="critic", model=CLAUDE_SONNET)

            # Build validation prompt
            intelligence_json = json.dumps(intelligence, indent=2)
            thesis_json = json.dumps(thesis_data, indent=2)
            prompt = THESIS_VALIDATION_PROMPT.format(
                intelligence_json=intelligence_json, thesis_json=thesis_json
            )

            logger.info("claude_validation_started", prompt_length=len(prompt))

            response = claude.generate(
                prompt=prompt,
                system="You are a thorough investment thesis reviewer. Always respond with valid JSON.",
                temperature=0.3,  # Lower temperature for consistent reviews
                purpose="thesis_validation",
            )

            validation_data = self._generator.parse_json_response(response.content)

            logger.info(
                "claude_validation_completed",
                approved=validation_data.get("approved"),
                confidence=validation_data.get("confidence"),
            )

            return ThesisValidation(
                provider="claude",
                approved=validation_data.get("approved", False),
                confidence=validation_data.get("confidence", 0.0),
                review_summary=validation_data.get("review_summary", ""),
                issues=validation_data.get("issues", []),
            )

        except Exception as e:
            logger.error("claude_validation_failed", error=str(e))
            # Return failed validation instead of raising
            return ThesisValidation(
                provider="claude",
                approved=False,
                confidence=0.0,
                review_summary=f"Validation failed: {e}",
                issues=["Validation process encountered an error"],
            )

    def calculate_cross_validation_score(self, claude_validation: ThesisValidation) -> float:
        """Calculate cross-validation score based on Claude's validation.

        Args:
            claude_validation: Validation result from Claude

        Returns:
            Score between 0.0 and 1.0
        """
        if not claude_validation.approved:
            # Penalize based on number of issues
            issue_count = len(claude_validation.issues)
            penalty = min(0.3, issue_count * 0.1)
            return max(0.0, claude_validation.confidence - penalty)

        # Approved - return confidence directly
        return claude_validation.confidence
