"""Thesis System data models.

Investment thesis models for LLM-generated investment rationale with dual-agent validation.
Supports versioning, invalidation tracking, and cross-validation between Claude and Gemini.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ThesisStatus(StrEnum):
    """Status of an investment thesis."""

    ACTIVE = "active"
    INVALIDATED = "invalidated"
    FLAGGED = "flagged_for_review"


class ThesisAction(StrEnum):
    """Recommended action for the thesis."""

    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"


class ThesisReason(BaseModel):
    """Individual reason supporting the thesis with confidence level."""

    reason: str = Field(..., description="Bullish or bearish reason")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence level (0.0 to 1.0)")


class ThesisCatalyst(BaseModel):
    """Upcoming catalyst event that could impact the thesis."""

    catalyst: str = Field(..., description="Description of the catalyst event")
    expected_date: str | None = Field(None, description="Expected date of catalyst (ISO 8601)")
    impact: Literal["positive", "negative", "neutral"] = Field(
        ..., description="Expected impact direction"
    )


class ThesisRisk(BaseModel):
    """Risk factor with severity assessment."""

    risk: str = Field(..., description="Description of the risk")
    severity: Literal["high", "medium", "low"] = Field(..., description="Risk severity level")
    mitigation: str | None = Field(None, description="Potential mitigation strategy")


class ThesisValueDrivers(BaseModel):
    """AI-derived value analysis components."""

    market_size: str | None = Field(None, description="Total addressable market analysis")
    company_position: str | None = Field(None, description="Company's competitive position")
    upside_potential: str | None = Field(None, description="Potential upside explanation")
    competitive_moat: str | None = Field(None, description="Sustainable competitive advantages")


class ThesisValidation(BaseModel):
    """LLM validation result from Claude or Gemini."""

    provider: str = Field(..., description="LLM provider (claude or gemini)")
    approved: bool = Field(..., description="Whether the thesis is approved")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Validator confidence (0.0 to 1.0)")
    review_summary: str = Field(..., description="Summary of the validation review")
    issues: list[str] = Field(default_factory=list, description="List of identified issues")


class Thesis(BaseModel):
    """Main investment thesis model with dual-agent validation."""

    id: str = Field(..., description="Unique thesis ID")
    symbol: str = Field(..., description="Stock symbol")
    version: int = Field(..., ge=1, description="Thesis version number")
    status: ThesisStatus = Field(..., description="Current thesis status")
    action: ThesisAction = Field(..., description="Recommended action (BUY, HOLD, SELL)")

    # Core thesis components
    core_reasons: list[ThesisReason] = Field(
        default_factory=list, description="Core bullish/bearish reasons"
    )
    key_catalysts: list[ThesisCatalyst] = Field(
        default_factory=list, description="Upcoming catalyst events"
    )
    risks: list[ThesisRisk] = Field(default_factory=list, description="Key risk factors")
    value_drivers: ThesisValueDrivers | None = Field(None, description="Value analysis components")

    # Expectations
    expected_return_pct: float | None = Field(
        None, description="Expected return percentage (annualized)"
    )
    expected_timeframe_days: int | None = Field(
        None, description="Expected timeframe in days for return"
    )

    # Cross-validation
    claude_validation: ThesisValidation | None = Field(
        None, description="Claude's validation result"
    )
    gemini_validation: ThesisValidation | None = Field(
        None, description="Gemini's validation result"
    )
    cross_validation_score: float | None = Field(
        None, ge=0.0, le=1.0, description="Cross-validation agreement score (0.0 to 1.0)"
    )

    # Invalidation tracking
    invalidation_reason: str | None = Field(None, description="Reason for invalidation")
    invalidated_at: str | None = Field(None, description="Invalidation timestamp (ISO 8601)")

    # Timestamps
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")
    updated_at: str = Field(..., description="Last update timestamp (ISO 8601)")


class ThesisVersion(BaseModel):
    """Version history entry for thesis changes."""

    id: str = Field(..., description="Unique version history ID")
    thesis_id: str = Field(..., description="Parent thesis ID")
    version: int = Field(..., ge=1, description="Version number")
    snapshot: dict[str, Any] = Field(..., description="Full thesis state at this version")
    change_reason: str = Field(..., description="Reason for version change")
    created_at: str = Field(..., description="Version creation timestamp (ISO 8601)")


class ThesisDecisionEligibility(BaseModel):
    """Whether a thesis can be used as current decision evidence."""

    eligible: bool = Field(..., description="True when thesis can be shown as current evidence")
    status: Literal["eligible", "review_required", "invalidated", "unavailable"] = Field(
        ..., description="Decision eligibility state"
    )
    reasons: list[str] = Field(
        default_factory=list, description="Human-readable reasons blocking clean use"
    )
    age_hours: float | None = Field(None, description="Age of the thesis in hours")
    evaluated_at: str | None = Field(None, description="Eligibility evaluation timestamp")


class ThesisGenerateRequest(BaseModel):
    """API request model for thesis generation."""

    force_regenerate: bool = Field(
        False, description="Force regeneration even if recent thesis exists"
    )


class ThesisResponse(BaseModel):
    """API response model for thesis retrieval."""

    thesis: Thesis | None = Field(None, description="Current thesis (null if none exists)")
    versions: list[ThesisVersion] = Field(
        default_factory=list, description="Version history (newest first)"
    )
    version_count: int = Field(..., ge=0, description="Total number of versions")
    decision_eligibility: ThesisDecisionEligibility = Field(
        default_factory=lambda: ThesisDecisionEligibility(
            eligible=True,
            status="eligible",
            reasons=[],
        ),
        description="Computed current-decision eligibility for the thesis",
    )
