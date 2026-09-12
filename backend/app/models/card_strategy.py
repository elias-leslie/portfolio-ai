"""The shared contract for a household's approved card strategy."""
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class StrategySettings(BaseModel):
    reminders_enabled: bool = True
    automatic_research: bool = False
    reserve_amazon: bool = True
    reserve_costco: bool = True
    reserve_gas: bool = True
    monthly_cap: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    costco_monthly: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class SpendingMonth(BaseModel):
    month: str
    ordinary_card_spend: float
    reserved_spend: float


class StrategyBaseline(BaseModel):
    monthly_available: float
    historical_monthly: float
    months: list[SpendingMonth]
    income_monthly: float | None
    income_source: str
    free_cash: float | None
    cash_status: str
    reservations: list[str]
    warnings: list[str]


class CardCandidate(BaseModel):
    key: str
    product_id: str
    product_name: str
    player: str
    applicant: str
    application_on: str
    application_by: str
    minimum_spend: float
    window_days: int
    bonus_value: float
    annual_fee: float
    incremental_value: float
    monthly_required: float
    terms_fingerprint: str
    terms_current: bool
    source_urls: list[str]
    checks: list[str]
    rationale: str
    spending_gap: float = 0
    monthly_gap: float = 0
    value_rank: int | None = None
    compared_offers: int = 0
    catalog_offers: int = 0


class BillPaymentPreference(BaseModel):
    preference: Literal["automatic", "keep_current", "consider_card"] = "automatic"


class BillSuggestion(BaseModel):
    key: str
    merchant: str
    amount: float
    cadence: str
    next_expected: str | None
    current_account: str | None
    already_card_spend: bool
    evidence: str
    status: Literal["suggested", "confirmed", "observed", "skipped", "already_on_card", "kept_in_place"] = "suggested"
    paid_from_cma: bool = False
    payment_preference: Literal["automatic", "keep_current", "consider_card"] = "automatic"
    keep_current_payment: bool = False
    payment_reason: str | None = None
    fee_per_charge: float | None = None
    lost_discount: float | None = None
    first_charge_due_on: str | None = None
    observed_on: str | None = None
    observation_id: str | None = None


class BonusTrack(BaseModel):
    card_id: str
    label: str
    applicant: str
    deadline: str | None
    required: float | None
    posted: float
    pending: float
    remaining: float | None
    days_left: int | None
    forecast: float | None
    status: str
    explanation: str


class StrategySnapshot(BaseModel):
    baseline: StrategyBaseline
    candidate: CardCandidate | None
    bills: list[BillSuggestion]
    settings: StrategySettings
    recommendation: str
    additional_spend_plan: str | None = None


class SavedStrategy(BaseModel):
    id: str
    fingerprint: str
    status: str
    snapshot: StrategySnapshot
    actual_card_id: str | None = None
    created_at: str
    approved_at: str | None = None
    eligibility_confirmed: bool = False


class StrategyView(BaseModel):
    as_of: str
    settings: StrategySettings
    baseline: StrategyBaseline
    candidates: list[CardCandidate]
    recommendation: str
    active: SavedStrategy | None
    draft: SavedStrategy | None
    history: list[SavedStrategy]
    progress: list[BonusTrack]
    bills: list[BillSuggestion]
    changes: list[str]
    review_events: list[dict[str, str]]


class ProposeStrategy(BaseModel):
    candidate_key: str | None = None
    wait: bool = False
    additional_spend_plan: str | None = Field(default=None, min_length=10, max_length=500)


class StrategyDecision(BaseModel):
    fingerprint: str
    action: Literal["approve", "pause", "resume", "link_card"]
    eligibility_confirmed: bool = False
    cash_flow_confirmed: bool = False
    additional_spend_confirmed: bool = False
    card_id: str | None = None


class BillDecision(BaseModel):
    status: Literal["confirmed", "skipped", "reset"]
    card_accepted: bool = False
    benefits_checked: bool = False
    fee_per_charge: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    lost_discount: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    confirmed_on: date | None = None
