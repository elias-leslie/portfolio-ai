"""Home automation center models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AutomationGuardrail(BaseModel):
    key: str
    label: str
    value: str
    detail: str


class AutomationRecentRun(BaseModel):
    id: str
    label: str
    status: str
    triggered_by: str
    started_at: str
    completed_at: str | None = None
    detail: str


class AutomationCenter(BaseModel):
    generated_at: str
    guardrails: list[AutomationGuardrail] = Field(default_factory=list)
    recent_runs: list[AutomationRecentRun] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
