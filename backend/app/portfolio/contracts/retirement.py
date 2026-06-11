"""Pydantic contracts for the retirement Monte Carlo simulator (F5).

The canonical service is ``app/services/retirement_planning_service.py``;
it builds these contracts from household + portfolio sources and
returns them. Field names stay technical
(``success_probability``, ``sequence_of_returns_risk``); the
plain-English translations from the plan's UX language table happen at
the render boundary, never in the contract.

Token-saving: ``ScenarioSummary`` is the compact list view; the full
``ScenarioResults`` (with percentile paths and the CMA snapshot) is
opt-in via ``GET /api/retirement/scenarios/{id}?detail=true``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class WithdrawalPhaseConfig(BaseModel):
    """Go-go / slow-go / no-go spending bands for ``decline_mode="phase"``."""

    model_config = ConfigDict(frozen=True)

    slow_go_age: int = Field(75, ge=40, le=110)
    no_go_age: int = Field(85, ge=40, le=120)
    go_go_pct: float = Field(1.0, ge=0.0, le=1.5)
    slow_go_pct: float = Field(0.85, ge=0.0, le=1.5)
    no_go_pct: float = Field(0.75, ge=0.0, le=1.5)


class WithdrawalBridgeConfig(BaseModel):
    """Pre-Social-Security bridge sleeve sizing (real dollars)."""

    model_config = ConfigDict(frozen=True)

    mode: Literal["auto", "manual"] = "auto"
    manual_amount: float | None = Field(None, ge=0.0)
    real_return: float = Field(0.01, ge=-0.05, le=0.10)


class WithdrawalHealthcarePoint(BaseModel):
    """Absolute real healthcare/LTC annual spend from ``age`` onward."""

    model_config = ConfigDict(frozen=True)

    age: int = Field(..., ge=18, le=120)
    real_amount: float = Field(..., ge=0.0)


class WithdrawalConfig(BaseModel):
    """Floor-and-upside spending-plan configuration (real dollars).

    ``essential_floor`` / ``base_discretionary`` are *resolved* annual real
    amounts. When both are ``None`` (the default, e.g. the persisted
    ``/scenarios`` route with no planner UI) the engine falls back to
    spend-the-gap semantics: the whole ``annual_expenses`` is treated as
    floor, no discretionary layer, and no bridge sleeve.
    """

    model_config = ConfigDict(frozen=True)

    strategy: Literal["vpw", "guardrails"] = "vpw"
    initial_rate: float = Field(0.05, ge=0.0, le=0.2)
    decline_mode: Literal["smooth", "phase"] = "smooth"
    discretionary_decline_rate: float = Field(0.01, ge=0.0, le=0.025)
    phase: WithdrawalPhaseConfig = Field(default_factory=WithdrawalPhaseConfig)
    bridge: WithdrawalBridgeConfig = Field(default_factory=WithdrawalBridgeConfig)
    healthcare_schedule: tuple[WithdrawalHealthcarePoint, ...] = ()
    essential_floor: float | None = Field(None, ge=0.0)
    base_discretionary: float | None = Field(None, ge=0.0)


class RetirementIncomeSource(BaseModel):
    """One household_retirement_income_sources row, normalised for sim."""

    model_config = ConfigDict(frozen=True)

    label: str
    source_type: str | None = None
    owner_name: str | None = None
    start_age: int = Field(..., ge=0, le=120)
    monthly_amount: float = Field(0.0, ge=0.0)
    inflation_adjusted: bool = False
    survivor_benefit: float | None = Field(None, ge=0.0)


class RetirementInputs(BaseModel):
    """Snapshot of the household + portfolio data driving a scenario.

    The service builds this once via ``build_inputs(household_id)``;
    the JSON shape is persisted in ``retirement_scenarios.inputs`` so
    that comparison runs against later household state remain
    reproducible.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    household_id: str
    primary_age: int = Field(..., ge=0, le=120)
    spouse_age: int | None = Field(None, ge=0, le=120)
    retirement_age: int = Field(..., ge=18, le=120)
    spouse_retirement_age: int | None = Field(None, ge=18, le=120)
    horizon_years: int = Field(30, ge=1, le=70)
    annual_expenses: float = Field(..., ge=0.0)
    annual_contribution: float = Field(0.0, ge=0.0)
    portfolio_value: float = Field(..., ge=0.0)
    asset_allocation: dict[str, float] = Field(default_factory=dict)
    cash_yield: float | None = Field(None, ge=0.0, le=0.2)
    taxable_gain_ratio: float | None = Field(None, ge=0.0, le=1.0)
    income_sources: tuple[RetirementIncomeSource, ...] = ()
    inflation_rate: float = Field(0.025, ge=0.0, le=0.2)
    social_security_payable_ratio: float = Field(1.0, ge=0.0, le=1.0)
    social_security_depletion_year: int | None = Field(None, ge=1900, le=2200)
    withdrawal: WithdrawalConfig = Field(default_factory=WithdrawalConfig)
    as_of_date: date


