"""Pydantic models for market-prediction committee data.

These models define the storage and API contract for the Investing Prediction
surface. They are intentionally explicit about the v1 prediction universe and
scoring bundle: direction, expected move, and probability calibration.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

PredictionDirection = Literal["bullish", "neutral", "bearish"]


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


class MarketPredictionEvaluationCandidate(BaseModel):
    call: MarketPredictionCall
    base_date: date
    target_date: date


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
