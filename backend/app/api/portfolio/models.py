"""Portfolio API request/response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# Request models
class AccountCreate(BaseModel):
    """Request model for creating an account."""

    name: str = Field(..., description="Account name")
    account_type: Literal["IRA", "Taxable", "401k", "Roth", "HSA", "paper"] = Field(
        ..., description="Account type"
    )


class PositionCreate(BaseModel):
    """Request model for creating/updating a position."""

    account_id: str = Field(..., description="Account ID")
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    shares: float = Field(..., description="Number of shares", gt=0)
    cost_basis: float = Field(..., description="Cost basis per share", gt=0)
    position_type: Literal["long", "short"] = Field(default="long", description="Position type")
    strategy_id: str | None = Field(
        default=None, description="Optional strategy ID to link this position to"
    )


# Response models
class AccountResponse(BaseModel):
    """Response model for account."""

    id: str
    name: str
    account_type: str
    cash_balance: float
    created_at: str
    updated_at: str


class PositionResponse(BaseModel):
    """Response model for position."""

    id: str
    account_id: str
    symbol: str
    shares: float
    cost_basis: float
    position_type: str
    strategy_id: str | None = None
    strategy_name: str | None = None
    created_at: str
    updated_at: str
    current_price: float | None = None
    current_value: float | None = None
    gain: float | None = None
    gain_pct: float | None = None


class PortfolioResponse(BaseModel):
    """Response model for portfolio with positions and current values."""

    positions: list[PositionResponse]
    cash_balance_total: float
    total_value: float
    total_cost_basis: float
    total_gain: float
    total_gain_pct: float


class PositionPerformanceResponse(BaseModel):
    """Response model for position performance."""

    symbol: str
    gain_pct: float
    gain_amount: float
    current_value: float
    weight_pct: float


class RiskProfileResponse(BaseModel):
    """Response model for risk profile."""

    level: str
    score: float
    factors: dict[str, str]


class DiversificationScoreResponse(BaseModel):
    """Response model for diversification score."""

    score: float
    level: str
    num_holdings: int
    num_sectors: int


class AnalyticsResponse(BaseModel):
    """Response model for portfolio analytics."""

    portfolio_value: dict[str, float]
    cash_balance_total: float
    cash_inclusive_total_value: float
    portfolio_beta: float | None
    portfolio_volatility: float | None
    sharpe_ratio: float | None
    sector_exposure: dict[str, float]
    concentration: dict[str, float]
    risk_profile: RiskProfileResponse | None
    diversification_score: DiversificationScoreResponse | None
    top_performers: list[PositionPerformanceResponse]
    bottom_performers: list[PositionPerformanceResponse]
    num_positions: int
    num_symbols: int


class JennyRoutineResponse(BaseModel):
    id: str
    routine_type: str
    status: str
    triggered_by: str
    summary: str | None
    agents_used: list[str]
    symbols_scanned: int
    notifications_created: int
    started_at: str
    completed_at: str | None
    metadata: dict[str, object]


class JennyEvaluationResponse(BaseModel):
    id: str
    routine_id: str
    symbol: str
    agent_name: str
    provider: str | None
    model: str | None
    verdict: str
    confidence: float | None
    rationale: str
    recommendation: str | None
    strengths: list[str]
    weaknesses: list[str]
    thesis_id: str | None
    agent_run_id: str | None
    created_at: str
    metadata: dict[str, object]


class JennySymbolReviewResponse(BaseModel):
    symbol: str
    final_verdict: str
    average_confidence: float | None
    thesis_status: str | None
    thesis_action: str | None
    management_action: str | None = None
    management_detail: str | None = None
    position_gain_pct: float | None = None
    position_weight_pct: float | None = None
    reasons: list[str]
    evaluations: list[JennyEvaluationResponse]


class JennyNotificationResponse(BaseModel):
    id: str
    routine_id: str | None
    symbol: str | None
    category: str
    severity: str
    status: str
    title: str
    detail: str
    recommendation: str | None
    created_at: str
    acknowledged_at: str | None
    metadata: dict[str, object]


class JennyTradeReviewResponse(BaseModel):
    id: str
    symbol: str
    thesis_id: str | None
    idea_id: str | None
    review_source: str
    outcome_label: str
    return_pct: float | None
    lesson: str
    what_worked: str | None
    what_failed: str | None
    next_time: str | None
    created_at: str
    updated_at: str
    agent_consensus: dict[str, object]
    metadata: dict[str, object]


class JennyAgentScorecardResponse(BaseModel):
    agent_name: str
    total_evaluations: int
    completed_reviews: int
    positive_verdicts: int
    win_rate: float | None
    avg_return_pct: float | None
    agreement_rate: float | None
    calibration_score: float | None
    entry_quality_score: float | None = None
    risk_judgment_score: float | None = None
    exit_timing_score: float | None = None
    alert_discipline_score: float | None = None
    strengths: list[str]
    weaknesses: list[str]
    last_evaluation_at: str | None
    updated_at: str


class JennyDashboardResponse(BaseModel):
    routines: list[JennyRoutineResponse]
    notifications: list[JennyNotificationResponse]
    symbol_reviews: list[JennySymbolReviewResponse]
    trade_reviews: list[JennyTradeReviewResponse]
    scorecards: list[JennyAgentScorecardResponse]


class JennyRunRequest(BaseModel):
    routine_type: Literal["daily_operator", "weekly_learning"] = Field(
        ..., description="Jenny routine to run"
    )


class JennyRunResponseModel(BaseModel):
    routine: JennyRoutineResponse
    dashboard: JennyDashboardResponse
