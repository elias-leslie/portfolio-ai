"""Pydantic models for market-prediction committee data.

These models define the storage and API contract for the Investing Prediction
surface. They are intentionally explicit about the v1 prediction universe and
scoring bundle: direction, expected move, and probability calibration.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr

PredictionDirection = Literal["bullish", "neutral", "bearish"]
ReviewState = Literal["live", "warmup", "degraded"]
SeatRecommendedAction = Literal["upweight", "downweight", "hold"]
ClusterRecommendedAction = Literal["upweight", "downweight", "hold"]
ClusterFreshness = Literal["fresh", "stale", "missing", "unknown"]
PredictionFreshnessState = Literal["fresh", "aging", "stale", "invalid", "degraded"]
PredictionResearchStatus = Literal["no_edge", "shadow", "usable"]
SUPPORTED_ADAPTIVE_SEAT_KEYS = ("cross_asset", "macro", "risk")
SUPPORTED_ADAPTIVE_CLUSTER_KEYS = (
    "market_regime",
    "sentiment",
    "options_positioning",
    "macro_calendar",
)


def normalize_market_prediction_seat_key(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def normalize_market_prediction_cluster_key(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


class PredictionSourceCluster(BaseModel):
    cluster: str = Field(..., description="Source cluster label")
    weight: float | None = Field(None, description="Optional contribution weight")
    freshness: str | None = Field(None, description="Freshness note for the cluster")
    as_of_date: str | None = Field(None, description="Source data date used for attribution freshness")
    note: str | None = Field(None, description="Optional plain-language attribution note")


class CommitteeSeatVote(BaseModel):
    seat_key: str
    agent_slug: str
    model_id: str | None = None
    provider: str | None = None
    symbol: str
    window_days: int = Field(..., ge=1)
    direction_label: PredictionDirection
    prob_up: float = Field(..., ge=0.0, le=1.0)
    expected_move_pct: float
    confidence_score: float | None = Field(None, ge=0.0, le=100.0)
    rationale_summary: str | None = None
    source_clusters: list[PredictionSourceCluster] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketPredictionCall(BaseModel):
    id: str | None = None
    symbol: str
    window_days: int = Field(..., ge=1)
    direction_label: PredictionDirection
    prob_up: float = Field(..., ge=0.0, le=1.0)
    expected_move_pct: float
    confidence_band_low_pct: float | None = None
    confidence_band_high_pct: float | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=100.0)
    committee_disagreement_score: float | None = Field(None, ge=0.0, le=1.0)
    rationale_summary: str | None = None
    top_source_clusters: list[PredictionSourceCluster] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketPredictionEvaluation(BaseModel):
    call_id: str
    evaluated_at: datetime
    base_close: float
    target_close: float
    realized_move_pct: float
    direction_hit: bool
    move_abs_error_pct: float = Field(..., ge=0.0)
    brier_score: float = Field(..., ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketPredictionVoteEvaluation(BaseModel):
    vote_id: int = Field(..., ge=1)
    evaluated_at: datetime
    seat_key: str
    symbol: str
    window_days: int = Field(..., ge=1)
    base_close: float
    target_close: float
    realized_move_pct: float
    direction_hit: bool
    move_abs_error_pct: float = Field(..., ge=0.0)
    brier_score: float = Field(..., ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketPredictionEvaluationCandidate(BaseModel):
    call: MarketPredictionCall
    base_date: date
    target_date: date


class MarketPredictionVoteEvaluationCandidate(BaseModel):
    vote_id: int = Field(..., ge=1)
    run_id: str
    symbol: str
    window_days: int = Field(..., ge=1)
    seat_key: str | None = None
    direction_label: PredictionDirection
    prob_up: float
    expected_move_pct: float
    base_date: date
    target_date: date
    confidence_score: float | None = Field(None, ge=0.0, le=100.0)


class MarketPredictionClusterEvaluationSample(BaseModel):
    call_id: str
    window_days: int = Field(..., ge=1)
    target_date: date
    active_cluster_keys: list[str] = Field(default_factory=list)
    direction_hit: bool
    move_abs_error_pct: float = Field(..., ge=0.0)
    brier_score: float = Field(..., ge=0.0)


class MarketPredictionClusterScorecardRow(BaseModel):
    cluster: str
    prior_weight: float = Field(..., ge=0.0, le=1.0)
    effective_weight: float = Field(..., ge=0.0, le=1.0)
    sample_size: int = Field(default=0, ge=0)
    direction_hit_rate: float | None = Field(None, ge=0.0, le=1.0)
    move_mae_pct: float | None = Field(None, ge=0.0)
    brier_score: float | None = Field(None, ge=0.0)
    skill_score: float | None = Field(None, ge=0.0, le=1.0)
    freshness: ClusterFreshness = "unknown"
    recommended_action: ClusterRecommendedAction = "hold"


class MarketPredictionResolvedClusterWeight(BaseModel):
    cluster: str
    prior_weight: float = Field(..., ge=0.0, le=1.0)
    effective_weight: float = Field(..., ge=0.0, le=1.0)
    sample_size: int = Field(default=0, ge=0)
    skill_score: float | None = Field(None, ge=0.0, le=1.0)
    freshness: ClusterFreshness = "unknown"


class MarketPredictionClusterReview(BaseModel):
    id: str
    generated_at: datetime
    as_of_ts: datetime
    window_days: int = Field(..., ge=1)
    review_state: ReviewState
    cluster_scorecards: list[MarketPredictionClusterScorecardRow] = Field(default_factory=list)
    review_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketPredictionSeatScorecardRow(BaseModel):
    seat_key: str
    prior_weight: float = Field(..., ge=0.0, le=1.0)
    effective_weight: float = Field(..., ge=0.0, le=1.0)
    sample_size: int = Field(default=0, ge=0)
    direction_hit_rate: float | None = Field(None, ge=0.0, le=1.0)
    move_mae_pct: float | None = Field(None, ge=0.0)
    brier_score: float | None = Field(None, ge=0.0)
    skill_score: float | None = Field(None, ge=0.0, le=1.0)
    recommended_action: SeatRecommendedAction = "hold"


class MarketPredictionResolvedSeatWeight(BaseModel):
    seat_key: str
    prior_weight: float = Field(..., ge=0.0, le=1.0)
    effective_weight: float = Field(..., ge=0.0, le=1.0)
    sample_size: int = Field(default=0, ge=0)
    skill_score: float | None = Field(None, ge=0.0, le=1.0)


class MarketPredictionSeatReview(BaseModel):
    id: str
    generated_at: datetime
    as_of_ts: datetime
    window_days: int = Field(..., ge=1)
    review_state: ReviewState
    seat_scorecards: list[MarketPredictionSeatScorecardRow] = Field(default_factory=list)
    review_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketPredictionSeatReviewResponse(BaseModel):
    as_of_ts: datetime
    window_days: int = Field(..., ge=1)
    review_state: ReviewState
    seat_scorecards: list[MarketPredictionSeatScorecardRow] = Field(default_factory=list)
    review_summary: dict[str, Any] = Field(default_factory=dict)


class MarketPredictionRun(BaseModel):
    id: str
    generated_at: datetime
    as_of_ts: datetime
    window_days: int = Field(..., ge=1)
    base_date: date
    target_date: date
    target_universe: list[str] = Field(default_factory=list)
    lead_symbol: str
    lead_direction: PredictionDirection
    lead_prob_up: float | None = Field(None, ge=0.0, le=1.0)
    lead_expected_move_pct: float | None = None
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    committee_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MarketPredictionScorecard(BaseModel):
    direction_hit_rate: float | None = Field(None, ge=0.0, le=1.0)
    move_mae_pct: float | None = Field(None, ge=0.0)
    brier_score: float | None = Field(None, ge=0.0)
    sample_size: int = Field(default=0, ge=0)


class MarketPredictionDataHealthRow(BaseModel):
    label: str
    status: str
    detail: str | None = None
    as_of_date: str | None = None


class MarketPredictionWalkForwardCandidateSummary(BaseModel):
    candidate_id: str | None = None
    candidate_label: str | None = None
    candidate_feature_kind: Literal["absolute", "relative_to_target"] = "absolute"
    benchmark_symbol: str | None = None
    status: Literal["pass", "fail", "insufficient"] = "insufficient"
    status_reason: str | None = None
    sample_count: int = Field(default=0, ge=0)
    hit_rate: float | None = Field(None, ge=0.0, le=1.0)
    hit_rate_lcb: float | None = Field(None, ge=0.0, le=1.0)
    brier_improvement_pct: float | None = None
    move_mae_pct: float | None = Field(None, ge=0.0)
    baseline_move_mae_pct: float | None = Field(None, ge=0.0)
    after_cost_edge_pct: float | None = None
    passed: bool = False


class MarketPredictionWalkForwardScorecard(BaseModel):
    status: Literal["pass", "fail", "insufficient"] = "insufficient"
    status_reason: str
    candidate_id: str | None = None
    candidate_label: str | None = None
    candidate_feature_kind: Literal["absolute", "relative_to_target"] = "absolute"
    benchmark_symbol: str | None = None
    driver_labels: list[str] = Field(default_factory=list)
    tested_candidates: int = Field(default=0, ge=0)
    sample_count: int = Field(default=0, ge=0)
    min_sample_count: int = Field(default=100, ge=1)
    trade_count: int = Field(default=0, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    train_window_days: int = Field(default=504, ge=1)
    stride_days: int = Field(default=1, ge=1)
    hit_rate: float | None = Field(None, ge=0.0, le=1.0)
    hit_rate_lcb: float | None = Field(None, ge=0.0, le=1.0)
    brier_score: float | None = Field(None, ge=0.0)
    baseline_brier_score: float | None = Field(None, ge=0.0)
    brier_improvement_pct: float | None = None
    move_mae_pct: float | None = Field(None, ge=0.0)
    baseline_move_mae_pct: float | None = Field(None, ge=0.0)
    max_move_mae_pct: float | None = Field(None, ge=0.0)
    after_cost_edge_pct: float | None = None
    cost_model: str = "next_open_to_target_close_5bps"
    passed: bool = False
    top_candidates: list[MarketPredictionWalkForwardCandidateSummary] = Field(default_factory=list)


class MarketPredictionResearchScoreboard(BaseModel):
    status: PredictionResearchStatus = "no_edge"
    status_reason: str
    sample_count: int = Field(default=0, ge=0)
    min_sample_count: int = Field(default=100, ge=1)
    sufficient_samples: bool = False
    hit_rate: float | None = Field(None, ge=0.0, le=1.0)
    move_mae_pct: float | None = Field(None, ge=0.0)
    brier_score: float | None = Field(None, ge=0.0)
    baseline_hit_rate: float | None = Field(None, ge=0.0, le=1.0)
    baseline_brier_score: float | None = Field(None, ge=0.0)
    beats_baseline: bool = False
    hit_rate_lcb: float | None = Field(None, ge=0.0, le=1.0)
    hit_rate_confident: bool = False
    max_move_mae_pct: float | None = Field(None, ge=0.0)
    move_error_ok: bool = False
    after_cost_edge_pct: float | None = None
    cost_model: str = "not_tracked"
    model_id: str | None = None
    model_version: str | None = None
    referee: str = "fixed_scorecard_v1"
    experiment_loop: str = "shadow_only"
    walk_forward: MarketPredictionWalkForwardScorecard | None = None
    data_health: list[MarketPredictionDataHealthRow] = Field(default_factory=list)


class PredictionFreshnessCluster(BaseModel):
    cluster: str
    freshness: ClusterFreshness = "unknown"
    as_of_date: str | None = None
    detail: str | None = None


class PredictionFreshnessSummary(BaseModel):
    state: PredictionFreshnessState
    summary: str
    invalidated: bool = False
    generated_age_seconds: int = Field(..., ge=0)
    evaluated_age_seconds: int | None = Field(None, ge=0)
    market_status: str
    market_date: date
    refresh_after_seconds: int = Field(..., ge=30)
    checked_at: datetime
    reason_codes: list[str] = Field(default_factory=list)
    critical_clusters: list[PredictionFreshnessCluster] = Field(default_factory=list)


class MarketPredictionCommitteeResponse(BaseModel):
    _storage_metadata: Any = PrivateAttr(default_factory=dict)

    as_of_ts: datetime
    generated_at: datetime
    window_days: int = Field(..., ge=1)
    base_date: date
    target_date: date
    target_universe: list[str] = Field(default_factory=list)
    lead_call: MarketPredictionCall
    calls: list[MarketPredictionCall] = Field(default_factory=list)
    votes: list[CommitteeSeatVote] = Field(default_factory=list)
    scorecard: MarketPredictionScorecard | None = None
    research_scoreboard: MarketPredictionResearchScoreboard | None = None
    committee_summary: dict[str, Any] = Field(default_factory=dict)
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    last_evaluated_at: datetime | None = None
    freshness_summary: PredictionFreshnessSummary | None = None


class MarketPredictionHistoryResponse(BaseModel):
    symbol: str
    window_days: int = Field(..., ge=1)
    items: list[MarketPredictionCall] = Field(default_factory=list)
