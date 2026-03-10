"""Persisted symbol workflow models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SymbolWorkflowEvent(BaseModel):
    id: str
    symbol: str
    from_stage: str | None = None
    to_stage: str
    note: str
    created_by: str
    created_at: str


class SymbolWorkflow(BaseModel):
    symbol: str
    stage: str
    summary: str
    last_transition_at: str
    updated_by: str
    notes: str | None = None
    next_review_at: str | None = None
    available_transitions: list[str] = Field(default_factory=list)
    history: list[SymbolWorkflowEvent] = Field(default_factory=list)


class SymbolWorkflowTransitionRequest(BaseModel):
    stage: str
    note: str | None = None