class ScenarioSummary(BaseModel):
    """Compact list-view row.

    Stored in ``retirement_scenarios`` as the cheap aggregate result —
    the simulation engine writes ``ScenarioResults`` to ``results`` and
    a ``ScenarioSummary`` is what list endpoints return.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    id: str
    household_id: str
    name: str
    success_probability: float = Field(..., ge=0.0, le=1.0)
    median_ending_balance: float
    sequence_of_returns_risk: float = Field(..., ge=0.0, le=1.0)
    trial_count: int = Field(..., ge=1, le=50_000)
    cma_source: str
    created_at: datetime


class ScenarioResults(BaseModel):
    """Full result body for one Monte Carlo run.

    ``percentiles`` is a {label: value} map (e.g.
    ``{"p10": 120000.0, "p50": 480000.0, "p90": 1200000.0}``).
    ``ending_balance_paths`` is opt-in detail (one float per percentile
    track per year) and can be null in the compact response.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    summary: ScenarioSummary
    inputs: RetirementInputs
    percentiles: dict[str, float]
    failure_year_distribution: dict[str, int] = Field(default_factory=dict)
    ending_balance_paths: dict[str, list[float]] | None = None
    cma_snapshot: dict[str, Any] | None = None


class RetirementAccountBucket(BaseModel):
    """Account-type bucket used by the visual retirement planner."""

    model_config = ConfigDict(frozen=True)

    bucket_type: str
    label: str
    account_type: str
    tax_treatment: str
    current_value: float = Field(0.0, ge=0.0)
    withdrawal_priority: int = Field(..., ge=1)


class RetirementHoldingsCoverageAccount(BaseModel):
    """Per-account confidence row for retirement allocation inputs."""

    model_config = ConfigDict(frozen=True)

    label: str
    bucket_type: str
    account_type: str
    current_value: float = Field(0.0, ge=0.0)
    exact_value: float = Field(0.0, ge=0.0)
    inferred_value: float = Field(0.0, ge=0.0)
    cash_value: float = Field(0.0, ge=0.0)
    priced_position_count: int = Field(0, ge=0)
    coverage_status: str
    coverage_label: str
    detail: str


class RetirementHoldingsCoverage(BaseModel):
    """Planning confidence for current-account holdings coverage."""

    model_config = ConfigDict(frozen=True)

    status: str = "no_accounts"
    label: str = "No accounts"
    detail: str = "No account values are available for holdings coverage."
    total_value: float = Field(0.0, ge=0.0)
    exact_value: float = Field(0.0, ge=0.0)
    inferred_value: float = Field(0.0, ge=0.0)
    cash_value: float = Field(0.0, ge=0.0)
    exact_share: float = Field(0.0, ge=0.0, le=1.0)
    accounts: tuple[RetirementHoldingsCoverageAccount, ...] = ()


class RetirementAccountAllocationAccount(BaseModel):
    """Per-account allocation row with exact-vs-inferred confidence."""

    model_config = ConfigDict(frozen=True)

    label: str
    bucket_type: str
    account_type: str
    current_value: float = Field(0.0, ge=0.0)
    exact_value: float = Field(0.0, ge=0.0)
    inferred_value: float = Field(0.0, ge=0.0)
    cash_value: float = Field(0.0, ge=0.0)
    priced_position_count: int = Field(0, ge=0)
    allocation_status: str
    allocation_label: str
    allocation: dict[str, float] = Field(default_factory=dict)
    detail: str


