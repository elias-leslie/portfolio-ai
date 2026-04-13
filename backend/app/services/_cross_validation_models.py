"""Data models and prompt slugs for cross-validation service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypedDict

from pydantic import BaseModel, Field


class ValidationStatus(StrEnum):
    """Status of a cross-validation result."""

    PENDING = "pending"  # Awaiting human review
    APPROVED = "approved"  # Human approved
    REJECTED = "rejected"  # Human rejected
    AUTO_APPLIED = "auto_applied"  # Applied automatically (full auto mode)
    MODIFIED = "modified"  # Human modified before applying


class DisagreementReason(StrEnum):
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


CROSS_VALIDATION_REVIEW_PROMPT = "portfolio-cross-validation-review-template"
CROSS_VALIDATION_REVIEW_SYSTEM_PROMPT = "portfolio-cross-validation-review-system"
