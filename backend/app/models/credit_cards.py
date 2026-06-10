"""Pydantic models for the Credit Card Management feature.

Three groups:
  1. Row models mirroring the cc0{1-4} tables (catalog, owned cards, soft charges,
     persisted rotation plans).
  2. Engine output models (rankings, rotation projections) — all shapes are
     directly chartable by the Cards tab.
  3. Request bodies for the /api/household/cards endpoints.

Compliance: every ranking/rotation output is decision-support modeling of public
reward structures with surfaced assumptions, carrying CARD_ADVICE_DISCLAIMER. This
is NOT personalized financial advice.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

CARD_ADVICE_DISCLAIMER: str = (
    "Informational estimates, not financial advice. Values model publicly known "
    "reward structures under the stated assumptions and may differ from your "
    "results. Card churning carries credit-score and approval risk; pay balances "
    "in full to avoid interest, which erases reward value. Verify current terms "
    "with the issuer before acting — approval is never guaranteed."
)


# ---------------------------------------------------------------------------
# 1. Row models (mirror the cc0{1-4} tables)
# ---------------------------------------------------------------------------


class CardCredit(BaseModel):
    """A recurring statement credit attached to a product."""

    name: str
    annual_value: float = 0.0
    # How easy the credit is to actually realize: easy | moderate | hard.
    type: str = "moderate"


class CreditCardProduct(BaseModel):
    id: str
    slug: str
    issuer: str
    network: str | None = None
    product_name: str
    card_kind: str = "personal"
    annual_fee: float = 0.0
    # Keyed by canonical reward bucket (dining, travel, flights, groceries, gas, other).
    reward_multipliers: dict[str, float] = Field(default_factory=dict)
    point_program: str | None = None
    est_point_value_cents: float | None = None
    welcome_bonus_points: int = 0
    welcome_bonus_cash: float = 0.0
    welcome_min_spend: float | None = None
    welcome_window_days: int | None = None
    transfer_partners: list[str] = Field(default_factory=list)
    credits: list[CardCredit] = Field(default_factory=list)
    issuer_rules: dict[str, object] = Field(default_factory=dict)
    source: str = "seed"
    source_document_id: str | None = None
    last_verified_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class HouseholdCreditCard(BaseModel):
    id: str
    product_id: str
    household_account_id: str | None = None
    status: str = "candidate"
    is_primary_active: bool = False
    # Which household member holds/applies for the card (two-player rotation).
    player: str = "p1"
    # rotating = participates in the 90-day rotation (≤1 is_primary_active);
    # keeper = held permanently for a spend niche (e.g. Amazon Prime Visa).
    role: str = "rotating"
    opened_date: str | None = None
    closed_date: str | None = None
    annual_fee_due_date: str | None = None
    welcome_progress_amount: float = 0.0
    welcome_deadline: str | None = None
    welcome_status: str = "not_started"
    notes: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    # Hydrated join (optional) for convenience in the UI.
    product: CreditCardProduct | None = None


class SoftCharge(BaseModel):
    id: str
    household_account_id: str | None = None
    amount: float
    description: str
    merchant: str | None = None
    category: str | None = None
    essentiality: str | None = None
    occurred_at: str
    source_document_id: str | None = None
    status: str = "pending"
    matched_plaid_transaction_id: str | None = None
    matched_at: str | None = None
    match_confidence: float | None = None
    match_method: str | None = None
    ledger_transaction_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None


# ---------------------------------------------------------------------------
# 2. Engine output models (rankings + rotation projections)
# ---------------------------------------------------------------------------


class SpendProfile(BaseModel):
    """Monthly spend by reward bucket. Defaults from the last 3 months of real
    transactions; user-overridable."""

    monthly_total: float
    by_bucket: dict[str, float] = Field(default_factory=dict)
    source: str = "transactions_3m"  # transactions_3m | user_override | default


class CategoryContribution(BaseModel):
    bucket: str
    monthly_spend: float
    multiplier: float
    point_value_cents: float
    annual_value: float


class CardRewardEstimate(BaseModel):
    product_id: str
    slug: str
    issuer: str
    product_name: str
    card_kind: str
    annual_fee: float
    assumed_point_value_cents: float
    # Steady-state (recurring) components.
    earn_value: float
    credits_value: float
    annual_value: float  # earn + credits - annual_fee
    # First-year adds the one-time welcome bonus (if reachable).
    welcome_value: float
    welcome_reachable: bool
    first_year_value: float  # annual_value + welcome_value
    amortization_years: int
    steady_state_value: float  # annual_value + welcome_value / amortization_years
    category_contributions: list[CategoryContribution] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CardRanking(BaseModel):
    spend_profile: SpendProfile
    valuation_stance: str  # balanced | conservative | optimistic | custom
    amortization_years: int
    by_first_year: list[CardRewardEstimate] = Field(default_factory=list)
    by_steady_state: list[CardRewardEstimate] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    disclaimer: str = CARD_ADVICE_DISCLAIMER


class RotationStepView(BaseModel):
    sequence_index: int
    quarter_start: str | None = None
    quarter_label: str
    product_id: str | None = None
    product_slug: str | None = None
    product_name: str | None = None
    issuer: str | None = None
    household_credit_card_id: str | None = None
    # Which player opens/holds the card this quarter (two-player rotation).
    player: str | None = None
    action: str  # open_and_spend | switch_to | hold
    target_spend: float
    projected_welcome_value: float
    projected_earn_value: float
    projected_value: float  # welcome + earn - prorated annual fee
    rule_warnings: list[str] = Field(default_factory=list)


class RotationCumulativePoint(BaseModel):
    quarter_index: int
    quarter_label: str
    rotation_cumulative_value: float
    baseline_cumulative_value: float


class RotationPlanView(BaseModel):
    plan_id: str | None = None
    name: str
    objective: str
    horizon_quarters: int
    spend_profile: SpendProfile
    steps: list[RotationStepView] = Field(default_factory=list)
    projected_total_value: float
    baseline_single_card_value: float
    baseline_product_slug: str | None = None
    uplift: float  # projected_total_value - baseline_single_card_value
    cumulative_value: list[RotationCumulativePoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    disclaimer: str = CARD_ADVICE_DISCLAIMER


# ---------------------------------------------------------------------------
# 3. Request bodies
# ---------------------------------------------------------------------------


class RankingRequest(BaseModel):
    # Optional spend overrides; when omitted the engine derives from real data.
    monthly_total: float | None = None
    by_bucket: dict[str, float] | None = None
    valuation_stance: str = "balanced"  # balanced | conservative | optimistic | custom
    point_value_overrides: dict[str, float] | None = None  # keyed by point_program
    amortization_years: int = 3
    include_owned_only: bool = False
    # How statement credits count toward value. Default easy_only: only credits
    # that redeem themselves hands-off (easy 1.0 / moderate 0 / hard 0).
    credit_stance: str = "easy_only"  # easy_only | balanced | face_value


class RotationRequest(BaseModel):
    objective: str = "rotate_90d"  # rotate_90d | maximize_welcome_bonuses | maximize_category_earn
    horizon_quarters: int = 8
    monthly_total: float | None = None
    by_bucket: dict[str, float] | None = None
    valuation_stance: str = "balanced"
    point_value_overrides: dict[str, float] | None = None
    credit_stance: str = "easy_only"
    # Household members who alternate applications; one player solo is allowed
    # but exceeds Chase 5/24 within a year at a 90-day cadence.
    players: list[str] = Field(default_factory=lambda: ["p1", "p2"])
    name: str | None = None
    persist: bool = False


class CreditCardCreate(BaseModel):
    product_id: str
    status: str = "candidate"
    household_account_id: str | None = None
    player: str = "p1"
    role: str = "rotating"  # rotating | keeper
    opened_date: str | None = None
    welcome_deadline: str | None = None
    notes: str | None = None


class CreditCardUpdate(BaseModel):
    status: str | None = None
    household_account_id: str | None = None
    player: str | None = None
    role: str | None = None
    opened_date: str | None = None
    closed_date: str | None = None
    annual_fee_due_date: str | None = None
    welcome_progress_amount: float | None = None
    welcome_deadline: str | None = None
    welcome_status: str | None = None
    notes: str | None = None


class CardIntakeResult(BaseModel):
    """Returned by the offer-intake endpoint after the agent extracts terms."""

    document_id: str
    status: str  # extracted | needs_review | failed
    product: CreditCardProduct | None = None
    confidence: float | None = None
    unreadable_fields: list[str] = Field(default_factory=list)
    extraction_notes: str | None = None
