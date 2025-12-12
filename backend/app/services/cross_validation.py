"""Cross-validation service for multi-agent output verification.

Orchestrates Gemini → Claude validation flow:
1. Gemini generates insight/output
2. Claude reviews and validates
3. Results queued for human review or auto-applied

Settings controlled via frontend Agent Hub settings.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, Field

from ..agents.clients.base_client import LLMClient, LLMResponse
from ..agents.clients.gemini_client import GeminiCLIClient
from ..logging_config import get_logger
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)


class ValidationStatus(str, Enum):
    """Status of a cross-validation result."""

    PENDING = "pending"  # Awaiting human review
    APPROVED = "approved"  # Human approved
    REJECTED = "rejected"  # Human rejected
    AUTO_APPLIED = "auto_applied"  # Applied automatically (full auto mode)
    MODIFIED = "modified"  # Human modified before applying


class DisagreementReason(str, Enum):
    """Reasons agents might disagree."""

    FACTUAL = "factual"  # Different facts cited
    LOGICAL = "logical"  # Different reasoning
    RISK_ASSESSMENT = "risk_assessment"  # Different risk evaluation
    CONFIDENCE = "confidence"  # Different confidence levels
    OTHER = "other"


class ValidationResult(BaseModel):
    """Result of cross-validation between two agents."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Original output
    generator_provider: str = "gemini"
    generator_model: str = ""
    generator_output: str = ""
    generator_confidence: float | None = None

    # Validation
    validator_provider: str = "claude"
    validator_model: str = ""
    validator_review: str = ""
    validator_approved: bool = False
    validator_confidence: float | None = None

    # Disagreement tracking
    has_disagreement: bool = False
    disagreement_reasons: list[DisagreementReason] = Field(default_factory=list)
    disagreement_details: str | None = None

    # Resolution
    status: ValidationStatus = ValidationStatus.PENDING
    resolved_at: str | None = None
    resolved_by: str | None = None  # "human" or "auto"
    final_output: str | None = None

    # Context
    context_type: str = ""  # "insight", "recommendation", "analysis"
    context_symbol: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CrossValidationSettings(TypedDict):
    """Settings for cross-validation behavior."""

    enabled: bool
    require_human_review: bool
    full_auto_mode: bool
    notify_on_disagreement: bool
    auto_apply_threshold: float  # 0.0 to 1.0


DEFAULT_SETTINGS: CrossValidationSettings = {
    "enabled": True,
    "require_human_review": True,
    "full_auto_mode": False,
    "notify_on_disagreement": True,
    "auto_apply_threshold": 0.9,
}


CLAUDE_VALIDATION_PROMPT = """You are reviewing output from another AI (Gemini) for accuracy and quality.

ORIGINAL OUTPUT TO REVIEW:
{generator_output}

CONTEXT:
- Type: {context_type}
- Symbol: {context_symbol}

YOUR TASK:
1. Verify factual accuracy of any claims
2. Check logical consistency of reasoning
3. Evaluate risk assessment if applicable
4. Assess confidence level appropriateness

RESPOND IN THIS JSON FORMAT:
{{
  "approved": true/false,
  "confidence": 0.0-1.0,
  "review_summary": "Brief summary of your review",
  "issues_found": ["list", "of", "issues"] or [],
  "suggestions": ["list", "of", "improvements"] or [],
  "disagreement_reasons": ["factual", "logical", "risk_assessment", "confidence"] or []
}}

Be thorough but fair. Approve if output is accurate and well-reasoned."""


