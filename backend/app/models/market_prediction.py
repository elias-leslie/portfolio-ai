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
    committee_summary: dict[str, Any] = Field(default_factory=dict)
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    last_evaluated_at: datetime | None = None


class MarketPredictionHistoryResponse(BaseModel):
    symbol: str
    window_days: int = Field(..., ge=1)
    items: list[MarketPredictionCall] = Field(default_factory=list)
