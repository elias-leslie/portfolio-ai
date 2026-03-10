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
    metadata: dict[str, object] = Field(default_factory=dict)


class SymbolWorkflowPositionContext(BaseModel):
    shares: float
    cost_basis: float
    market_value: float | None = None
    gain_pct: float | None = None
    weight_pct: float | None = None


class SymbolWorkflowOutcomeSnapshot(BaseModel):
    action: str
    stage: str
    note: str
    created_at: str
    jenny_verdict: str | None = None
    management_action: str | None = None
    position: SymbolWorkflowPositionContext | None = None


class SymbolWorkflow(BaseModel):
    symbol: str
    stage: str
    summary: str
    last_transition_at: str
    updated_by: str
    notes: str | None = None
    next_review_at: str | None = None
    available_transitions: list[str] = Field(default_factory=list)
    position: SymbolWorkflowPositionContext | None = None
    latest_outcome: SymbolWorkflowOutcomeSnapshot | None = None
    history: list[SymbolWorkflowEvent] = Field(default_factory=list)


class SymbolWorkflowTransitionRequest(BaseModel):
    stage: str
    note: str | None = None


class SymbolWorkflowOutcomeRequest(BaseModel):
    action: str
    note: str | None = None
    jenny_verdict: str | None = None
    management_action: str | None = None