class CrossValidationService:
    """Service for cross-validating AI outputs between providers."""

    def __init__(
        self,
        generator_client: LLMClient | None = None,
        validator_client: LLMClient | None = None,
        settings: CrossValidationSettings | None = None,
    ) -> None:
        """Initialize cross-validation service.

        Args:
            generator_client: Client for generating outputs (default: Gemini)
            validator_client: Client for validating outputs (default: Claude via CLI)
            settings: Cross-validation settings
        """
        self.settings = settings or DEFAULT_SETTINGS
        self._generator = generator_client
        self._validator = validator_client

        # Lazy initialization
        self._generator_initialized = False
        self._validator_initialized = False

    def _ensure_generator(self) -> LLMClient:
        """Ensure generator client is initialized."""
        if self._generator is None and not self._generator_initialized:
            try:
                self._generator = GeminiCLIClient()
                self._generator_initialized = True
            except RuntimeError as e:
                logger.warning("gemini_not_available", error=str(e))
                self._generator_initialized = True  # Don't retry
        if self._generator is None:
            raise RuntimeError("Generator client (Gemini) not available")
        return self._generator

    def _ensure_validator(self) -> LLMClient:
        """Ensure validator client is initialized."""
        if self._validator is None and not self._validator_initialized:
            # Import here to avoid circular dependency
            try:
                from ..agents.clients.claude_client import ClaudeCLIClient  # noqa: PLC0415

                self._validator = ClaudeCLIClient()
                self._validator_initialized = True
            except (ImportError, RuntimeError) as e:
                logger.warning("claude_not_available", error=str(e))
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
        """Validate generator output using Claude.

        Args:
            generator_output: The output to validate
            context_type: Type of content (insight, recommendation, analysis)
            context_symbol: Stock symbol if applicable
            generator_confidence: Confidence from generator (0-1)
            metadata: Additional context

        Returns:
            ValidationResult with approval status and review
        """
        if not self.settings["enabled"]:
            # Cross-validation disabled, auto-approve
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

        # Build validation prompt
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
                max_tokens=2048,
                temperature=0.3,  # Lower temperature for consistent reviews
            )

            # Parse JSON response
            review_data = self._parse_review_response(response.content)

            # Build result
            result = ValidationResult(
                generator_provider="gemini",
                generator_model=self._generator.get_model_name() if self._generator else "",
                generator_output=generator_output,
                generator_confidence=generator_confidence,
                validator_provider="claude",
                validator_model=validator.get_model_name()
                if hasattr(validator, "get_model_name")
                else "",
                validator_review=review_data.get("review_summary", response.content),
                validator_approved=review_data.get("approved", False),
                validator_confidence=review_data.get("confidence"),
                has_disagreement=not review_data.get("approved", False),
                disagreement_reasons=[
                    DisagreementReason(r)
                    for r in review_data.get("disagreement_reasons", [])
                    if r in [e.value for e in DisagreementReason]
                ],
                disagreement_details=json.dumps(review_data.get("issues_found", [])),
                context_type=context_type,
                context_symbol=context_symbol,
                metadata=metadata or {},
            )

            # Determine status based on settings
            result.status = self._determine_status(result)
            if result.status == ValidationStatus.AUTO_APPLIED:
                result.final_output = generator_output
                result.resolved_at = datetime.now(UTC).isoformat()
                result.resolved_by = "auto"

            # Persist result
            self._save_result(result)

            logger.info(
                "cross_validation_completed",
                result_id=result.id,
                approved=result.validator_approved,
                status=result.status.value,
                has_disagreement=result.has_disagreement,
            )

            return result

        except Exception as e:
            logger.error("cross_validation_failed", error=str(e))
            # Return pending result for human review
            return ValidationResult(
                generator_output=generator_output,
                validator_review=f"Validation failed: {e}",
                validator_approved=False,
                has_disagreement=True,
                status=ValidationStatus.PENDING,
                context_type=context_type,
                context_symbol=context_symbol,
                metadata=metadata or {},
            )

    def generate_and_validate(
        self,
        prompt: str,
        system: str | None = None,
        context_type: str = "insight",
        context_symbol: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[LLMResponse, ValidationResult]:
        """Generate output with Gemini and validate with Claude.

        Full cross-validation flow:
        1. Gemini generates response
        2. Claude reviews response
        3. Result queued for human review or auto-applied

        Args:
            prompt: Prompt for generation
            system: System prompt
            context_type: Type of content
            context_symbol: Stock symbol if applicable
            metadata: Additional context

        Returns:
            Tuple of (LLMResponse, ValidationResult)
        """
        generator = self._ensure_generator()

        # Generate with Gemini
        logger.info("gemini_generating", prompt_length=len(prompt))
        response = generator.generate(prompt=prompt, system=system)

        # Validate with Claude
        result = self.validate(
            generator_output=response.content,
            context_type=context_type,
            context_symbol=context_symbol,
            metadata=metadata,
        )

        return response, result

    def _parse_review_response(self, content: str) -> dict[str, Any]:
        """Parse JSON review response from validator."""
        # Try to extract JSON from response
        try:
            # Look for JSON block
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0].strip()
            elif "{" in content:
                # Find JSON object
                start = content.index("{")
                end = content.rindex("}") + 1
                json_str = content[start:end]
            else:
                return {"approved": False, "review_summary": content}

            parsed: dict[str, Any] = json.loads(json_str)
            return parsed
        except (json.JSONDecodeError, ValueError, IndexError):
            logger.warning("review_parse_failed", content_preview=content[:200])
            return {"approved": False, "review_summary": content}

    def _determine_status(self, result: ValidationResult) -> ValidationStatus:
        """Determine validation status based on settings."""
        if not result.validator_approved:
            return ValidationStatus.PENDING

        # Approved by validator
        if self.settings["full_auto_mode"]:
            # Check confidence threshold
            confidence = result.validator_confidence or 0.0
            if confidence >= self.settings["auto_apply_threshold"]:
                return ValidationStatus.AUTO_APPLIED
            return ValidationStatus.PENDING

        if self.settings["require_human_review"]:
            return ValidationStatus.PENDING

        return ValidationStatus.AUTO_APPLIED

    def _save_result(self, result: ValidationResult) -> None:
        """Save validation result to database."""
        conn_mgr = get_connection_manager()
        try:
            with conn_mgr.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO cross_validation_results (
                        id, created_at, generator_provider, generator_model,
                        generator_output, generator_confidence, validator_provider,
                        validator_model, validator_review, validator_approved,
                        validator_confidence, has_disagreement, disagreement_reasons,
                        disagreement_details, status, resolved_at, resolved_by,
                        final_output, context_type, context_symbol, metadata
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        result.id,
                        result.created_at,
                        result.generator_provider,
                        result.generator_model,
                        result.generator_output,
                        result.generator_confidence,
                        result.validator_provider,
                        result.validator_model,
                        result.validator_review,
                        result.validator_approved,
                        result.validator_confidence,
                        result.has_disagreement,
                        json.dumps([r.value for r in result.disagreement_reasons]),
                        result.disagreement_details,
                        result.status.value,
                        result.resolved_at,
                        result.resolved_by,
                        result.final_output,
                        result.context_type,
                        result.context_symbol,
                        json.dumps(result.metadata),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.error("save_validation_result_failed", error=str(e))

    def get_pending_validations(self, limit: int = 50) -> list[ValidationResult]:
        """Get pending validations awaiting human review."""
        conn_mgr = get_connection_manager()
        results = []
        try:
            with conn_mgr.connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM cross_validation_results
                    WHERE status = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (ValidationStatus.PENDING.value, limit),
                )
                for row in cursor.fetchall():
                    results.append(self._row_to_result(row))
        except Exception as e:
            logger.error("get_pending_validations_failed", error=str(e))
        return results

    def resolve_validation(
        self,
        validation_id: str,
        approved: bool,
        final_output: str | None = None,
        resolved_by: str = "human",
    ) -> ValidationResult | None:
        """Resolve a pending validation.

        Args:
            validation_id: ID of validation to resolve
            approved: Whether to approve
            final_output: Modified output (if any)
            resolved_by: Who resolved ("human" or "auto")

        Returns:
            Updated ValidationResult or None if not found
        """
        conn_mgr = get_connection_manager()
        try:
            with conn_mgr.connection() as conn:
                # Get current result
                cursor = conn.execute(
                    "SELECT * FROM cross_validation_results WHERE id = %s",
                    (validation_id,),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                result = self._row_to_result(row)

                # Determine new status
                if approved:
                    if final_output and final_output != result.generator_output:
                        new_status = ValidationStatus.MODIFIED
                    else:
                        new_status = ValidationStatus.APPROVED
                else:
                    new_status = ValidationStatus.REJECTED

                # Update
                now = datetime.now(UTC).isoformat()
                conn.execute(
                    """
                    UPDATE cross_validation_results
                    SET status = %s, resolved_at = %s, resolved_by = %s, final_output = %s
                    WHERE id = %s
                    """,
                    (
                        new_status.value,
                        now,
                        resolved_by,
                        final_output or result.generator_output,
                        validation_id,
                    ),
                )
                conn.commit()

                result.status = new_status
                result.resolved_at = now
                result.resolved_by = resolved_by
                result.final_output = final_output or result.generator_output

                logger.info(
                    "validation_resolved",
                    validation_id=validation_id,
                    status=new_status.value,
                    resolved_by=resolved_by,
                )

                return result

        except Exception as e:
            logger.error("resolve_validation_failed", error=str(e), validation_id=validation_id)
            return None

    def _row_to_result(self, row: Any) -> ValidationResult:
        """Convert database row (tuple) to ValidationResult.

        Column order from SELECT *:
        0: id, 1: created_at, 2: generator_provider, 3: generator_model,
        4: generator_output, 5: generator_confidence, 6: validator_provider,
        7: validator_model, 8: validator_review, 9: validator_approved,
        10: validator_confidence, 11: has_disagreement, 12: disagreement_reasons,
        13: disagreement_details, 14: status, 15: resolved_at, 16: resolved_by,
        17: final_output, 18: context_type, 19: context_symbol, 20: metadata
        """
        # Handle datetime objects - convert to ISO string if needed
        created_at = row[1]
        if hasattr(created_at, "isoformat"):
            created_at = created_at.isoformat()

        resolved_at = row[15]
        if resolved_at and hasattr(resolved_at, "isoformat"):
            resolved_at = resolved_at.isoformat()

        # Parse JSONB fields - PostgreSQL may return dict or string
        disagreement_reasons_raw = row[12]
        if isinstance(disagreement_reasons_raw, str):
            disagreement_reasons_raw = json.loads(disagreement_reasons_raw or "[]")
        elif disagreement_reasons_raw is None:
            disagreement_reasons_raw = []

        metadata_raw = row[20]
        if isinstance(metadata_raw, str):
            metadata_raw = json.loads(metadata_raw or "{}")
        elif metadata_raw is None:
            metadata_raw = {}

        return ValidationResult(
            id=row[0],
            created_at=created_at,
            generator_provider=row[2],
            generator_model=row[3] or "",
            generator_output=row[4],
            generator_confidence=row[5],
            validator_provider=row[6],
            validator_model=row[7] or "",
            validator_review=row[8],
            validator_approved=row[9],
            validator_confidence=row[10],
            has_disagreement=row[11],
            disagreement_reasons=[DisagreementReason(r) for r in disagreement_reasons_raw],
            disagreement_details=row[13],
            status=ValidationStatus(row[14]),
            resolved_at=resolved_at,
            resolved_by=row[16],
            final_output=row[17],
            context_type=row[18],
            context_symbol=row[19],
            metadata=metadata_raw,
        )