class RetirementAccountAllocationCoverage(BaseModel):
    """Planning confidence for account/bucket-specific allocation."""

    model_config = ConfigDict(frozen=True)

    status: str = "no_accounts"
    label: str = "No account allocation"
    detail: str = "No account values are available for allocation coverage."
    total_value: float = Field(0.0, ge=0.0)
    exact_value: float = Field(0.0, ge=0.0)
    inferred_value: float = Field(0.0, ge=0.0)
    cash_value: float = Field(0.0, ge=0.0)
    exact_share: float = Field(0.0, ge=0.0, le=1.0)
    asset_allocation: dict[str, float] = Field(default_factory=dict)
    accounts: tuple[RetirementAccountAllocationAccount, ...] = ()


class RetirementDrawdownYear(BaseModel):
    """One calendar year in the deterministic drawdown schedule.

    The ``spending_target`` .. ``withdrawal_rate`` block reports the
    floor-and-upside engine decision in REAL (today's) dollars; nominal
    amounts (``spending_need``, taxes, bucket draws) stay nominal.
    """

    model_config = ConfigDict(frozen=True)

    year_index: int = Field(..., ge=0)
    calendar_year: int
    primary_age: int = Field(..., ge=0, le=120)
    spending_need: float = Field(0.0, ge=0.0)
    income: float = Field(0.0, ge=0.0)
    gross_withdrawal: float = Field(0.0, ge=0.0)
    tax_estimate: float = Field(0.0, ge=0.0)
    penalty_estimate: float = Field(0.0, ge=0.0)
    net_withdrawal: float = Field(0.0, ge=0.0)
    ending_balance: float = Field(0.0, ge=0.0)
    rmd_amount: float = Field(0.0, ge=0.0)
    rmd_applied: bool = False
    withdrawals_by_bucket: dict[str, float] = Field(default_factory=dict)
    balances_by_bucket: dict[str, float] = Field(default_factory=dict)
    spending_target: float = Field(0.0, ge=0.0)
    floor_amount: float = Field(0.0, ge=0.0)
    discretionary_target: float = Field(0.0, ge=0.0)
    guaranteed_income: float = Field(0.0, ge=0.0)
    bridge_draw: float = Field(0.0, ge=0.0)
    portfolio_draw: float = Field(0.0, ge=0.0)
    bridge_balance: float = Field(0.0, ge=0.0)
    withdrawal_rate: float = Field(0.0, ge=0.0)


class RetirementAccountRule(BaseModel):
    """Plain-language audit of how one account bucket is modeled.

    Sourced from the F5 constants (withdrawal order, penalty rates, RMD
    age, tax treatment) so the planner can explain its assumptions
    without making advice claims.
    """

    model_config = ConfigDict(frozen=True)

    bucket_type: str
    label: str
    tax_treatment: str
    early_access: str
    rmd: str


class RetirementLeverImpact(BaseModel):
    """Small comparison run for a concrete planning lever."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    value: str
    success_probability: float = Field(..., ge=0.0, le=1.0)
    delta_success_probability: float
    detail: str


class RetirementPreview(BaseModel):
    """Interactive Money retirement planner response.

    Unlike ``ScenarioResults``, this response is not persisted. It adds
    account-type buckets and a deterministic drawdown schedule for UI
    exploration while reusing the Monte Carlo engine for readiness.
    """

    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    trusted_totals: bool
    account_control_status: str
    account_control_summary: str
    inputs: RetirementInputs
    success_probability: float = Field(..., ge=0.0, le=1.0)
    median_ending_balance: float
    sequence_of_returns_risk: float = Field(..., ge=0.0, le=1.0)
    percentiles: dict[str, float]
    ending_balance_paths: dict[str, list[float]]
    account_buckets: tuple[RetirementAccountBucket, ...] = ()
    holdings_coverage: RetirementHoldingsCoverage = Field(default_factory=RetirementHoldingsCoverage)
    account_allocation_coverage: RetirementAccountAllocationCoverage = Field(
        default_factory=RetirementAccountAllocationCoverage
    )
    tax_assumptions: dict[str, Any] = Field(default_factory=dict)
    return_assumptions: dict[str, Any] = Field(default_factory=dict)
    drawdown_schedule: tuple[RetirementDrawdownYear, ...] = ()
    account_rules: tuple[RetirementAccountRule, ...] = ()
    lever_impacts: tuple[RetirementLeverImpact, ...] = ()
    first_depletion_age: int | None = None
    median_discretionary_path: tuple[float, ...] = ()
    # Monte Carlo failure counts keyed by the primary age at which the trial
    # first fell short (string keys survive JSON round-trips untouched).
    failure_age_distribution: dict[str, int] = Field(default_factory=dict)
