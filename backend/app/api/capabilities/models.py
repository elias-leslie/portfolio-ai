"""Pydantic models for capabilities API.

This module consolidates all request and response models used across
capabilities routers.
"""

from __future__ import annotations

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
    dependencies: DependenciesDict = Field(default_factory=dict)


# Insights Router Models


class InsightReviewRequest(BaseModel):
    """Request for reviewing an insight."""

    status: str = Field(description="New review status: confirmed, dismissed, pending")
    annotation: str | None = Field(default=None, description="Optional review annotation")


class InsightsListResponse(BaseModel):
    """Response for paginated insights list."""

    total: int
    insights: list[InsightDict]


# Notes Router Models


class NoteCreateRequest(BaseModel):
    """Request for creating a capability note."""

    capability_type: str = Field(description="Capability type: db, celery, api")
    capability_id: str = Field(description="Capability identifier")
    content: str = Field(description="Note content")
    category: str | None = Field(default=None, description="Note category")


class NotesListResponse(BaseModel):
    """Response for notes list."""

    total: int
    notes: list[NoteDict]


class NoteCreateResponse(BaseModel):
    """Response for note creation."""

    note_id: int
    message: str
