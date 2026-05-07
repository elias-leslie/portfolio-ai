"""Jenny operator models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

JennySeverity = Literal["critical", "warning", "info"]
JennyVerdict = Literal["buy", "hold", "review", "trim", "exit", "avoid"]
JennyRoutineType = Literal[
    "daily_operator",
    "daily_household_maintenance",
    "weekly_learning",
    "manual_refresh",
]


class JennyRoutine(BaseModel):
    id: str
    routine_type: JennyRoutineType | str
    status: str
    triggered_by: str
    summary: str | None = None
    agents_used: list[str] = Field(default_factory=list)
    symbols_scanned: int = 0
    notifications_created: int = 0
    started_at: str
    completed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JennyAgentEvaluation(BaseModel):
    id: str
    routine_id: str
    symbol: str
    agent_name: str
    provider: str | None = None
    model: str | None = None
    verdict: JennyVerdict | str
    confidence: float | None = None
    rationale: str
    recommendation: str | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    thesis_id: str | None = None
    agent_run_id: str | None = None
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class JennySymbolReview(BaseModel):
    symbol: str
    final_verdict: JennyVerdict | str
    average_confidence: float | None = None
    thesis_status: str | None = None
    thesis_action: str | None = None
    management_action: str | None = None
    management_detail: str | None = None
    position_gain_pct: float | None = None
    position_weight_pct: float | None = None
    reasons: list[str] = Field(default_factory=list)
    evaluations: list[JennyAgentEvaluation] = Field(default_factory=list)


class JennyNotification(BaseModel):
    id: str
    routine_id: str | None = None
    symbol: str | None = None
    category: str
    severity: JennySeverity | str
    status: str
    title: str
    detail: str
    recommendation: str | None = None
    created_at: str
    acknowledged_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JennyTradeReview(BaseModel):
    id: str
    symbol: str
    thesis_id: str | None = None
    idea_id: str | None = None
    review_source: str
    outcome_label: str
    return_pct: float | None = None
    lesson: str
    what_worked: str | None = None
    what_failed: str | None = None
    next_time: str | None = None
    created_at: str
    updated_at: str
    agent_consensus: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JennyAgentScorecard(BaseModel):
    agent_name: str
    total_evaluations: int = 0
    completed_reviews: int = 0
    positive_verdicts: int = 0
    win_rate: float | None = None
    avg_return_pct: float | None = None
    agreement_rate: float | None = None
    calibration_score: float | None = None
    entry_quality_score: float | None = None
    risk_judgment_score: float | None = None
    exit_timing_score: float | None = None
    alert_discipline_score: float | None = None
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    last_evaluation_at: str | None = None
    updated_at: str


class JennyPredictionReviewChange(BaseModel):
    kind: str = "seat"
    key: str
    prior_weight: float
    effective_weight: float


class JennyPredictionReviewSeatWeight(BaseModel):
    seat_key: str
    prior_weight: float
    effective_weight: float
    sample_size: int = 0
    recommended_action: str = "hold"


class JennyPredictionReviewClusterWeight(BaseModel):
    cluster: str
    prior_weight: float
    effective_weight: float
    sample_size: int = 0
    freshness: str = "unknown"
    gate_state: str = "off"
    recommended_action: str = "hold"


class JennyPredictionReviewSummary(BaseModel):
    window_days: int
    review_state: str
    generated_at: str
    as_of_ts: str
    seat_weights: list[JennyPredictionReviewSeatWeight] = Field(default_factory=list)
    cluster_weights: list[JennyPredictionReviewClusterWeight] = Field(default_factory=list)
    drift_callouts: list[str] = Field(default_factory=list)
    gap_callouts: list[str] = Field(default_factory=list)
    agent_actions: list[str] = Field(default_factory=list)
    top_upweighted: list[JennyPredictionReviewChange] = Field(default_factory=list)
    top_downweighted: list[JennyPredictionReviewChange] = Field(default_factory=list)


class JennyDashboard(BaseModel):
    routines: list[JennyRoutine] = Field(default_factory=list)
    notifications: list[JennyNotification] = Field(default_factory=list)
    symbol_reviews: list[JennySymbolReview] = Field(default_factory=list)
    trade_reviews: list[JennyTradeReview] = Field(default_factory=list)
    scorecards: list[JennyAgentScorecard] = Field(default_factory=list)
    prediction_review_summary: JennyPredictionReviewSummary | None = None


class JennyRunResponse(BaseModel):
    routine: JennyRoutine
    dashboard: JennyDashboard
