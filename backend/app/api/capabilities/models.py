"""Pydantic models for capabilities API.

This module consolidates all request and response models used across
capabilities routers.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..types import CapabilityDict, DependenciesDict, InsightDict, NoteDict

# Capabilities Router Models


class ScanTriggerResponse(BaseModel):
    """Response for manual scan trigger."""

    task_id: str
    status: str = "queued"
    message: str


class CapabilitiesListResponse(BaseModel):
    """Response for paginated capabilities list."""

    total: int
    capabilities: list[CapabilityDict]


class CapabilityDetailResponse(BaseModel):
    """Response for single capability with related data."""

    capability: CapabilityDict
    insights: list[InsightDict] = Field(default_factory=list)
    notes: list[NoteDict] = Field(default_factory=list)
    dependencies: DependenciesDict = Field(default_factory=dict)  # type: ignore[assignment]


# Insights Router Models


class InsightCreateRequest(BaseModel):
    """Request for creating a capability insight."""

    capability_type: str = Field(description="Capability type: db, celery, api")
    capability_id: int | None = Field(default=None, description="Capability ID (optional)")
    table_name: str | None = Field(default=None, description="Table name for quick reference")
    insight_type: str = Field(
        description="Insight type: broken_dependency, missing_data, data_quality, "
        "missing_capability, performance"
    )
    severity: str = Field(description="Severity: low, medium, high, critical")
    finding: str = Field(description="Concise description of the finding")
    expected_behavior: str | None = Field(default=None, description="What should happen")
    actual_behavior: str | None = Field(default=None, description="What's actually happening")
    impact: str | None = Field(default=None, description="Why this matters")
    suggested_fix: str | None = Field(default=None, description="Specific action to take")
    reference_data: dict[str, Any] | None = Field(
        default=None, description="Related files, tables, etc."
    )
    ai_model: str | None = Field(default=None, description="AI model that generated insight")
    ai_confidence: float | None = Field(
        default=None, ge=0.0, le=1.0, description="AI confidence 0.0-1.0"
    )


class InsightCreateResponse(BaseModel):
    """Response for insight creation."""

    id: int
    message: str


class InsightReviewRequest(BaseModel):
    """Request for reviewing an insight."""

    status: str = Field(description="New review status: confirmed, dismissed, pending")
    status_reason: str | None = Field(default=None, description="Reason for status change")
    reviewed_by: str = Field(default="human", description="Reviewer identifier")


class InsightsListResponse(BaseModel):
    """Response for paginated insights list."""

    total: int
    insights: list[InsightDict]


# Notes Router Models


class NoteCreateRequest(BaseModel):
    """Request for creating a capability note."""

    capability_type: str = Field(description="Capability type: db, celery, api")
    capability_id: int | None = Field(default=None, description="Capability ID (optional)")
    insight_id: int | None = Field(default=None, description="Related insight ID (optional)")
    note_type: str = Field(
        description="Note type: observation, recommendation, question, decision, reference"
    )
    note: str = Field(description="Note content")


class NotesListResponse(BaseModel):
    """Response for notes list."""

    total: int
    notes: list[NoteDict]


class NoteCreateResponse(BaseModel):
    """Response for note creation."""

    id: int
    message: str
