"""Portfolio API request/response models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.portfolio.account_linkage import HouseholdLinkageState
from app.portfolio.account_types import AccountType


# Request models
class AccountCreate(BaseModel):
    """Request model for creating an account."""

    name: str = Field(..., description="Account name")
    account_type: AccountType = Field(..., description="Account type")


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
    household_account_id: str | None = None
    household_linkage_state: HouseholdLinkageState = "unmapped"
    household_linkage_label: str = "Unmapped investment account"
    household_linkage_detail: str | None = None
    household_linkage_action_href: str | None = None
    household_linkage_candidate_count: int = 0
    household_linkage_candidate_ids: list[str] = Field(default_factory=list)
    cash_balance: float
    is_spouse: bool = False
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
    price_updated_at: str | None = None
    price_source: str | None = None
    source: str = "manual"
    source_account_id: str | None = None
    source_position_key: str | None = None
    raw_symbol: str | None = None
    security_kind: str | None = None
    average_purchase_price: float | None = None
    source_cost_basis: float | None = None
    source_market_value: float | None = None
    source_price: float | None = None
    source_currency: str | None = None
    source_updated_at: str | None = None


class PortfolioResponse(BaseModel):
    """Response model for portfolio with positions and current values."""

    positions: list[PositionResponse]
    cash_balance_total: float
    total_value: float
    total_cost_basis: float
    total_gain: float
    total_gain_pct: float
    effective_total_value: float | None = None
    household_total_value: float | None = None
    household_invested_total_value: float | None = None
    household_cash_reserve: float | None = None
    household_investment_accounts_count: int | None = None
    household_totals_trusted: bool = False
    account_control_status: str | None = None
    account_control_summary: str | None = None
    account_control_blocking_issue_count: int = 0
    quotes_updated_at: str | None = None
    quote_freshness_status: str | None = None
    quote_freshness_label: str | None = None


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
    method: str = "line_item"
    lookthrough_coverage_pct: float = 0.0


class ConcentrationResponse(BaseModel):
    """Response model for concentration metrics."""

    top_holding_pct: float
    top_3_pct: float
    top_10_pct: float
    herfindahl_index: float
    method: str = "line_item"
    top_holding_name: str | None = None
    vehicle_top_holding_pct: float = 0.0
    vehicle_top_3_pct: float = 0.0
    vehicle_top_10_pct: float = 0.0
    vehicle_herfindahl_index: float = 0.0
    vehicle_top_holding_name: str | None = None
    lookthrough_coverage_pct: float = 0.0


class AnalyticsResponse(BaseModel):
    """Response model for portfolio analytics."""

    portfolio_value: dict[str, float]
    cash_balance_total: float
    cash_inclusive_total_value: float
    effective_total_value: float | None = None
    household_total_value: float | None = None
    household_invested_total_value: float | None = None
    household_cash_reserve: float | None = None
    household_investment_accounts_count: int | None = None
    household_totals_trusted: bool = False
    account_control_status: str | None = None
    account_control_summary: str | None = None
    account_control_blocking_issue_count: int = 0
    quotes_updated_at: str | None = None
    quote_freshness_status: str | None = None
    quote_freshness_label: str | None = None
    portfolio_beta: float | None
    portfolio_volatility: float | None
    sharpe_ratio: float | None
    sector_exposure: dict[str, float]
    concentration: ConcentrationResponse
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
    routine_type: Literal["daily_operator", "daily_household_maintenance", "weekly_learning"] = Field(
        ..., description="Jenny routine to run"
    )


class JennyRunResponseModel(BaseModel):
    routine: JennyRoutineResponse
    dashboard: JennyDashboardResponse


class JennyPageContext(BaseModel):
    pathname: str = Field(..., description="Current app route, e.g. /money")
    title: str | None = Field(default=None, description="document.title at send time")
    search: str | None = Field(default=None, description="window.location.search at send time")


class JennyChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Free-form message to Jenny")
    session_id: str | None = Field(default=None, description="Existing Agent Hub session to continue")
    page_context: JennyPageContext | None = Field(default=None, description="Screen the user is viewing")


class JennyChatResolvedQuestionResponse(BaseModel):
    id: str
    field_name: str | None = None
    question: str
    answer_text: str | None = None


class JennyChatResponseModel(BaseModel):
    reply: str
    session_id: str
    resolved_questions: list[JennyChatResolvedQuestionResponse] = Field(default_factory=list)
    updated_fields: list[str] = Field(default_factory=list)
    referenced_symbols: list[str] = Field(default_factory=list)
