"""Cross-validation service for multi-agent output verification.

Orchestrates Gemini → Claude validation flow:
1. Gemini generates insight/output
2. Claude reviews and validates
3. Results queued for human review or auto-applied

Settings controlled via frontend Agent Hub settings.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from ..agents.clients.agent_hub_client import AgentHubAPIClient
from ..agents.clients.base_client import LLMClient, LLMResponse
from ..constants import CLAUDE_SONNET, GEMINI_FLASH
from ..logging_config import get_logger
from ._cross_validation_models import (
    CLAUDE_VALIDATION_PROMPT,
    DEFAULT_SETTINGS,
    CrossValidationSettings,
    DisagreementReason,
    ValidationResult,
    ValidationStatus,
)
from ._cross_validation_storage import (
    get_pending_validations as _get_pending_validations,
)
from ._cross_validation_storage import (
    resolve_validation as _resolve_validation,
)
from ._cross_validation_storage import (
    save_result as _save_result,
)

# Re-export everything so existing imports continue to work
__all__ = [
    "CLAUDE_VALIDATION_PROMPT",
    "DEFAULT_SETTINGS",
    "CrossValidationService",
    "CrossValidationSettings",
    "DisagreementReason",
    "ValidationResult",
    "ValidationStatus",
]

logger = get_logger(__name__)

_VALID_DISAGREEMENT_VALUES = {e.value for e in DisagreementReason}


def _extract_json_str(content: str) -> str | None:
    """Extract JSON string from content, handling markdown fences."""
    if "```json" in content:
        return content.split("```json")[1].split("```")[0].strip()
    if "```" in content:
        return content.split("```")[1].split("```")[0].strip()
    if "{" not in content:
        return None
    if "}" not in content:
        return None
    start = content.index("{")
    end = content.rindex("}") + 1
    return content[start:end]


def _make_failed_result(
    generator_output: str,
    error: Exception,
    context_type: str,
    context_symbol: str | None,
    metadata: dict[str, Any] | None,
) -> ValidationResult:
    """Build a ValidationResult for when validation errors out."""
    return ValidationResult(
        generator_output=generator_output,
        validator_review=f"Validation failed: {error}",
        validator_approved=False,
        has_disagreement=True,
        status=ValidationStatus.PENDING,
        context_type=context_type,
        context_symbol=context_symbol,
        metadata=metadata or {},
    )


class CrossValidationService:
    """Service for cross-validating AI outputs between providers."""

    def __init__(
        self,
        generator_client: LLMClient | None = None,
        validator_client: LLMClient | None = None,
        settings: CrossValidationSettings | None = None,
    ) -> None:
        self.settings = settings or DEFAULT_SETTINGS
        self._generator = generator_client
        self._validator = validator_client
        self._generator_initialized = False
        self._validator_initialized = False

    def _ensure_generator(self) -> LLMClient:
        """Ensure generator client is initialized."""
        if self._generator is None and not self._generator_initialized:
            try:
                self._generator = AgentHubAPIClient(model=GEMINI_FLASH)
            except RuntimeError as e:
                logger.warning("gemini_not_available", error=str(e))
            finally:
                self._generator_initialized = True
        if self._generator is None:
            raise RuntimeError("Generator client (Gemini) not available")
        return self._generator

    def _ensure_validator(self) -> LLMClient:
        """Ensure validator client is initialized."""
        if self._validator is None and not self._validator_initialized:
            try:
                self._validator = AgentHubAPIClient(model=CLAUDE_SONNET)
            except RuntimeError as e:
                logger.warning("claude_not_available", error=str(e))
            finally:
                self._validator_initialized = True
        if self._validator is None:
            raise RuntimeError("Validator client (Claude) not available")
        return self._validator

    def validate(
        self,
        generator_output: str,
        context_type: str = "insight",
        context_symbol: str | None = None,
        generator_confidence: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """Validate generator output using Claude."""
        if not self.settings["enabled"]:
            return ValidationResult(
                generator_output=generator_output,
                validator_review="Cross-validation disabled",
                validator_approved=True,
                status=ValidationStatus.AUTO_APPLIED,
                final_output=generator_output,
                context_type=context_type,
                context_symbol=context_symbol,
                metadata=metadata or {},
            )

        validator = self._ensure_validator()
        prompt = CLAUDE_VALIDATION_PROMPT.format(
            generator_output=generator_output,
            context_type=context_type,
            context_symbol=context_symbol or "N/A",
        )
        logger.info(
            "cross_validation_started",
            context_type=context_type,
            context_symbol=context_symbol,
            output_length=len(generator_output),
        )
        try:
            response = validator.generate(
                prompt=prompt,
                system="You are a thorough AI output reviewer. Always respond with valid JSON.",
                temperature=0.3,
                purpose="cross_validation",
            )
            return self._build_result(
                response=response,
                validator=validator,
                generator_output=generator_output,
                generator_confidence=generator_confidence,
                context_type=context_type,
                context_symbol=context_symbol,
                metadata=metadata,
            )
        except Exception as e:
            logger.error("cross_validation_failed", error=str(e), exc_info=True)
            return _make_failed_result(generator_output, e, context_type, context_symbol, metadata)

    def generate_and_validate(
        self,
        prompt: str,
        system: str | None = None,
        context_type: str = "insight",
        context_symbol: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[LLMResponse, ValidationResult]:
        """Generate output with Gemini and validate with Claude."""
        generator = self._ensure_generator()
        logger.info("gemini_generating", prompt_length=len(prompt))
        response = generator.generate(prompt=prompt, system=system, purpose="gemini_generation")
        try:
            result = self.validate(
                generator_output=response.content,
                context_type=context_type,
                context_symbol=context_symbol,
                metadata=metadata,
            )
        except Exception as e:
            logger.error("cross_validation_failed", error=str(e), exc_info=True)
            result = _make_failed_result(response.content, e, context_type, context_symbol, metadata)
        return response, result

    def get_pending_validations(self, limit: int = 50) -> list[ValidationResult]:
        """Get pending validations awaiting human review."""
        return _get_pending_validations(limit=limit)

    def resolve_validation(
        self,
        validation_id: str,
        approved: bool,
        final_output: str | None = None,
        resolved_by: str = "human",
    ) -> ValidationResult | None:
        """Resolve a pending validation."""
        return _resolve_validation(
            validation_id=validation_id,
            approved=approved,
            final_output=final_output,
            resolved_by=resolved_by,
        )

    @staticmethod
    def _parse_review_response(content: str) -> dict[str, Any]:
        """Parse JSON review response from validator."""
        json_str = _extract_json_str(content)
        if json_str is None:
            return {"approved": False, "review_summary": content}
        try:
            parsed: dict[str, Any] = json.loads(json_str)
            return parsed
        except (json.JSONDecodeError, ValueError, IndexError):
            logger.warning("review_parse_failed", content_preview=content[:200])
            return {"approved": False, "review_summary": content}

    def _build_result(
        self,
        response: LLMResponse,
        validator: LLMClient,
        generator_output: str,
        generator_confidence: float | None,
        context_type: str,
        context_symbol: str | None,
        metadata: dict[str, Any] | None,
    ) -> ValidationResult:
        """Build and persist a ValidationResult from a validator response."""
        review_data = self._parse_review_response(response.content)
        approved = review_data.get("approved", False)
        disagreement_reasons = [
            DisagreementReason(r)
            for r in review_data.get("disagreement_reasons", [])
            if r in _VALID_DISAGREEMENT_VALUES
        ]
        result = ValidationResult(
            generator_provider="gemini",
            generator_model=self._generator.get_model_name() if self._generator else "",
            generator_output=generator_output,
            generator_confidence=generator_confidence,
            validator_provider="claude",
            validator_model=validator.get_model_name() if hasattr(validator, "get_model_name") else "",
            validator_review=review_data.get("review_summary", response.content),
            validator_approved=approved,
            validator_confidence=review_data.get("confidence"),
            has_disagreement=not approved,
            disagreement_reasons=disagreement_reasons,
            disagreement_details=json.dumps(review_data.get("issues_found", [])),
            context_type=context_type,
            context_symbol=context_symbol,
            metadata=metadata or {},
        )
        result.status = self._determine_status(result)
        if result.status == ValidationStatus.AUTO_APPLIED:
            result.final_output = generator_output
            result.resolved_at = datetime.now(UTC).isoformat()
            result.resolved_by = "auto"
        _save_result(result)
        logger.info(
            "cross_validation_completed",
            result_id=result.id,
            approved=result.validator_approved,
            status=result.status.value,
            has_disagreement=result.has_disagreement,
        )
        return result

    def _determine_status(self, result: ValidationResult) -> ValidationStatus:
        """Determine validation status based on settings."""
        if not result.validator_approved:
            return ValidationStatus.PENDING
        if self.settings["full_auto_mode"]:
            confidence = result.validator_confidence or 0.0
            if confidence >= self.settings["auto_apply_threshold"]:
                return ValidationStatus.AUTO_APPLIED
            return ValidationStatus.PENDING
        if self.settings["require_human_review"]:
            return ValidationStatus.PENDING
        return ValidationStatus.AUTO_APPLIED
