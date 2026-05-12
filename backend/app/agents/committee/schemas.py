"""Typed payloads for committee stages, events, and outputs.

These mirror the SSE event schema in plans/sunny-puzzling-sprout.md.
Stage outputs are pydantic models so callers get validated structure;
Agent Hub raw responses are coerced via ``model_validate`` at the
stages.py boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

Stage = Literal[
    "analysts",
    "researchers",
    "trader",
    "ips",
    "risk",
    "pm",
    "feedback",
    "system",
]

Side = Literal["bull", "bear", "neutral"]
Action = Literal["buy", "sell", "trim", "add", "hold"]
RiskVote = Literal["approve", "downgrade", "reject"]
FeedbackScore = Literal["weak", "mistaken", "partial", "decisive"]


class Evidence(BaseModel):
    """One claim entry on the evidence ledger."""

    claim: str
    source: str | None = None
    side: Side
    weight: float = 1.0


class AnalystOutput(BaseModel):
    """Output from any of the four analyst slugs."""

    agent_slug: str
    role: Literal["analyst"] = "analyst"
    content_md: str
    score: float = Field(ge=-1.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    tokens: int = 0
    latency_ms: int = 0


class ResearcherOutput(BaseModel):
    """Output from a bull or bear researcher in one debate round."""

    agent_slug: str
    role: Literal["bull", "bear"]
    argument_md: str
    rebuttals_md: str = ""
    score: float = Field(ge=0.0, le=1.0)
    evidence: list[Evidence] = Field(default_factory=list)
    tokens: int = 0
    latency_ms: int = 0


class DebateRound(BaseModel):
    """One full bull/bear exchange."""

    round_idx: int
    bull: ResearcherOutput
    bear: ResearcherOutput


class TradeProposal(BaseModel):
    """Trader's synthesis output, pre-IPS, pre-risk-vote."""

    action: Action
    qty_pct: float = Field(ge=0.0, le=1.0)
    entry_price: float
    stop_price: float | None = None
    horizon: str
    rationale_md: str
    signers: list[str] = Field(default_factory=list)
    tokens: int = 0
    latency_ms: int = 0


class IpsCheck(BaseModel):
    """One IPS check result."""

    name: Literal["concentration", "tax_bill", "sector_exposure", "wash_sale"]
    passed: bool
    severity: Literal["block", "warn", "info"]
    detail: str
    value: float | None = None
    threshold: float | None = None


class IpsResult(BaseModel):
    """Aggregate IPS outcome."""

    checks: list[IpsCheck]
    all_passed: bool


class RiskObjection(BaseModel):
    claim: str
    severity: Literal["low", "medium", "high"]


class RiskVoteOutput(BaseModel):
    """Output from any of the three risk voters."""

    agent_slug: str
    vote: RiskVote
    score: float = Field(ge=-1.0, le=1.0)
    narrative_md: str
    objections: list[RiskObjection] = Field(default_factory=list)
    tokens: int = 0
    latency_ms: int = 0


class PmDecision(BaseModel):
    """Portfolio manager's final decision."""

    action: Action
    qty_pct: float = Field(ge=0.0, le=1.0)
    qty: float = 0.0
    confidence: float = Field(ge=0.0, le=1.0)
    horizon: str
    signers: list[str] = Field(default_factory=list)
    rationale_md: str
    rebuttal_md: str | None = None
    tokens: int = 0
    latency_ms: int = 0


class FeedbackAgentResponse(BaseModel):
    """Per-agent response during a feedback round."""

    agent_slug: str
    score: FeedbackScore
    revised_stance: Side
    rebuttal_or_concession: str
    prior_stance: Side


class CommitteeEvent(BaseModel):
    """Single SSE event emitted by the runner."""

    seq: int
    ts: datetime
    run_id: str
    type: str
    stage: Stage | None = None
    agent_slug: str | None = None
    role: str | None = None
    content: dict[str, Any] = Field(default_factory=dict)
    score: float | None = None
    tokens: int | None = None
    latency_ms: int | None = None


class PastDecisionEntry(BaseModel):
    """One prior decision injected into the PM context."""

    run_id: str
    started_at: datetime
    action: Action
    qty_pct: float | None = None
    realized_pnl: float | None = None
    horizon: str | None = None
