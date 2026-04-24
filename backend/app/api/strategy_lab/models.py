from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ActionLiteral = Literal["buy_now", "buy_in_stages", "hold", "wait"]
StrategyTemplateLiteral = Literal["pullback_accumulator", "breakout_confirmation"]
BacktestStatusLiteral = Literal["ready", "insufficient_history", "no_trades", "quote_unavailable"]
StrategyLabUnavailableReason = Literal["insufficient_history", "evaluation_error"]


class StrategyLabPrimaryAccountTarget(BaseModel):
    account_id: str
    account_name: str
    account_type: str
    cash_balance: float
    held_market_value: float | None = None


class StrategyLabTicket(BaseModel):
    account_id: str
    account_name: str
    action: ActionLiteral
    dollars: float
    estimated_shares: float
    first_tranche_dollars: float
    helper_text: str | None = None


class StrategyLabBacktestPoint(BaseModel):
    date: str
    equity: float


class StrategyLabBacktestSnapshot(BaseModel):
    status: BacktestStatusLiteral
    lookback_days: int | None = None
    requested_start_date: str | None = None
    requested_end_date: str | None = None
    available_start_date: str | None = None
    available_end_date: str | None = None
    total_return_pct: float | None = None
    buy_hold_return_pct: float | None = None
    excess_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    trade_count: int = 0
    equity_curve: list[StrategyLabBacktestPoint] = Field(default_factory=list)
    helper_text: str | None = None


class StrategyLabReviewCapability(BaseModel):
    available: bool
    message: str | None = None


class StrategyLabBaseEvaluation(BaseModel):
    symbol: str
    action: ActionLiteral
    strategy_template: StrategyTemplateLiteral
    primary_account_target: StrategyLabPrimaryAccountTarget | None = None
    updated_at: datetime
    helper_text: str | None = None


class StrategyLabListItem(StrategyLabBaseEvaluation):
    backtest_status: BacktestStatusLiteral | None = None
    backtest_helper_text: str | None = None
    backtest_lookback_days: int | None = None


class StrategyLabUnavailableItem(BaseModel):
    symbol: str
    reason: StrategyLabUnavailableReason
    message: str
    requested_start_date: str | None = None
    requested_end_date: str | None = None
    available_start_date: str | None = None
    available_end_date: str | None = None
    lookback_days: int | None = None


class StrategyLabListResponse(BaseModel):
    items: list[StrategyLabListItem] = Field(default_factory=list)
    unavailable_items: list[StrategyLabUnavailableItem] = Field(default_factory=list)
    total_count: int = 0


class StrategyLabDetailResponse(StrategyLabBaseEvaluation):
    why_bullets: list[str] = Field(default_factory=list)
    watch_item: str
    ticket: StrategyLabTicket | None = None
    backtest_snapshot: StrategyLabBacktestSnapshot
    review: StrategyLabReviewCapability


class StrategyLabReviewSuccess(BaseModel):
    verdict: str
    summary: str
    tailwinds: list[str] = Field(default_factory=list)
    headwinds: list[str] = Field(default_factory=list)
    invalidation_triggers: list[str] = Field(default_factory=list)
    act_now_or_wait: str
    generated_at: datetime


class StrategyLabReviewError(BaseModel):
    status: Literal["unavailable", "timeout", "stale_quote"]
    message: str
