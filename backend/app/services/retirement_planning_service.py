"""Retirement Monte Carlo planning service (F5 single source of truth).

Reads household + portfolio state, runs the simulation engine in
``_retirement_simulation.py``, and persists ``ScenarioSummary`` +
``ScenarioResults`` rows in ``retirement_scenarios``. The router and
``st portfolio retirement-plan`` CLI are thin shims; no analytics live
outside this module.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from app.logging_config import get_logger
from app.portfolio.contracts.retirement import (
    RetirementACAConfig,
    RetirementACAPerson,
    RetirementAccountAllocationAccount,
    RetirementAccountAllocationCoverage,
    RetirementAccountBucket,
    RetirementAccountRule,
    RetirementBucketStrategy,
    RetirementBucketStrategyBucket,
    RetirementBucketStrategyHolding,
    RetirementCollegeYear,
    RetirementDrawdownYear,
    RetirementHoldingsCoverage,
    RetirementHoldingsCoverageAccount,
    RetirementIncomeSource,
    RetirementInputs,
    RetirementLeverImpact,
    RetirementLiquidityEvent,
    RetirementOutcomeFraming,
    RetirementPreview,
    RetirementSpendingReduction,
    ScenarioResults,
    ScenarioSummary,
    WithdrawalBridgeConfig,
    WithdrawalConfig,
    WithdrawalHealthcarePoint,
    WithdrawalPhaseConfig,
)
from app.services._aca_estimator import (
    MEDICARE_DEFAULT_MONTHLY_PER_PERSON,
    ACAPerson,
    ACAYearPlan,
    build_aca_year_plans,
    household_premium_monthly,
    premium_tax_credit_annual,
)
from app.services._retirement_simulation import (
    PERCENTILE_KEYS,
    SEQUENCE_OF_RETURNS_HORIZON,
    SimulationOutputs,
    _covariance_matrix,
    _normalize_allocation,
)
from app.services._withdrawal_engine import (
    BridgeConfig as EngineBridgeConfig,
)
from app.services._withdrawal_engine import (
    GuardrailsState,
    bridge_initial_size,
    guardrails_capacity_and_update,
    healthcare_ltc,
    step_year,
)
from app.services._withdrawal_engine import (
    HealthcarePoint as EngineHealthcarePoint,
)
from app.services._withdrawal_engine import (
    PhaseConfig as EnginePhaseConfig,
)
from app.services._withdrawal_engine import (
    SpendingReduction as EngineSpendingReduction,
)
from app.services._withdrawal_engine import (
    WithdrawalConfig as EngineWithdrawalConfig,
)
from app.services.aca_marketplace_ingest_service import (
    DEFAULT_COUNTIES as DEFAULT_ACA_COUNTIES,
)

logger = get_logger(__name__)

DEFAULT_TRIALS = 10_000
MAX_TRIALS = 50_000
DEFAULT_HORIZON_YEARS = 30
DEFAULT_RETIREMENT_AGE = 65
DEFAULT_LIST_LIMIT = 20
MAX_LIST_LIMIT = 100
CMA_PATH = Path(__file__).parent / "retirement_cma.yaml"
DEFAULT_PREVIEW_TRIALS = 2_500
RMD_START_AGE = 73
# 10% additional tax on pre-tax withdrawals before 59½ (limited exceptions).
EARLY_WITHDRAWAL_PENALTY_AGE = 59.5
# IRS Uniform Lifetime Table (effective 2022) — distribution-period divisors
# by age. RMDs begin at 73; 72 is kept for completeness, and ages past 120 use
# the 120+ divisor.
IRS_UNIFORM_LIFETIME_DIVISORS: dict[int, float] = {
    72: 27.4, 73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0,
    79: 21.1, 80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0,
    86: 15.2, 87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8,
    93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4, 97: 7.8, 98: 7.3, 99: 6.8,
    100: 6.4, 101: 6.0, 102: 5.6, 103: 5.2, 104: 4.9, 105: 4.6, 106: 4.3,
    107: 4.1, 108: 3.9, 109: 3.7, 110: 3.5, 111: 3.4, 112: 3.3, 113: 3.1,
    114: 3.0, 115: 2.9, 116: 2.8, 117: 2.7, 118: 2.5, 119: 2.3, 120: 2.0,
}
# HSA draws are modeled as non-medical (taxed as ordinary income, 20%
# penalty before 65) since the engine can't earmark medical spending — so
# the HSA is the costliest bucket to tap and drains after Roth.
DEFAULT_DRAWDOWN_ORDER = (
    "cash",
    "taxable",
    "governmental_457b",
    "pre_tax",
    "roth",
    "hsa",
    "other",
)
BUCKET_WITHDRAWAL_PRIORITY = {
    bucket: index + 1 for index, bucket in enumerate(DEFAULT_DRAWDOWN_ORDER)
}
BUCKET_LABELS = {
    "cash": "Cash bridge",
    "taxable": "Taxable brokerage",
    "governmental_457b": "Governmental 457(b)",
    "pre_tax": "Traditional retirement",
    "roth": "Roth IRA",
    "hsa": "HSA",
    "other": "Other assets",
}
BUCKET_TAX_TREATMENTS = {
    "cash": "already_taxed",
    "taxable": "taxable_capital_gains_estimate",
    "governmental_457b": "ordinary_income_no_10pct_early_penalty",
    "pre_tax": "ordinary_income",
    "roth": "tax_free_if_qualified",
    "hsa": "tax_free_for_qualified_medical",
    "other": "planning_estimate",
}
STRATEGY_BUCKET_LABELS = {
    "now": "Now / liquidity",
    "soon": "Soon / stability",
    "later": "Later / growth",
}
STRATEGY_BUCKET_HORIZONS = {
    "now": "Retirement year 1",
    "soon": "Retirement years 2-6",
    "later": "Years 7+",
}
STRATEGY_BUCKET_PURPOSES = {
    "now": "Cash and cash equivalents for the first year of portfolio withdrawals.",
    "soon": "High-quality bond exposure for the next five years of portfolio withdrawals.",
    "later": "Stock, real-estate, and other growth exposure for long-horizon spending.",
}
TAXABLE_WITHDRAWAL_GAIN_RATIO = 0.15
FEDERAL_TAX_YEAR = 2026
# Plain-language audit of how each bucket is modeled, keyed by bucket type.
# Kept terse on purpose: one early-access line and one RMD line each, sourced
# from the constants above — no advice, just what the simulation assumes.
BUCKET_RULE_EXPLANATIONS: dict[str, dict[str, str]] = {
    "cash": {
        "early_access": "Already-taxed cash; no withdrawal penalty.",
        "rmd": "Not subject to RMDs.",
    },
    "taxable": {
        "early_access": "No early-withdrawal penalty; only realized gains are taxed, at long-term rates.",
        "rmd": "Not subject to RMDs.",
    },
    "governmental_457b": {
        "early_access": "Penalty-free at any age after you separate from service; taxed as ordinary income.",
        "rmd": "Required minimum distributions begin at 73.",
    },
    "pre_tax": {
        "early_access": "10% penalty on withdrawals before 59½ (limited exceptions); taxed as ordinary income.",
        "rmd": "Required minimum distributions begin at 73.",
    },
    "roth": {
        "early_access": "Contributions withdrawable anytime; earnings tax-free after 59½ and the 5-year rule.",
        "rmd": "Roth IRAs have no lifetime RMDs for the original owner.",
    },
    "hsa": {
        "early_access": (
            "Tax-free for qualified medical costs; 20% penalty plus tax on non-medical use "
            "before 65. Modeled conservatively as non-medical: ordinary income tax, plus the "
            "penalty before 65."
        ),
        "rmd": "Not subject to RMDs; after 65 non-medical withdrawals are taxed as ordinary income.",
    },
    "other": {
        "early_access": "Modeled with planning-grade assumptions; confirm the specific account's rules.",
        "rmd": "RMD treatment depends on the underlying account type.",
    },
}
BUCKET_TAX_TREATMENT_LABELS: dict[str, str] = {
    "already_taxed": "Already taxed",
    "taxable_capital_gains_estimate": "Long-term capital gains on realized gains",
    "ordinary_income_no_10pct_early_penalty": "Ordinary income, no early-withdrawal penalty",
    "ordinary_income": "Ordinary income",
    "tax_free_if_qualified": "Tax-free if qualified",
    "tax_free_for_qualified_medical": "Tax-free for qualified medical",
    "planning_estimate": "Planning estimate",
}
SSA_2026_TAXABLE_WAGE_BASE = 184_500.0
SSA_2026_FIRST_BEND_POINT = 1_286.0
SSA_2026_SECOND_BEND_POINT = 7_749.0
SSA_FULL_RETIREMENT_AGE = 67
SSA_ASSUMED_CAREER_START_AGE = 22
DEFAULT_SOCIAL_SECURITY_DEPLETION_YEAR = 2033
DEFAULT_SOCIAL_SECURITY_PAYABLE_RATIO = 0.77
DEFAULT_SPAXX_CASH_YIELD = 0.0328
DEFAULT_SPAXX_CASH_YIELD_AS_OF = date(2026, 5, 7)
DEFAULT_SPAXX_CASH_YIELD_SOURCE = "Fidelity SPAXX 7-day yield"
# Freshness windows (days) shared with the frontend freshnessTone palette.
YIELD_FRESH_MAX_DAYS = 14
YIELD_AGING_MAX_DAYS = 45
INCOME_YIELD_BY_ASSET_CLASS = {
    "us_equity": 0.014,
    "intl_equity": 0.025,
    "bonds": 0.04,
    "cash": DEFAULT_SPAXX_CASH_YIELD,
    "real_estate": 0.035,
    "alts": 0.0,
}
CASH_EQUIVALENT_SYMBOLS = {"SPAXX", "FDRXX", "VMFXX", "SWVXX", "BIL", "SHV", "SGOV"}
DEFAULT_HOLDING_INCOME_YIELDS = {
    "VTI": 0.0106,
    "VOO": 0.011,
    "SPY": 0.011,
    "SCHD": 0.036,
    "VYM": 0.028,
    "DGRO": 0.021,
    "HDV": 0.034,
    "JEPI": 0.075,
    "BND": 0.04,
    "AGG": 0.04,
}
FILING_STATUS_LABELS = {
    "single": "Single",
    "married_filing_jointly": "Married filing jointly",
    "married_filing_separately": "Married filing separately",
    "head_of_household": "Head of household",
}
STANDARD_DEDUCTION_2026 = {
    "single": 16_100.0,
    "married_filing_jointly": 32_200.0,
    "married_filing_separately": 16_100.0,
    "head_of_household": 24_150.0,
}
ADDITIONAL_STANDARD_DEDUCTION_65_2026 = {
    "single": 2_050.0,
    "married_filing_jointly": 1_650.0,
    "married_filing_separately": 1_650.0,
    "head_of_household": 2_050.0,
}
ORDINARY_TAX_BRACKETS_2026 = {
    "single": (
        (12_400.0, 0.10),
        (50_400.0, 0.12),
        (105_700.0, 0.22),
        (201_775.0, 0.24),
        (256_225.0, 0.32),
        (640_600.0, 0.35),
        (float("inf"), 0.37),
    ),
    "married_filing_jointly": (
        (24_800.0, 0.10),
        (100_800.0, 0.12),
        (211_400.0, 0.22),
        (403_550.0, 0.24),
        (512_450.0, 0.32),
        (768_700.0, 0.35),
        (float("inf"), 0.37),
    ),
    "married_filing_separately": (
        (12_400.0, 0.10),
        (50_400.0, 0.12),
        (105_700.0, 0.22),
        (201_775.0, 0.24),
        (256_225.0, 0.32),
        (384_350.0, 0.35),
        (float("inf"), 0.37),
    ),
    "head_of_household": (
        (17_700.0, 0.10),
        (67_450.0, 0.12),
        (105_700.0, 0.22),
        (201_750.0, 0.24),
        (256_200.0, 0.32),
        (640_600.0, 0.35),
        (float("inf"), 0.37),
    ),
}
LONG_TERM_CAPITAL_GAINS_BRACKETS_2026 = {
    "single": (49_450.0, 545_500.0),
    "married_filing_jointly": (98_900.0, 613_700.0),
    "married_filing_separately": (49_450.0, 306_850.0),
    "head_of_household": (66_200.0, 579_600.0),
}
NIIT_THRESHOLDS_2026 = {
    "single": 200_000.0,
    "married_filing_jointly": 250_000.0,
    "married_filing_separately": 125_000.0,
    "head_of_household": 200_000.0,
}
NO_STATE_INCOME_TAX_STATES = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}


@dataclass(frozen=True, slots=True)
class FederalTaxContext:
    filing_status: str
    filing_status_source: str
    state_tax_rate: float
    state_tax_source: str


@dataclass(frozen=True, slots=True)
class WithdrawalOutcome:
    withdrawals: dict[str, float]
    tax_estimate: float
    penalty_estimate: float
    rmd_amount: float
    shortfall: float


def load_cma(path: Path | None = None) -> dict[str, Any]:
    """Load the long-term return estimates YAML.

    Module-level function so the simulation engine and tests can drive
    it without a service instance.
    """
    target = path or CMA_PATH
    with target.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _yield_freshness(as_of: date | None, anchor: date) -> tuple[str, str]:
    """Map a yield's as-of date to a (status, label) the UI can colour.

    Status values match the frontend ``freshnessTone`` palette so the
    planner reuses the existing badge styling rather than inventing one.
    A missing ``as_of`` means the number is a hardcoded planning
    assumption, not observed market data.
    """
    if as_of is None:
        return "needs_evidence", "Planning assumption"
    age_days = max((anchor - as_of).days, 0)
    if age_days <= YIELD_FRESH_MAX_DAYS:
        return "fresh", f"As of {as_of:%b %-d, %Y}"
    if age_days <= YIELD_AGING_MAX_DAYS:
        return "aging", f"{age_days} days old (as of {as_of:%b %-d, %Y})"
    return "stale", f"Stale — as of {as_of:%b %-d, %Y}"


# Worst-first so the rollup reflects the least-trustworthy input.
_FRESHNESS_PRIORITY = ("stale", "needs_evidence", "aging", "fresh", "not_applicable")
_FRESHNESS_ROLLUP_LABELS = {
    "stale": "Some yields are stale",
    "needs_evidence": "Some yields use planning assumptions",
    "aging": "Some yields are aging",
    "fresh": "Yields are current",
    "not_applicable": "Yields entered by you",
}


def _aggregate_income_yield_freshness(
    holding_yields: list[dict[str, Any]],
) -> tuple[str, str]:
    """Roll per-holding yield freshness into one status for the income card."""
    statuses = {str(row.get("freshness_status") or "fresh") for row in holding_yields}
    if not statuses:
        return "needs_evidence", "Income yield uses planning assumptions"
    for status in _FRESHNESS_PRIORITY:
        if status in statuses:
            return status, _FRESHNESS_ROLLUP_LABELS[status]
    return "fresh", _FRESHNESS_ROLLUP_LABELS["fresh"]


class RetirementPlanningService:
    """High-level F5 surface used by the router, CLI, and Jenny.

    Storage is the only required dependency at the constructor; the
    household + portfolio readers are imported lazily so test seams
    remain straightforward (``patch.object`` on the storage cursor).
    """

    def __init__(self, storage: Any) -> None:
        self.storage = storage
        self._cma = load_cma()

    # ------------------------------------------------------------------
    # public surface
    # ------------------------------------------------------------------

    def build_inputs(
        self,
        household_id: str,
        *,
        annual_expenses: float | None = None,
        annual_contribution: float | None = None,
        asset_allocation: dict[str, float] | None = None,
        allocation_holdings: list[Any] | tuple[Any, ...] | None = None,
        cash_yield: float | None = None,
        retirement_age: int | None = None,
        spouse_retirement_age: int | None = None,
        horizon_years: int | None = None,
        inflation_rate: float | None = None,
        social_security_payable_ratio: float | None = None,
        primary_age: int | None = None,
        spouse_age: int | None = None,
        spouse_net_monthly_income: float | None = None,
        partial_retirement_monthly_spend: float | None = None,
        spouse_gross_annual_income: float | None = None,
        as_of_date: date | None = None,
    ) -> RetirementInputs:
        """Pull inputs from household_planning + portfolio totals.

        ``annual_expenses`` / ``retirement_age`` / ``horizon_years``
        are caller-overridable so the CLI and Jenny can run
        what-if scenarios without first persisting different
        household state.
        """
        anchor = as_of_date or date.today()
        members = self._load_members()
        inferred_primary, inferred_spouse = _split_members(members, anchor)
        primary = primary_age if primary_age is not None else inferred_primary
        spouse = spouse_age if spouse_age is not None else inferred_spouse
        income_sources = self._load_retirement_income_sources()
        if annual_expenses is None:
            annual_expenses = self._infer_annual_expenses(default_when_missing=72_000.0)
        if annual_contribution is None:
            annual_contribution = self._infer_annual_contribution()
        portfolio_value, allocation = self._portfolio_snapshot()
        if allocation_holdings:
            allocation = self._allocation_from_holding_weights(allocation_holdings)
        elif asset_allocation:
            allocation = _normalized_asset_allocation(asset_allocation, self._cma)
        target_retirement_age = retirement_age or DEFAULT_RETIREMENT_AGE
        if spouse_retirement_age is None and spouse is not None:
            spouse_retirement_age = spouse + max(0, target_retirement_age - primary)

        return RetirementInputs(
            household_id=household_id,
            primary_age=primary,
            spouse_age=spouse,
            retirement_age=target_retirement_age,
            spouse_retirement_age=spouse_retirement_age,
            horizon_years=horizon_years or DEFAULT_HORIZON_YEARS,
            annual_expenses=annual_expenses,
            annual_contribution=annual_contribution,
            portfolio_value=portfolio_value,
            asset_allocation=allocation,
            cash_yield=_cash_yield(cash_yield),
            income_sources=income_sources,
            inflation_rate=(
                inflation_rate
                if inflation_rate is not None
                else float(self._cma.get("inflation_rate", 0.025))
            ),
            social_security_payable_ratio=_social_security_payable_ratio(social_security_payable_ratio),
            social_security_depletion_year=DEFAULT_SOCIAL_SECURITY_DEPLETION_YEAR,
            spouse_net_monthly_income=spouse_net_monthly_income,
            partial_retirement_monthly_spend=partial_retirement_monthly_spend,
            spouse_gross_annual_income=spouse_gross_annual_income,
            as_of_date=anchor,
        )

    def run_simulation(
        self,
        inputs: RetirementInputs,
        *,
        trials: int = DEFAULT_TRIALS,
        seed: int | None = None,
        tax_context: FederalTaxContext | None = None,
        buckets: tuple[RetirementAccountBucket, ...] = (),
        bucket_return_allocations: dict[str, dict[str, float]] | None = None,
    ) -> SimulationOutputs:
        """Run the Monte Carlo without persisting; pure compute.

        Single unified path: with no explicit buckets the tax-aware
        engine synthesizes one taxable bucket from ``portfolio_value``
        (see ``_bucket_balances``).
        """
        trials = max(1, min(trials, MAX_TRIALS))
        tax_context = tax_context or _tax_context_from_profile(None, inputs)
        cma = _cma_with_cash_yield(self._cma, inputs.cash_yield)
        return _run_tax_aware_monte_carlo(
            inputs,
            tax_context=tax_context,
            buckets=buckets,
            cma=cma,
            trials=trials,
            seed=seed,
            bucket_return_allocations=bucket_return_allocations,
        )

    def preview(
        self,
        household_id: str,
        *,
        annual_expenses: float | None = None,
        monthly_spend: float | None = None,
        asset_allocation: dict[str, float] | None = None,
        allocation_holdings: list[Any] | tuple[Any, ...] | None = None,
        cash_yield: float | None = None,
        retirement_age: int | None = None,
        spouse_retirement_age: int | None = None,
        horizon_years: int | None = None,
        annual_contribution: float | None = None,
        inflation_rate: float | None = None,
        primary_age: int | None = None,
        spouse_age: int | None = None,
        primary_social_security_monthly: float | None = None,
        spouse_social_security_monthly: float | None = None,
        primary_social_security_annual_earnings: float | None = None,
        spouse_social_security_annual_earnings: float | None = None,
        primary_social_security_start_age: int | None = None,
        spouse_social_security_start_age: int | None = None,
        social_security_payable_ratio: float | None = None,
        withdrawal: WithdrawalConfig | None = None,
        college_schedule: tuple[RetirementCollegeYear, ...] | None = None,
        spending_reductions: tuple[RetirementSpendingReduction, ...] | None = None,
        liquidity_events: tuple[RetirementLiquidityEvent, ...] | None = None,
        extra_income_sources: tuple[RetirementIncomeSource, ...] | None = None,
        aca: RetirementACAConfig | None = None,
        spouse_net_monthly_income: float | None = None,
        partial_retirement_monthly_spend: float | None = None,
        spouse_gross_annual_income: float | None = None,
        trials: int = DEFAULT_PREVIEW_TRIALS,
        seed: int | None = 7,
        as_of_date: date | None = None,
    ) -> RetirementPreview:
        """Build the interactive Money retirement planner preview."""
        dashboard = self._load_money_dashboard()
        profile = getattr(dashboard, "profile", None)
        if monthly_spend is None and profile is not None:
            monthly_spend = getattr(profile, "target_retirement_spend", None)
        if annual_expenses is None and monthly_spend is not None:
            annual_expenses = monthly_spend * 12.0
        if annual_contribution is None and profile is not None:
            monthly_savings = getattr(profile, "monthly_savings_target", None)
            annual_contribution = float(monthly_savings or 0.0) * 12.0
        if retirement_age is None and profile is not None:
            retirement_age = getattr(profile, "target_retirement_age", None)
        if spouse_retirement_age is None and profile is not None:
            spouse_retirement_age = getattr(profile, "target_spouse_retirement_age", None)
        if horizon_years is None and profile is not None:
            horizon_years = getattr(profile, "retirement_horizon_years", None)
        if inflation_rate is None and profile is not None:
            inflation_rate = getattr(profile, "retirement_inflation_rate", None)
        if primary_social_security_monthly is None and profile is not None:
            primary_social_security_monthly = getattr(profile, "primary_social_security_monthly", None)
        if spouse_social_security_monthly is None and profile is not None:
            spouse_social_security_monthly = getattr(profile, "spouse_social_security_monthly", None)
        if primary_social_security_annual_earnings is None and profile is not None:
            primary_social_security_annual_earnings = getattr(
                profile, "primary_social_security_annual_earnings", None
            )
        if spouse_social_security_annual_earnings is None and profile is not None:
            spouse_social_security_annual_earnings = getattr(
                profile, "spouse_social_security_annual_earnings", None
            )
        if primary_social_security_start_age is None and profile is not None:
            primary_social_security_start_age = getattr(
                profile, "primary_social_security_start_age", None
            )
        if spouse_social_security_start_age is None and profile is not None:
            spouse_social_security_start_age = getattr(
                profile, "spouse_social_security_start_age", None
            )
        if social_security_payable_ratio is None and profile is not None:
            social_security_payable_ratio = getattr(profile, "social_security_payable_ratio", None)
        social_security_payable_ratio = _social_security_payable_ratio(social_security_payable_ratio)
        if spouse_net_monthly_income is None and profile is not None:
            spouse_net_monthly_income = getattr(profile, "spouse_net_monthly_income", None)
        if partial_retirement_monthly_spend is None and profile is not None:
            partial_retirement_monthly_spend = getattr(
                profile, "partial_retirement_monthly_spend", None
            )
        if spouse_gross_annual_income is None and profile is not None:
            spouse_gross_annual_income = getattr(profile, "spouse_gross_annual_income", None)

        inputs = self.build_inputs(
            household_id,
            annual_expenses=annual_expenses,
            annual_contribution=annual_contribution,
            asset_allocation=asset_allocation,
            allocation_holdings=allocation_holdings,
            cash_yield=cash_yield,
            retirement_age=retirement_age,
            spouse_retirement_age=spouse_retirement_age,
            horizon_years=horizon_years,
            inflation_rate=inflation_rate,
            social_security_payable_ratio=social_security_payable_ratio,
            primary_age=primary_age,
            spouse_age=spouse_age,
            spouse_net_monthly_income=spouse_net_monthly_income,
            partial_retirement_monthly_spend=partial_retirement_monthly_spend,
            spouse_gross_annual_income=spouse_gross_annual_income,
            as_of_date=as_of_date,
        )
        inputs = _append_preview_social_security(
            inputs,
            primary_monthly=primary_social_security_monthly,
            spouse_monthly=spouse_social_security_monthly,
            primary_annual_earnings=primary_social_security_annual_earnings,
            spouse_annual_earnings=spouse_social_security_annual_earnings,
            primary_start_age=primary_social_security_start_age,
            spouse_start_age=spouse_social_security_start_age,
        )
        buckets = self._account_buckets_from_dashboard(dashboard)
        holdings_coverage = self._holdings_coverage_from_dashboard(dashboard)
        account_allocation_coverage = self._account_allocation_coverage_from_dashboard(
            dashboard,
            inputs.asset_allocation,
        )
        bucket_return_allocations = (
            _bucket_return_allocations(account_allocation_coverage, self._cma)
            if not asset_allocation and not allocation_holdings
            else {}
        )
        bucket_total = round(sum(bucket.current_value for bucket in buckets), 2)
        if bucket_total > 0:
            input_updates: dict[str, Any] = {"portfolio_value": bucket_total}
            if not asset_allocation and not allocation_holdings:
                input_updates["asset_allocation"] = (
                    account_allocation_coverage.asset_allocation
                    or _allocation_with_bucket_cash(
                        inputs.asset_allocation,
                        buckets,
                    )
                )
            inputs = inputs.model_copy(update=input_updates)
        elif inputs.portfolio_value > 0:
            buckets = (
                RetirementAccountBucket(
                    bucket_type="taxable",
                    label="Tracked portfolio",
                    account_type="portfolio",
                    tax_treatment=BUCKET_TAX_TREATMENTS["taxable"],
                    current_value=inputs.portfolio_value,
                    withdrawal_priority=BUCKET_WITHDRAWAL_PRIORITY["taxable"],
                ),
            )

        taxable_account_ids = [
            str(linked_id)
            for account in getattr(dashboard, "accounts", []) or []
            if _bucket_type(
                str(getattr(account, "asset_group", "") or "").lower(),
                str(getattr(account, "account_type", "") or "other"),
            )
            == "taxable"
            and (linked_id := getattr(account, "linked_portfolio_account_id", None))
        ]
        gain_ratio_result = self._taxable_embedded_gain_ratio(taxable_account_ids)
        gain_ratio_meta: dict[str, Any] | None = None
        if gain_ratio_result is not None:
            gain_ratio_value, gain_ratio_meta = gain_ratio_result
            inputs = inputs.model_copy(update={"taxable_gain_ratio": gain_ratio_value})

        return_allocation_holdings = allocation_holdings
        if (
            not asset_allocation
            and not allocation_holdings
            and account_allocation_coverage.total_value <= 0
        ):
            return_allocation_holdings = self._current_income_holdings(
                cash_value=sum(
                    bucket.current_value for bucket in buckets if bucket.bucket_type == "cash"
                )
            )
        baseline_ordinary_income = sum(
            float(value or 0.0)
            for value in (
                primary_social_security_annual_earnings,
                spouse_social_security_annual_earnings,
            )
            if value is not None and value > 0
        )

        healthcare_schedule = self._load_retirement_healthcare_schedule()
        base_config = withdrawal or _withdrawal_config_from_profile(profile, healthcare_schedule)
        if withdrawal is not None and not withdrawal.healthcare_schedule:
            # Requests that omit healthcare points inherit the persisted
            # schedule; an explicit list (even edited) wins.
            base_config = base_config.model_copy(update={"healthcare_schedule": healthcare_schedule})
        inputs = inputs.model_copy(
            update={"withdrawal": _withdrawal_config_from_inputs(inputs, profile, base_config)}
        )

        # College plan: explicit request schedule wins, else the persisted
        # one; the 529 sleeve is the education-account value excluded from
        # the retirement buckets above.
        college_rows = (
            college_schedule
            if college_schedule is not None
            else self._load_retirement_college_schedule()
        )
        college_529_value = round(
            sum(
                float(getattr(account, "current_value", 0.0) or 0.0)
                for account in getattr(dashboard, "accounts", []) or []
                if str(getattr(account, "asset_group", "") or "").lower() == "education"
                and float(getattr(account, "current_value", 0.0) or 0.0) > 0
            ),
            2,
        )
        if college_rows or college_529_value > 0:
            inputs = inputs.model_copy(
                update={
                    "college_schedule": tuple(college_rows),
                    "college_529_value": college_529_value,
                }
            )
        if spending_reductions is not None:
            inputs = inputs.model_copy(update={"spending_reductions": spending_reductions})
        if liquidity_events is not None:
            inputs = inputs.model_copy(update={"liquidity_events": liquidity_events})
        if extra_income_sources:
            inputs = inputs.model_copy(
                update={"income_sources": (*inputs.income_sources, *extra_income_sources)}
            )

        # ACA healthcare stream: explicit request config wins, else the
        # profile levers + household members; premium anchors resolve from
        # the CMS landscape table (manual override wins) and persist on the
        # inputs so saved scenarios replay reproducibly.
        aca_config = self._resolve_aca_config(
            aca if aca is not None else self._default_aca_config(profile), inputs
        )
        if aca_config is not None:
            inputs = inputs.model_copy(update={"aca": aca_config})

        tax_context = _tax_context_from_profile(profile, inputs)
        sim = self.run_simulation(
            inputs,
            trials=trials,
            seed=seed,
            tax_context=tax_context,
            buckets=buckets,
            bucket_return_allocations=bucket_return_allocations,
        )
        drawdown = self._drawdown_schedule(
            inputs,
            buckets=buckets,
            tax_context=tax_context,
            bucket_return_allocations=bucket_return_allocations,
        )
        bucket_strategy = self._bucket_strategy_from_dashboard(
            dashboard,
            inputs,
            drawdown=drawdown,
            account_allocation_coverage=account_allocation_coverage,
        )
        account_control = getattr(dashboard, "account_control", None)
        trusted_totals = not bool(getattr(account_control, "blocking_issue_count", 0))
        return RetirementPreview(
            trusted_totals=trusted_totals,
            account_control_status=getattr(account_control, "status", "unknown"),
            account_control_summary=getattr(account_control, "summary", ""),
            inputs=inputs,
            success_probability=sim.success_probability,
            median_ending_balance=sim.median_ending_balance,
            sequence_of_returns_risk=sim.sequence_of_returns_risk,
            percentiles=sim.percentiles,
            ending_balance_paths=sim.ending_balance_paths,
            account_buckets=buckets,
            holdings_coverage=holdings_coverage,
            account_allocation_coverage=account_allocation_coverage,
            bucket_strategy=bucket_strategy,
            tax_assumptions=_tax_assumptions(
                tax_context, buckets=buckets, inputs=inputs, gain_ratio_meta=gain_ratio_meta
            ),
            return_assumptions={
                **self._return_assumptions(
                    inputs,
                    allocation_holdings=return_allocation_holdings,
                    account_allocation_coverage=account_allocation_coverage,
                    tax_context=tax_context,
                    buckets=buckets,
                    baseline_ordinary_income=baseline_ordinary_income,
                ),
                **_withdrawal_summary(inputs, drawdown),
            },
            drawdown_schedule=tuple(drawdown),
            account_rules=_account_rule_explanations(buckets),
            lever_impacts=self._lever_impacts(
                inputs,
                sim.success_probability,
                trials=trials,
                seed=seed,
                tax_context=tax_context,
                buckets=buckets,
                bucket_return_allocations=bucket_return_allocations,
            ),
            first_depletion_age=_first_depletion_age(drawdown, _household_retirement_primary_age(inputs)),
            median_discretionary_path=tuple(sim.median_discretionary_path),
            failure_age_distribution=_failure_age_distribution(sim, inputs),
            outcome_framing=(
                RetirementOutcomeFraming(**sim.outcome_framing) if sim.outcome_framing else None
            ),
        )

    def save_scenario(
        self,
        *,
        name: str,
        inputs: RetirementInputs,
        sim: SimulationOutputs,
        trials: int,
        cma_source: str | None = None,
    ) -> ScenarioResults:
        """Persist a scenario row and return the full result contract."""
        scenario_id = str(uuid.uuid4())
        cma_label = cma_source or str(self._cma.get("version") or "yaml-v1")
        created_at = datetime.now(UTC)
        summary = ScenarioSummary(
            id=scenario_id,
            household_id=inputs.household_id,
            name=name,
            success_probability=sim.success_probability,
            median_ending_balance=sim.median_ending_balance,
            sequence_of_returns_risk=sim.sequence_of_returns_risk,
            trial_count=trials,
            cma_source=cma_label,
            created_at=created_at,
        )
        results = ScenarioResults(
            summary=summary,
            inputs=inputs,
            percentiles=sim.percentiles,
            failure_year_distribution=sim.failure_year_distribution,
            ending_balance_paths=sim.ending_balance_paths,
            cma_snapshot=self._cma,
        )

        with self.storage.connection() as conn:
            conn.execute(
                """
                INSERT INTO retirement_scenarios
                    (id, household_id, name, inputs, results,
                     cma_source, trial_count, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    scenario_id,
                    inputs.household_id,
                    name,
                    json.dumps(inputs.model_dump(mode="json")),
                    json.dumps(results.model_dump(mode="json")),
                    cma_label,
                    trials,
                    created_at,
                ],
            )
            conn.commit()
        return results

    def list_scenarios(
        self,
        household_id: str,
        *,
        limit: int = DEFAULT_LIST_LIMIT,
    ) -> list[ScenarioSummary]:
        limit = max(1, min(limit, MAX_LIST_LIMIT))
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT id, household_id, name, results, cma_source,
                       trial_count, created_at
                FROM retirement_scenarios
                WHERE household_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                [household_id, limit],
            ).fetchall()
        out: list[ScenarioSummary] = []
        for row in rows:
            results_payload = _coerce_json(row[3]) or {}
            summary_payload = results_payload.get("summary") or {}
            out.append(
                ScenarioSummary.model_validate(
                    {
                        **summary_payload,
                        "id": str(row[0]),
                        "household_id": row[1],
                        "name": row[2],
                        "trial_count": int(row[5]),
                        "cma_source": row[4],
                        "created_at": row[6],
                    }
                )
            )
        return out

    def show_scenario(
        self,
        scenario_id: str,
        *,
        detail: bool = False,
    ) -> ScenarioResults | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                "SELECT id, household_id, name, results, cma_source, trial_count, created_at"
                " FROM retirement_scenarios WHERE id = %s",
                [scenario_id],
            ).fetchone()
        if row is None:
            return None
        results_payload = _coerce_json(row[3]) or {}
        results = ScenarioResults.model_validate(results_payload)
        if not detail:
            return results.model_copy(
                update={"ending_balance_paths": None, "cma_snapshot": None}
            )
        return results

    def compare_scenarios(self, scenario_ids: list[str]) -> list[ScenarioSummary]:
        if not scenario_ids:
            return []
        with self.storage.connection() as conn:
            placeholders = ",".join(["%s"] * len(scenario_ids))
            rows = conn.execute(
                f"""
                SELECT id, household_id, name, results, cma_source,
                       trial_count, created_at
                FROM retirement_scenarios
                WHERE id IN ({placeholders})
                ORDER BY created_at DESC
                """,
                list(scenario_ids),
            ).fetchall()
        ordered: list[ScenarioSummary] = []
        for row in rows:
            results_payload = _coerce_json(row[3]) or {}
            summary_payload = results_payload.get("summary") or {}
            ordered.append(
                ScenarioSummary.model_validate(
                    {
                        **summary_payload,
                        "id": str(row[0]),
                        "household_id": row[1],
                        "name": row[2],
                        "trial_count": int(row[5]),
                        "cma_source": row[4],
                        "created_at": row[6],
                    }
                )
            )
        return ordered

    # ------------------------------------------------------------------
    # internal readers
    # ------------------------------------------------------------------

    def _load_members(self) -> list[dict[str, Any]]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT display_name, role, relationship, birth_year, is_dependent, notes"
                " FROM household_members"
                " ORDER BY is_dependent ASC, role ASC"
            ).fetchall()
        return [
            {
                "display_name": row[0],
                "role": row[1],
                "relationship": row[2] if len(row) > 4 else None,
                "birth_year": row[3] if len(row) > 4 else row[2],
                "is_dependent": (
                    bool(row[4])
                    if len(row) > 4 and row[4] is not None
                    else bool(row[3])
                    if len(row) > 3 and row[3] is not None
                    else False
                ),
                "notes": row[5] if len(row) > 5 else None,
            }
            for row in rows
        ]

    def _load_retirement_income_sources(self) -> tuple[RetirementIncomeSource, ...]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT label, source_type, owner_name, start_age, monthly_amount,"
                "       inflation_adjusted, survivor_benefit"
                " FROM household_retirement_income_sources"
                " ORDER BY start_age ASC"
            ).fetchall()
        sources: list[RetirementIncomeSource] = []
        for row in rows:
            start_age = int(row[3] or DEFAULT_RETIREMENT_AGE)
            monthly = float(row[4] or 0.0)
            sources.append(
                RetirementIncomeSource(
                    label=row[0] or "",
                    source_type=row[1],
                    owner_name=row[2],
                    start_age=start_age,
                    monthly_amount=monthly,
                    inflation_adjusted=bool(row[5]) if row[5] is not None else False,
                    survivor_benefit=float(row[6]) if row[6] is not None else None,
                )
            )
        return tuple(sources)

    def _load_money_dashboard(self) -> Any:
        """Load the canonical Money dashboard so account controls and values align."""
        service_mod = import_module("app.services.household_finance_service")
        return service_mod.HouseholdFinanceService().get_dashboard()

    def _load_retirement_healthcare_schedule(self) -> tuple[WithdrawalHealthcarePoint, ...]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT age, real_amount FROM household_retirement_healthcare_schedule"
                " ORDER BY age ASC"
            ).fetchall()
        return tuple(
            WithdrawalHealthcarePoint(age=int(row[0]), real_amount=float(row[1] or 0.0))
            for row in rows
            if row[0] is not None
        )

    def _load_retirement_college_schedule(self) -> tuple[RetirementCollegeYear, ...]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT calendar_year, real_amount FROM household_retirement_college_schedule"
                " ORDER BY calendar_year ASC"
            ).fetchall()
        return tuple(
            RetirementCollegeYear(calendar_year=int(row[0]), real_amount=float(row[1] or 0.0))
            for row in rows
            if row[0] is not None
        )

    def _household_aca_persons(
        self, dependents_covered_until_age: int | None
    ) -> tuple[RetirementACAPerson, ...]:
        """Covered lives from canonical household members.

        Dependents default to coverage until the year they turn 22
        (twins finish college — interview decision 4's default option);
        adults stay until Medicare. 0 drops dependents from coverage
        and the FPL household entirely (e.g. kids on FL KidCare —
        mirrors the accepted size-tracks-coverage simplification).
        """
        until_age = (
            22 if dependents_covered_until_age is None else dependents_covered_until_age
        )
        persons: list[RetirementACAPerson] = []
        for member in self._load_members():
            birth_year = member.get("birth_year")
            if birth_year is None:
                continue
            if member.get("is_dependent"):
                if until_age == 0:
                    continue
                covered_until = int(birth_year) + until_age
            else:
                covered_until = None
            persons.append(
                RetirementACAPerson(
                    birth_year=int(birth_year), covered_until_year=covered_until
                )
            )
        return tuple(persons)

    def _default_aca_config(self, profile: Any) -> RetirementACAConfig:
        """ACA config from profile levers + household members."""
        persons = self._household_aca_persons(None)
        tier = str(getattr(profile, "aca_tier", None) or "silver").lower()
        if tier not in {"silver", "bronze", "none"}:
            tier = "silver"
        override_raw = getattr(profile, "aca_premium_age21_override", None)
        oop_raw = getattr(profile, "aca_oop_monthly", None)
        medicare_raw = getattr(profile, "medicare_monthly_per_person", None)
        return RetirementACAConfig(
            tier=tier,
            premium_age21_monthly_override=float(override_raw) if override_raw else None,
            oop_monthly=float(oop_raw) if oop_raw else 0.0,
            medicare_monthly_per_person=(
                float(medicare_raw) if medicare_raw is not None else None
            ),
            persons=persons,
        )

    def _resolve_aca_config(
        self, config: RetirementACAConfig, inputs: RetirementInputs
    ) -> RetirementACAConfig | None:
        """Fill premium anchors and fall-back persons; ``None`` disables.

        A manual override prices the chosen plan but the subsidy is
        always computed against the Silver benchmark anchor.
        """
        if config.tier == "none":
            return None
        persons = config.persons
        if not persons:
            # Request overrides send levers, never raw persons — covered
            # lives re-derive from canonical household members so
            # dependents survive the override.
            persons = self._household_aca_persons(config.dependents_covered_until_age)
        if not persons:
            # No member rows: model the adults straight off the sim ages.
            birth_year = inputs.as_of_date.year - inputs.primary_age
            persons = (RetirementACAPerson(birth_year=birth_year),)
            if inputs.spouse_age is not None:
                persons += (
                    RetirementACAPerson(birth_year=inputs.as_of_date.year - inputs.spouse_age),
                )
        anchors = self._load_aca_premium_anchors()
        if anchors is None:
            return None
        plan_year, benchmark_age21, bronze_age21 = anchors
        chosen = config.premium_age21_monthly_override
        if chosen is None:
            chosen = bronze_age21 if config.tier == "bronze" else benchmark_age21
        if chosen is None or benchmark_age21 is None:
            return None
        return config.model_copy(
            update={
                "persons": persons,
                "plan_year": plan_year,
                "benchmark_age21_monthly": benchmark_age21,
                "chosen_age21_monthly": chosen,
                # None -> published-rate seed (CMS Part B/D + KFF Plan G),
                # persisted so saved scenario inputs replay reproducibly.
                "medicare_monthly_per_person": (
                    config.medicare_monthly_per_person
                    if config.medicare_monthly_per_person is not None
                    else MEDICARE_DEFAULT_MONTHLY_PER_PERSON
                ),
            }
        )

    def _load_aca_premium_anchors(self) -> tuple[int, float | None, float | None] | None:
        """(plan_year, benchmark Silver, lowest Bronze-tier) age-21 premiums.

        Benchmark = second-lowest-cost Silver plan (SLCSP) in the
        configured county for the latest ingested plan year; the Bronze
        anchor spans Bronze + Expanded Bronze.
        """
        fips = DEFAULT_ACA_COUNTIES[0][1]
        with self.storage.connection() as conn:
            year_row = conn.execute(
                "SELECT MAX(plan_year) FROM aca_marketplace_plans WHERE fips_county_code = %s",
                [fips],
            ).fetchone()
            if year_row is None or year_row[0] is None:
                return None
            plan_year = int(year_row[0])
            silver_rows = conn.execute(
                "SELECT premium_age_21 FROM aca_marketplace_plans"
                " WHERE plan_year = %s AND fips_county_code = %s AND metal_level = 'Silver'"
                "   AND premium_age_21 IS NOT NULL"
                " ORDER BY premium_age_21 ASC LIMIT 2",
                [plan_year, fips],
            ).fetchall()
            bronze_row = conn.execute(
                "SELECT MIN(premium_age_21) FROM aca_marketplace_plans"
                " WHERE plan_year = %s AND fips_county_code = %s"
                "   AND metal_level IN ('Bronze', 'Expanded Bronze')",
                [plan_year, fips],
            ).fetchone()
        benchmark = float(silver_rows[-1][0]) if silver_rows else None
        bronze = float(bronze_row[0]) if bronze_row and bronze_row[0] is not None else None
        return plan_year, benchmark, bronze

    def aca_estimate(
        self,
        *,
        magi_annual: float,
        ages: tuple[int, ...] | None = None,
        household_size: int | None = None,
        tier: str = "silver",
    ) -> dict[str, Any] | None:
        """One-shot ACA premium/subsidy estimate at an explicit MAGI.

        Ages and household size default to the household members
        currently in their coverage window. ``None`` when no landscape
        plans are ingested.
        """
        anchors = self._load_aca_premium_anchors()
        if anchors is None or anchors[1] is None:
            return None
        plan_year, benchmark_age21, bronze_age21 = anchors
        if ages is None or household_size is None:
            current_year = date.today().year
            in_window: list[int] = []
            for member in self._load_members():
                birth_year = member.get("birth_year")
                if birth_year is None:
                    continue
                if member.get("is_dependent") and current_year >= int(birth_year) + 22:
                    continue
                in_window.append(int(birth_year))
            if ages is None:
                ages = tuple(
                    sorted(
                        current_year - birth_year
                        for birth_year in in_window
                        if 0 <= current_year - birth_year < 65
                    )
                )
            if household_size is None:
                household_size = len(in_window)
        chosen_age21 = bronze_age21 if tier == "bronze" else benchmark_age21
        if chosen_age21 is None:
            return None
        gross_monthly = household_premium_monthly(chosen_age21, ages)
        benchmark_monthly = household_premium_monthly(benchmark_age21, ages)
        credit = premium_tax_credit_annual(
            magi_annual=magi_annual,
            household_size=household_size,
            benchmark_annual=benchmark_monthly * 12.0,
        )
        return {
            "plan_year": plan_year,
            "tier": tier,
            "ages": list(ages),
            "household_size": household_size,
            "magi_annual": round(magi_annual, 2),
            "magi_used": round(credit.magi_used, 2),
            "fpl_annual": round(credit.fpl, 2),
            "fpl_ratio": round(credit.fpl_ratio, 4),
            "applicable_pct": (
                round(credit.applicable_pct, 6) if credit.applicable_pct is not None else None
            ),
            "over_cliff": credit.over_cliff,
            "expected_contribution_annual": round(credit.expected_contribution, 2),
            "benchmark_age21_monthly": round(benchmark_age21, 2),
            "chosen_age21_monthly": round(chosen_age21, 2),
            "benchmark_premium_monthly": round(benchmark_monthly, 2),
            "gross_premium_monthly": round(gross_monthly, 2),
            "subsidy_monthly": round(credit.credit / 12.0, 2),
            "net_premium_monthly": round(
                max(0.0, gross_monthly * 12.0 - credit.credit) / 12.0, 2
            ),
        }

    def _account_buckets_from_dashboard(self, dashboard: Any) -> tuple[RetirementAccountBucket, ...]:
        buckets: list[RetirementAccountBucket] = []
        for account in getattr(dashboard, "accounts", []) or []:
            asset_group = str(getattr(account, "asset_group", "") or "").lower()
            # Education (529) accounts are earmarked for college and modeled
            # as a separate sleeve, never as spendable retirement money.
            if asset_group in {"credit", "debt", "education"}:
                continue
            value = float(getattr(account, "current_value", 0.0) or 0.0)
            if value <= 0:
                continue
            account_type = str(getattr(account, "account_type", "") or "other")
            label = str(getattr(account, "label", "") or "")
            bucket_type = _bucket_type(asset_group, account_type)
            if bucket_type == "taxable":
                cash_balance = min(float(getattr(account, "cash_balance", 0.0) or 0.0), value)
                if cash_balance > 0:
                    cash_label = label if cash_balance >= value else f"{label} cash"
                    buckets.append(
                        RetirementAccountBucket(
                            bucket_type="cash",
                            label=cash_label or BUCKET_LABELS["cash"],
                            account_type=account_type,
                            tax_treatment=BUCKET_TAX_TREATMENTS["cash"],
                            current_value=round(cash_balance, 2),
                            withdrawal_priority=BUCKET_WITHDRAWAL_PRIORITY["cash"],
                        )
                    )
                    value = max(value - cash_balance, 0.0)
                if value <= 0:
                    continue
            buckets.append(
                RetirementAccountBucket(
                    bucket_type=bucket_type,
                    label=label or BUCKET_LABELS[bucket_type],
                    account_type=account_type,
                    tax_treatment=BUCKET_TAX_TREATMENTS[bucket_type],
                    current_value=round(value, 2),
                    withdrawal_priority=BUCKET_WITHDRAWAL_PRIORITY[bucket_type],
                )
            )
        return tuple(sorted(buckets, key=lambda b: (b.withdrawal_priority, b.label)))

    def _holdings_coverage_from_dashboard(self, dashboard: Any) -> RetirementHoldingsCoverage:
        rows: list[RetirementHoldingsCoverageAccount] = []
        for account in getattr(dashboard, "accounts", []) or []:
            asset_group = str(getattr(account, "asset_group", "") or "").lower()
            # Education (529) accounts are earmarked for college and modeled
            # as a separate sleeve, never as spendable retirement money.
            if asset_group in {"credit", "debt", "education"}:
                continue
            value = float(getattr(account, "current_value", 0.0) or 0.0)
            if value <= 0:
                continue
            account_type = str(getattr(account, "account_type", "") or "other")
            label = str(getattr(account, "label", "") or "")
            bucket_type = _bucket_type(asset_group, account_type)
            cash_balance = min(float(getattr(account, "cash_balance", 0.0) or 0.0), value)
            if bucket_type in {"cash", "taxable"} and cash_balance > 0:
                cash_label = label if cash_balance >= value else f"{label} cash"
                rows.append(
                    RetirementHoldingsCoverageAccount(
                        label=cash_label or BUCKET_LABELS["cash"],
                        bucket_type="cash",
                        account_type=account_type,
                        current_value=round(cash_balance, 2),
                        exact_value=round(cash_balance, 2),
                        cash_value=round(cash_balance, 2),
                        priced_position_count=0,
                        coverage_status="cash",
                        coverage_label="Cash exact",
                        detail="Cash balance is modeled directly.",
                    )
                )
                value = max(value - cash_balance, 0.0)
                if value <= 0:
                    continue
            household_account_id = getattr(account, "household_account_id", None)
            linked_portfolio_id = str(
                getattr(account, "linked_portfolio_account_id", "") or ""
            )
            manual_editable = bool(household_account_id) and not linked_portfolio_id.startswith(
                "snaptrade:"
            )
            priced_count = int(getattr(account, "priced_position_count", 0) or 0)
            holdings_value = getattr(account, "holdings_value", None)
            if priced_count > 0:
                exact_value = min(value, float(holdings_value if holdings_value is not None else value))
                inferred_value = max(value - exact_value, 0.0)
                status = "partial_holdings" if inferred_value > 0.01 else "exact_holdings"
                rows.append(
                    RetirementHoldingsCoverageAccount(
                        label=label or BUCKET_LABELS[bucket_type],
                        bucket_type=bucket_type,
                        account_type=account_type,
                        household_account_id=household_account_id,
                        manual_holdings_editable=manual_editable,
                        current_value=round(value, 2),
                        exact_value=round(exact_value, 2),
                        inferred_value=round(inferred_value, 2),
                        priced_position_count=priced_count,
                        coverage_status=status,
                        coverage_label="Partial holdings" if status == "partial_holdings" else "Exact holdings",
                        detail=(
                            f"{priced_count} priced position"
                            f"{'s' if priced_count != 1 else ''} linked to this account."
                        ),
                    )
                )
                continue
            rows.append(
                RetirementHoldingsCoverageAccount(
                    label=label or BUCKET_LABELS[bucket_type],
                    bucket_type=bucket_type,
                    account_type=account_type,
                    household_account_id=household_account_id,
                    manual_holdings_editable=manual_editable,
                    current_value=round(value, 2),
                    inferred_value=round(value, 2),
                    coverage_status="account_value_only",
                    coverage_label="Account value only",
                    detail="No exact holdings are linked; allocation uses portfolio-level assumptions.",
                )
            )
        return _summarize_holdings_coverage(rows)

    def _account_allocation_coverage_from_dashboard(
        self,
        dashboard: Any,
        fallback_allocation: dict[str, float],
    ) -> RetirementAccountAllocationCoverage:
        ac_mod = import_module("app.portfolio.asset_classification")
        classifier = ac_mod.AssetClassifier(self.storage)
        linked_ids = [
            str(linked_id)
            for account in getattr(dashboard, "accounts", []) or []
            if (linked_id := getattr(account, "linked_portfolio_account_id", None))
        ]
        holdings_by_account = self._priced_holdings_by_account(linked_ids)
        fallback = _non_cash_fallback_allocation(fallback_allocation, self._cma)
        rows: list[RetirementAccountAllocationAccount] = []
        for account in getattr(dashboard, "accounts", []) or []:
            asset_group = str(getattr(account, "asset_group", "") or "").lower()
            # Education (529) accounts are earmarked for college and modeled
            # as a separate sleeve, never as spendable retirement money.
            if asset_group in {"credit", "debt", "education"}:
                continue
            value = float(getattr(account, "current_value", 0.0) or 0.0)
            if value <= 0:
                continue
            account_type = str(getattr(account, "account_type", "") or "other")
            label = str(getattr(account, "label", "") or "")
            bucket_type = _bucket_type(asset_group, account_type)
            cash_balance = min(float(getattr(account, "cash_balance", 0.0) or 0.0), value)
            if bucket_type in {"cash", "taxable"} and cash_balance > 0:
                cash_label = label if cash_balance >= value else f"{label} cash"
                rows.append(
                    RetirementAccountAllocationAccount(
                        label=cash_label or BUCKET_LABELS["cash"],
                        bucket_type="cash",
                        account_type=account_type,
                        current_value=round(cash_balance, 2),
                        exact_value=round(cash_balance, 2),
                        cash_value=round(cash_balance, 2),
                        allocation_status="cash",
                        allocation_label="Cash exact",
                        allocation={"cash": 1.0},
                        detail="Cash balance is modeled directly.",
                    )
                )
                value = max(value - cash_balance, 0.0)
                if value <= 0:
                    continue

            linked_id = getattr(account, "linked_portfolio_account_id", None)
            exact_holdings = holdings_by_account.get(str(linked_id), []) if linked_id else []
            exact_values = _class_values_from_holdings(ac_mod, classifier, exact_holdings)
            exact_value = sum(exact_values.values())
            if exact_value > value > 0:
                scale = value / exact_value
                exact_values = {
                    asset_class: asset_value * scale
                    for asset_class, asset_value in exact_values.items()
                }
                exact_value = value
            inferred_value = max(value - exact_value, 0.0)
            account_values = dict(exact_values)
            if inferred_value > 0.01:
                for asset_class, weight in fallback.items():
                    account_values[asset_class] = account_values.get(asset_class, 0.0) + (
                        inferred_value * weight
                    )
            status, status_label, detail = _account_allocation_status(
                exact_value=exact_value,
                inferred_value=inferred_value,
                priced_position_count=int(getattr(account, "priced_position_count", 0) or 0),
            )
            rows.append(
                RetirementAccountAllocationAccount(
                    label=label or BUCKET_LABELS[bucket_type],
                    bucket_type=bucket_type,
                    account_type=account_type,
                    current_value=round(value, 2),
                    exact_value=round(exact_value, 2),
                    inferred_value=round(inferred_value, 2),
                    priced_position_count=int(getattr(account, "priced_position_count", 0) or 0),
                    allocation_status=status,
                    allocation_label=status_label,
                    allocation=_values_to_allocation(account_values, self._cma),
                    detail=detail,
                )
            )
        return _summarize_account_allocation_coverage(rows, self._cma)

    def _bucket_strategy_from_dashboard(
        self,
        dashboard: Any,
        inputs: RetirementInputs,
        *,
        drawdown: list[RetirementDrawdownYear],
        account_allocation_coverage: RetirementAccountAllocationCoverage,
    ) -> RetirementBucketStrategy:
        holdings = self._strategy_holdings_from_dashboard(
            dashboard,
            inputs.asset_allocation,
        )
        return _build_retirement_bucket_strategy(
            inputs,
            drawdown=drawdown,
            account_allocation_coverage=account_allocation_coverage,
            holdings=holdings,
        )

    def _strategy_holdings_from_dashboard(
        self,
        dashboard: Any,
        fallback_allocation: dict[str, float],
    ) -> tuple[RetirementBucketStrategyHolding, ...]:
        ac_mod = import_module("app.portfolio.asset_classification")
        classifier = ac_mod.AssetClassifier(self.storage)
        linked_ids = [
            str(linked_id)
            for account in getattr(dashboard, "accounts", []) or []
            if (linked_id := getattr(account, "linked_portfolio_account_id", None))
        ]
        holdings_by_account = self._priced_holdings_by_account(linked_ids)
        fallback = _non_cash_fallback_allocation(fallback_allocation, self._cma)
        rows: list[RetirementBucketStrategyHolding] = []
        for account in getattr(dashboard, "accounts", []) or []:
            asset_group = str(getattr(account, "asset_group", "") or "").lower()
            if asset_group in {"credit", "debt", "education"}:
                continue
            value = float(getattr(account, "current_value", 0.0) or 0.0)
            if value <= 0:
                continue
            account_type = str(getattr(account, "account_type", "") or "other")
            account_label = str(getattr(account, "label", "") or "")
            bucket_type = _bucket_type(asset_group, account_type)
            cash_balance = min(float(getattr(account, "cash_balance", 0.0) or 0.0), value)
            if bucket_type in {"cash", "taxable"} and cash_balance > 0:
                cash_label = account_label if cash_balance >= value else f"{account_label} cash"
                rows.append(
                    RetirementBucketStrategyHolding(
                        symbol="CASH",
                        label=cash_label or "Cash",
                        asset_class="cash",
                        current_value=round(cash_balance, 2),
                        share_of_bucket=0.0,
                        source="cash",
                        account_label=account_label or None,
                    )
                )
                value = max(value - cash_balance, 0.0)
                if value <= 0:
                    continue

            linked_id = getattr(account, "linked_portfolio_account_id", None)
            exact_holdings = holdings_by_account.get(str(linked_id), []) if linked_id else []
            exact_total = sum(float(row.get("current_value") or 0.0) for row in exact_holdings)
            scale = value / exact_total if exact_total > value > 0 else 1.0
            exact_value = 0.0
            for holding in exact_holdings:
                holding_value = float(holding.get("current_value") or 0.0) * scale
                if holding_value <= 0:
                    continue
                symbol = str(holding.get("symbol") or "").upper()
                if not symbol:
                    continue
                asset_class = str(classifier.primary_class(symbol))
                exact_value += holding_value
                rows.append(
                    RetirementBucketStrategyHolding(
                        symbol=symbol,
                        label=symbol,
                        asset_class=asset_class,
                        current_value=round(holding_value, 2),
                        share_of_bucket=0.0,
                        source="exact",
                        account_label=account_label or None,
                    )
                )

            inferred_value = max(value - exact_value, 0.0)
            if inferred_value > 0.01:
                for asset_class, weight in fallback.items():
                    inferred_slice = inferred_value * float(weight or 0.0)
                    if inferred_slice <= 0:
                        continue
                    rows.append(
                        RetirementBucketStrategyHolding(
                            symbol=f"INFERRED_{asset_class.upper()}",
                            label=f"Inferred {_asset_class_label(asset_class)}",
                            asset_class=asset_class,
                            current_value=round(inferred_slice, 2),
                            share_of_bucket=0.0,
                            source="inferred",
                            account_label=account_label or None,
                        )
                    )
        return tuple(rows)

    def _priced_holdings_by_account(
        self,
        account_ids: list[str],
    ) -> dict[str, list[dict[str, Any]]]:
        if not account_ids:
            return {}
        price_mod = import_module("app.portfolio.price_fetcher")
        price_fetcher = price_mod.PriceDataFetcher(self.storage)
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT account_id, symbol, shares
                FROM portfolio_positions
                WHERE account_id = ANY(%s)
                  AND position_type = 'long'
                  AND shares > 0
                """,
                [sorted(set(account_ids))],
            ).fetchall()
        if not rows:
            return {}
        symbols = sorted({str(row[1]).upper() for row in rows})
        prices = price_fetcher.fetch_cached_price_data(symbols)
        out: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            account_id = str(row[0])
            symbol = str(row[1]).upper()
            shares = float(row[2] or 0.0)
            info = prices.get(symbol)
            if info is None or getattr(info, "error", None):
                continue
            price = float(getattr(info, "price", 0.0) or 0.0)
            if price <= 0 or shares <= 0:
                continue
            out.setdefault(account_id, []).append(
                {"symbol": symbol, "current_value": shares * price}
            )
        return out

    def _taxable_embedded_gain_ratio(
        self, taxable_account_ids: list[str]
    ) -> tuple[float, dict[str, Any]] | None:
        """Blended unrealized-gain share of taxable lots, or None if unknown.

        Uses ``portfolio_tax_lots`` (remaining open shares and their
        cost basis) priced against the cached quote so taxable-brokerage
        withdrawals tax only the embedded gain instead of a flat planning
        ratio. Returns ``None`` when no priced lots exist so the caller
        can fall back visibly to the planning assumption.
        """
        account_ids = sorted({str(a) for a in taxable_account_ids if a})
        if not account_ids:
            return None
        with self.storage.connection() as conn:
            rows = conn.execute(
                """
                SELECT symbol,
                       SUM(remaining_shares) AS shares,
                       SUM(remaining_shares * cost_per_share) AS cost
                FROM portfolio_tax_lots
                WHERE account_id = ANY(%s)
                  AND remaining_shares > 0
                  AND disposed_at IS NULL
                GROUP BY symbol
                """,
                [account_ids],
            ).fetchall()
        if not rows:
            return None
        price_mod = import_module("app.portfolio.price_fetcher")
        price_fetcher = price_mod.PriceDataFetcher(self.storage)
        symbols = sorted({str(row[0]).upper() for row in rows})
        prices = price_fetcher.fetch_cached_price_data(symbols)
        market_value = 0.0
        cost_basis = 0.0
        priced_symbols = 0
        for symbol, shares, cost in rows:
            sym = str(symbol).upper()
            shares_f = float(shares or 0.0)
            info = prices.get(sym)
            if shares_f <= 0 or info is None or getattr(info, "error", None):
                continue
            price = float(getattr(info, "price", 0.0) or 0.0)
            if price <= 0:
                continue
            market_value += shares_f * price
            cost_basis += float(cost or 0.0)
            priced_symbols += 1
        if market_value <= 0 or priced_symbols == 0:
            return None
        gain_ratio = max(0.0, min((market_value - cost_basis) / market_value, 1.0))
        meta = {
            "market_value": round(market_value, 2),
            "cost_basis": round(cost_basis, 2),
            "lot_symbol_count": priced_symbols,
        }
        return round(gain_ratio, 6), meta

    def _drawdown_schedule(
        self,
        inputs: RetirementInputs,
        *,
        buckets: tuple[RetirementAccountBucket, ...],
        tax_context: FederalTaxContext | None = None,
        bucket_return_allocations: dict[str, dict[str, float]] | None = None,
        ordinary_tax_rate: float | None = None,
        capital_gains_rate: float | None = None,
    ) -> list[RetirementDrawdownYear]:
        del ordinary_tax_rate, capital_gains_rate  # kept for older direct unit-call compatibility
        tax_context = tax_context or _tax_context_from_profile(None, inputs)
        annual_return = self._expected_return(inputs.asset_allocation, inputs.cash_yield)
        cash_return = self._expected_return({"cash": 1.0}, inputs.cash_yield)
        bucket_expected_returns = {
            bucket: self._expected_return(allocation, inputs.cash_yield)
            for bucket, allocation in (bucket_return_allocations or {}).items()
            if allocation
        }
        r_real = (1.0 + annual_return) / (1.0 + inputs.inflation_rate) - 1.0
        gain_ratio = _effective_gain_ratio(inputs)
        household_retirement_age = _household_retirement_primary_age(inputs)
        balances = _bucket_balances(inputs, buckets)
        contribution_bucket = _contribution_bucket(balances)
        aca_plans = _aca_year_plans(inputs)
        cfg = _engine_withdrawal_config(inputs, r_real=r_real, aca_plans=aca_plans)
        bridge_balance = _carve_bridge_from_balances(
            balances, bridge_initial_size(cfg, _real_guaranteed_income_fn(inputs))
        )
        guardrails_state = (
            GuardrailsState(initial_rate=cfg.initial_rate) if cfg.strategy == "guardrails" else None
        )
        # 529 sleeve (real dollars): earmarked for the college schedule,
        # drained before any retirement money; never part of ending_balance.
        college_balance = inputs.college_529_value
        college_by_year = {row.calendar_year: row.real_amount for row in inputs.college_schedule}
        liquidity_by_year: dict[int, float] = {}
        for event in inputs.liquidity_events:
            liquidity_by_year[event.calendar_year] = (
                liquidity_by_year.get(event.calendar_year, 0.0) + event.real_amount
            )
        rows: list[RetirementDrawdownYear] = []
        for year_index in range(inputs.horizon_years):
            primary_age = inputs.primary_age + year_index
            calendar_year = inputs.as_of_date.year + year_index
            if year_index > 0:
                for bucket in list(balances):
                    bucket_return = bucket_expected_returns.get(
                        bucket,
                        cash_return if bucket == "cash" else annual_return,
                    )
                    balances[bucket] = max(0.0, balances[bucket] * (1.0 + bucket_return))
                bridge_balance *= 1.0 + (
                    r_real if cfg.bridge.growth == "portfolio" else cfg.bridge.real_return
                )
                college_balance *= 1.0 + inputs.college_529_real_return
                if primary_age < household_retirement_age and inputs.annual_contribution > 0:
                    balances[contribution_bucket] = balances.get(contribution_bucket, 0.0) + inputs.annual_contribution

            inflation_factor = (1.0 + inputs.inflation_rate) ** year_index
            liquidity_real = liquidity_by_year.get(calendar_year, 0.0)
            if liquidity_real > 0:
                balances["taxable"] = balances.get("taxable", 0.0) + liquidity_real * inflation_factor
            spouse_age = inputs.spouse_age + year_index if inputs.spouse_age is not None else None
            income_components = _income_components_for_age(
                inputs.income_sources,
                primary_age,
                inflation_factor=inflation_factor,
                calendar_year=calendar_year,
                social_security_payable_ratio=inputs.social_security_payable_ratio,
                social_security_depletion_year=inputs.social_security_depletion_year,
            )
            income = income_components["total"]

            wy = None
            spending = 0.0
            portfolio_bal_real = sum(balances.values()) / inflation_factor
            if primary_age >= household_retirement_age:
                if guardrails_state is not None:
                    # Deterministic path: the expected return never flips
                    # sign year-to-year, so prev_return_negative is static.
                    guardrails_capacity_and_update(
                        portfolio_bal_real,
                        guardrails_state,
                        annual_return < 0 and year_index > 0,
                        inputs.inflation_rate,
                    )
                wy = step_year(
                    cfg,
                    year_index=year_index,
                    age=primary_age,
                    portfolio_bal_real=portfolio_bal_real,
                    bridge_bal_real=bridge_balance,
                    guaranteed_real=income / inflation_factor,
                    strategy_state=guardrails_state,
                )
                bridge_balance = wy.bridge_balance_end
                # R3 seam: gross-up target = portfolio draw (nominal) plus the
                # full nominal income so the tax estimate still sees income
                # for SS-taxability/bracket fill, with no double-count.
                spending = wy.portfolio_draw * inflation_factor + income

            # Partial-retirement window (primary retired, spouse working):
            # fund the spend-minus-net gap through the seam; her wages stack
            # the brackets without their own tax hitting the portfolio. The
            # engine never runs in these years (predicate ends at household
            # retirement, so ``wy is None`` here).
            partial = _partial_year_amounts_real(inputs, primary_age)
            partial_spend_nominal = 0.0
            partial_net_nominal = 0.0
            partial_wages_nominal = 0.0
            partial_gap_nominal = 0.0
            if partial is not None:
                spend_real, net_real, gross_real = partial
                partial_spend_nominal = spend_real * inflation_factor
                partial_net_nominal = net_real * inflation_factor
                partial_wages_nominal = gross_real * inflation_factor
                partial_gap_nominal = max(0.0, spend_real - net_real) * inflation_factor
                spending = partial_gap_nominal

            # College spend: 529 sleeve first; overflow lands on the
            # portfolio in retirement years (working years pay it from
            # salary, which the model never spends from the portfolio).
            college_cost = college_by_year.get(calendar_year, 0.0)
            college_draw = min(college_balance, college_cost)
            college_balance -= college_draw
            college_overflow = college_cost - college_draw
            if college_overflow > 0 and primary_age >= household_retirement_age:
                spending += college_overflow * inflation_factor

            # ACA true-up: the engine floor carries the *planning* net
            # healthcare cost; premium years reprice the subsidy off the
            # year's realized MAGI (draws included) and re-run the seam
            # with the difference. Snapshot first — the seam mutates.
            aca_plan = (
                aca_plans[year_index]
                if aca_plans is not None and primary_age >= household_retirement_age
                else None
            )
            pre_seam_balances = (
                dict(balances) if aca_plan is not None and aca_plan.gross_premium > 0 else None
            )
            outcome = _apply_tax_aware_withdrawals(
                balances,
                spending=spending,
                income_components=income_components,
                primary_age=primary_age,
                spouse_age=spouse_age,
                inflation_factor=inflation_factor,
                tax_context=tax_context,
                gain_ratio=gain_ratio,
                external_taxed_income=partial_wages_nominal,
            )
            aca_subsidy = aca_plan.planning_subsidy if aca_plan is not None else 0.0
            aca_net = aca_plan.planning_net if aca_plan is not None else 0.0
            magi_real = 0.0
            if aca_plan is not None and pre_seam_balances is not None:
                magi_real = (
                    _aca_magi_nominal(outcome, income_components, gain_ratio) / inflation_factor
                )
                aca_subsidy = premium_tax_credit_annual(
                    magi_annual=magi_real,
                    household_size=aca_plan.household_size,
                    benchmark_annual=aca_plan.benchmark_premium,
                ).credit
                aca_net = max(0.0, aca_plan.gross_premium - aca_subsidy) + aca_plan.oop
                delta = aca_net - aca_plan.planning_net
                if abs(delta) > 0.005:
                    balances = pre_seam_balances
                    spending += delta * inflation_factor
                    outcome = _apply_tax_aware_withdrawals(
                        balances,
                        spending=spending,
                        income_components=income_components,
                        primary_age=primary_age,
                        spouse_age=spouse_age,
                        inflation_factor=inflation_factor,
                        tax_context=tax_context,
                        gain_ratio=gain_ratio,
                    )
            withdrawals = outcome.withdrawals
            gross_withdrawal = round(sum(withdrawals.values()), 2)
            if wy is not None or partial_gap_nominal > 0.0:
                # R1: an RMD forced beyond the plan leaves post-tax surplus —
                # reinvest it in taxable so the household only consumes the
                # spending target.
                surplus_net = (
                    income + gross_withdrawal - outcome.tax_estimate - outcome.penalty_estimate - spending
                )
                if surplus_net > 0.01:
                    balances["taxable"] = balances.get("taxable", 0.0) + surplus_net

            # Bridge sleeve counts toward the household balance (nominal);
            # without it the carve reads as a phantom first-year drop and
            # _first_depletion_age can fire while the bridge still holds money.
            bridge_nominal = bridge_balance * inflation_factor
            ending_balance = round(sum(balances.values()) + bridge_nominal, 2)
            balances_by_bucket = {k: round(v, 2) for k, v in balances.items()}
            if bridge_nominal > 0.005:
                balances_by_bucket["bridge"] = round(bridge_nominal, 2)
            rows.append(
                RetirementDrawdownYear(
                    year_index=year_index,
                    calendar_year=calendar_year,
                    primary_age=primary_age,
                    spending_need=(
                        round(wy.spending_target * inflation_factor, 2)
                        if wy is not None
                        else round(partial_spend_nominal, 2)
                    ),
                    income=round(income, 2),
                    gross_withdrawal=gross_withdrawal,
                    tax_estimate=round(outcome.tax_estimate, 2),
                    penalty_estimate=round(outcome.penalty_estimate, 2),
                    net_withdrawal=round(
                        max(0.0, gross_withdrawal - outcome.tax_estimate - outcome.penalty_estimate),
                        2,
                    ),
                    ending_balance=ending_balance,
                    rmd_amount=round(outcome.rmd_amount, 2),
                    rmd_applied=outcome.rmd_amount > 0,
                    withdrawals_by_bucket={k: round(v, 2) for k, v in withdrawals.items()},
                    balances_by_bucket=balances_by_bucket,
                    spending_target=round(wy.spending_target, 2) if wy is not None else 0.0,
                    floor_amount=round(wy.floor, 2) if wy is not None else 0.0,
                    discretionary_target=round(wy.discretionary_target, 2) if wy is not None else 0.0,
                    spending_reduction=round(wy.spending_reduction, 2) if wy is not None else 0.0,
                    guaranteed_income=round(wy.guaranteed_income, 2) if wy is not None else 0.0,
                    bridge_draw=round(wy.bridge_draw, 2) if wy is not None else 0.0,
                    portfolio_draw=round(wy.portfolio_draw, 2) if wy is not None else 0.0,
                    bridge_balance=round(bridge_balance, 2),
                    withdrawal_rate=(
                        round(wy.portfolio_draw / portfolio_bal_real, 6)
                        if wy is not None and portfolio_bal_real > 0
                        else 0.0
                    ),
                    college_cost=round(college_cost, 2),
                    college_529_draw=round(college_draw, 2),
                    college_529_balance=round(college_balance, 2),
                    aca_premium_gross=(
                        round(aca_plan.gross_premium, 2) if aca_plan is not None else 0.0
                    ),
                    aca_subsidy=round(aca_subsidy, 2),
                    aca_oop=round(aca_plan.oop, 2) if aca_plan is not None else 0.0,
                    aca_net=round(aca_net, 2),
                    aca_planning_net=(
                        round(aca_plan.planning_net, 2) if aca_plan is not None else 0.0
                    ),
                    magi=round(magi_real, 2),
                    medicare_premium=(
                        round(aca_plan.medicare_premium, 2) if aca_plan is not None else 0.0
                    ),
                    partial_retirement_year=partial is not None,
                    spouse_net_income=round(partial_net_nominal, 2),
                )
            )
        return rows

    def _expected_return(self, allocation: dict[str, float], cash_yield: float | None = None) -> float:
        asset_classes = _cma_with_cash_yield(self._cma, cash_yield).get("asset_classes", {})
        weighted = 0.0
        total_weight = 0.0
        for klass, weight in allocation.items():
            meta = asset_classes.get(klass)
            if not meta:
                continue
            w = float(weight or 0.0)
            weighted += w * float(meta.get("expected_return", 0.0) or 0.0)
            total_weight += w
        if total_weight > 0:
            return weighted / total_weight
        cash = asset_classes.get("cash", {})
        return float(cash.get("expected_return", 0.02) or 0.02)

    def _return_assumptions(
        self,
        inputs: RetirementInputs,
        *,
        allocation_holdings: list[Any] | tuple[Any, ...] | None = None,
        account_allocation_coverage: RetirementAccountAllocationCoverage | None = None,
        tax_context: FederalTaxContext | None = None,
        buckets: tuple[RetirementAccountBucket, ...] = (),
        baseline_ordinary_income: float = 0.0,
    ) -> dict[str, Any]:
        cash_yield = _cash_yield(inputs.cash_yield)
        anchor = inputs.as_of_date
        holding_yields = self._holding_income_yields(
            allocation_holdings or (), cash_yield, anchor=anchor
        )
        if holding_yields:
            income_yield = sum(
                float(row["weight"]) * float(row["income_yield"]) for row in holding_yields
            )
        else:
            income_yield = _income_yield(inputs.asset_allocation, cash_yield)
        tax_drag = _income_tax_drag_estimate(
            inputs,
            income_yield=income_yield,
            holding_yields=holding_yields,
            tax_context=tax_context,
            buckets=buckets,
            baseline_ordinary_income=baseline_ordinary_income,
        )
        cash_freshness_status, cash_freshness_label = _yield_freshness(
            DEFAULT_SPAXX_CASH_YIELD_AS_OF, anchor
        )
        income_freshness = _aggregate_income_yield_freshness(holding_yields)
        return {
            "expected_return": round(self._expected_return(inputs.asset_allocation, cash_yield), 6),
            "income_yield": round(income_yield, 6),
            "income_yield_freshness_status": income_freshness[0],
            "income_yield_freshness_label": income_freshness[1],
            "cash_yield": round(cash_yield, 6),
            "cash_yield_source": DEFAULT_SPAXX_CASH_YIELD_SOURCE,
            "cash_yield_as_of": DEFAULT_SPAXX_CASH_YIELD_AS_OF.isoformat(),
            "cash_yield_freshness_status": cash_freshness_status,
            "cash_yield_freshness_label": cash_freshness_label,
            "dividend_tax_character": {
                "basis": "assumption",
                "detail": (
                    "Qualified vs. ordinary dividend treatment is assumed from fund type; "
                    "no per-fund tax-character source is available."
                ),
            },
            "holding_income_yields": holding_yields,
            "account_allocation_confidence": (
                {
                    "status": account_allocation_coverage.status,
                    "label": account_allocation_coverage.label,
                    "exact_share": account_allocation_coverage.exact_share,
                    "detail": account_allocation_coverage.detail,
                }
                if account_allocation_coverage is not None
                else None
            ),
            **tax_drag,
        }

    def _current_income_holdings(self, *, cash_value: float = 0.0) -> list[dict[str, Any]]:
        price_mod = import_module("app.portfolio.price_fetcher")
        price_fetcher = price_mod.PriceDataFetcher(self.storage)
        rows = [
            {"symbol": holding["symbol"], "weight": holding["current_value"]}
            for holding in self._holdings(price_fetcher)
            if float(holding.get("current_value") or 0.0) > 0
        ]
        if cash_value > 0:
            rows.append({"symbol": "SPAXX", "weight": cash_value})
        return rows

    def _holding_income_yields(
        self,
        holdings: list[Any] | tuple[Any, ...],
        cash_yield: float,
        *,
        anchor: date | None = None,
    ) -> list[dict[str, Any]]:
        anchor = anchor or date.today()
        weighted_rows: list[tuple[str, float, float, str, str, date | None]] = []
        total_weight = 0.0
        for holding in holdings:
            symbol = str(_holding_field(holding, "symbol") or "").upper().strip()
            weight = float(_holding_field(holding, "weight") or 0.0)
            if not symbol or weight <= 0:
                continue
            provided_yield = _optional_yield(_holding_field(holding, "dividend_yield"))
            if provided_yield is None:
                provided_yield = _optional_yield(_holding_field(holding, "dividendYield"))
            if provided_yield is not None:
                income_yield = provided_yield
                source = "user"
                as_of: date | None = None
            else:
                income_yield, source, as_of = self._income_yield_for_symbol(symbol, cash_yield)
            tax_category = _income_tax_category(symbol)
            weighted_rows.append((symbol, weight, income_yield, source, tax_category, as_of))
            total_weight += weight
        if total_weight <= 0:
            return []
        rows: list[dict[str, Any]] = []
        for symbol, weight, income_yield, source, tax_category, as_of in weighted_rows:
            freshness_as_of = as_of if source in {"reference_cache", "cash_yield"} else None
            if source == "user":
                freshness_status, freshness_label = "not_applicable", "Entered by you"
            else:
                freshness_status, freshness_label = _yield_freshness(freshness_as_of, anchor)
            rows.append(
                {
                    "symbol": symbol,
                    "weight": round(weight / total_weight, 6),
                    "income_yield": round(income_yield, 6),
                    "source": source,
                    "tax_category": tax_category,
                    "as_of": as_of.isoformat() if as_of is not None else None,
                    "freshness_status": freshness_status,
                    "freshness_label": freshness_label,
                }
            )
        return rows

    def _income_yield_for_symbol(
        self, symbol: str, cash_yield: float
    ) -> tuple[float, str, date | None]:
        if symbol in CASH_EQUIVALENT_SYMBOLS:
            return cash_yield, "cash_yield", DEFAULT_SPAXX_CASH_YIELD_AS_OF
        cached = self._latest_reference_dividend_yield(symbol)
        if cached is not None:
            return cached[0], "reference_cache", cached[1]
        fallback = DEFAULT_HOLDING_INCOME_YIELDS.get(symbol)
        if fallback is not None:
            return fallback, "default_symbol", None
        ac_mod = import_module("app.portfolio.asset_classification")
        asset_class = ac_mod.ASSET_CLASS_BY_SYMBOL.get(symbol, "us_equity")
        return float(INCOME_YIELD_BY_ASSET_CLASS.get(asset_class, 0.0)), "asset_class_default", None

    def _latest_reference_dividend_yield(self, symbol: str) -> tuple[float, date | None] | None:
        with self.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT dividend_yield, as_of_date
                FROM reference_cache
                WHERE symbol = %s AND dividend_yield IS NOT NULL
                ORDER BY as_of_date DESC, created_at DESC
                LIMIT 1
                """,
                [symbol],
            ).fetchone()
        if row is None:
            return None
        cached_yield = _optional_yield(row[0])
        if cached_yield is None:
            return None
        as_of = row[1] if len(row) > 1 else None
        if isinstance(as_of, datetime):
            as_of = as_of.date()
        return cached_yield, as_of if isinstance(as_of, date) else None

    def _lever_impacts(
        self,
        inputs: RetirementInputs,
        base_success_probability: float,
        *,
        trials: int,
        seed: int | None,
        tax_context: FederalTaxContext | None = None,
        buckets: tuple[RetirementAccountBucket, ...] = (),
        bucket_return_allocations: dict[str, dict[str, float]] | None = None,
    ) -> tuple[RetirementLeverImpact, ...]:
        later_update: dict[str, int] = {"retirement_age": min(inputs.retirement_age + 2, 120)}
        if inputs.spouse_retirement_age is not None:
            later_update["spouse_retirement_age"] = min(inputs.spouse_retirement_age + 2, 120)
        scenarios = [
            (
                "retire_later",
                "Both retire 2 years later" if inputs.spouse_retirement_age is not None else "Retire 2 years later",
                f"Your age {later_update['retirement_age']}",
                inputs.model_copy(update=later_update),
            ),
            (
                "spend_less",
                "Spend 10% less",
                f"${inputs.annual_expenses * 0.9 / 12:,.0f}/mo",
                # The engine spends the resolved floor/discretionary, not
                # annual_expenses — scale them too or the lever is a no-op.
                inputs.model_copy(
                    update={
                        "annual_expenses": round(inputs.annual_expenses * 0.9, 2),
                        "withdrawal": inputs.withdrawal.model_copy(
                            update={
                                "essential_floor": (
                                    round(inputs.withdrawal.essential_floor * 0.9, 2)
                                    if inputs.withdrawal.essential_floor is not None
                                    else None
                                ),
                                "base_discretionary": (
                                    round(inputs.withdrawal.base_discretionary * 0.9, 2)
                                    if inputs.withdrawal.base_discretionary is not None
                                    else None
                                ),
                            }
                        ),
                    }
                ),
            ),
            (
                "save_more",
                "Save $500/mo more",
                f"${(inputs.annual_contribution + 6_000) / 12:,.0f}/mo",
                inputs.model_copy(update={"annual_contribution": inputs.annual_contribution + 6_000}),
            ),
        ]
        out: list[RetirementLeverImpact] = []
        lever_trials = max(500, min(trials, 5_000))
        for lever_id, label, value, lever_inputs in scenarios:
            sim = self.run_simulation(
                lever_inputs,
                trials=lever_trials,
                seed=seed,
                tax_context=tax_context,
                buckets=buckets,
                bucket_return_allocations=bucket_return_allocations,
            )
            delta = sim.success_probability - base_success_probability
            out.append(
                RetirementLeverImpact(
                    id=lever_id,
                    label=label,
                    value=value,
                    success_probability=sim.success_probability,
                    delta_success_probability=round(delta, 6),
                    detail=(
                        f"{delta * 100:+.1f} percentage points versus the current preview."
                    ),
                )
            )
        return tuple(out)

    def _portfolio_snapshot(self) -> tuple[float, dict[str, float]]:
        """Build (total_value, asset_class_weights) from current portfolio.

        Reuses :class:`AssetClassifier` so the weights are aligned with
        the F3 drift report's bucketing — runs against the same set of
        positions, same fund-lookthrough rules.
        """
        ac_mod = import_module("app.portfolio.asset_classification")
        price_mod = import_module("app.portfolio.price_fetcher")
        classifier = ac_mod.AssetClassifier(self.storage)
        price_fetcher = price_mod.PriceDataFetcher(self.storage)
        holdings = self._holdings(price_fetcher)
        if not holdings:
            return 0.0, {}
        bucketed = classifier.classify_value(
            ac_mod.HoldingValue(symbol=h["symbol"], value=h["current_value"])
            for h in holdings
        )
        total = float(bucketed.total_value or 0.0)
        if total <= 0:
            return 0.0, {}
        weights: dict[str, float] = {}
        for klass, value in bucketed.by_class.items():
            if klass == "unclassified":
                continue
            value_f = float(value or 0.0)
            if value_f <= 0:
                continue
            weights[klass] = round(value_f / total, 6)
        return round(total, 2), weights

    def _allocation_from_holding_weights(self, holdings: list[Any] | tuple[Any, ...]) -> dict[str, float]:
        ac_mod = import_module("app.portfolio.asset_classification")
        classifier = ac_mod.AssetClassifier(self.storage)
        weighted_holdings = []
        for holding in holdings:
            symbol = str(_holding_field(holding, "symbol") or "").upper().strip()
            weight = float(_holding_field(holding, "weight") or 0.0)
            if not symbol or weight <= 0:
                continue
            weighted_holdings.append(ac_mod.HoldingValue(symbol=symbol, value=weight))
        if not weighted_holdings:
            return {}
        bucketed = classifier.classify_value(weighted_holdings)
        weights = dict(bucketed.by_class)
        unclassified = float(weights.pop("unclassified", 0.0) or 0.0)
        if unclassified > 0:
            weights["us_equity"] = weights.get("us_equity", 0.0) + unclassified
        return _normalized_asset_allocation(weights, self._cma)

    def _holdings(self, price_fetcher: Any) -> list[dict[str, Any]]:
        with self.storage.connection() as conn:
            rows = conn.execute(
                "SELECT symbol, shares FROM portfolio_positions"
                " WHERE position_type = 'long' AND shares > 0"
            ).fetchall()
        if not rows:
            return []
        symbols = sorted({str(row[0]).upper() for row in rows})
        prices = price_fetcher.fetch_cached_price_data(symbols)
        out: list[dict[str, Any]] = []
        for row in rows:
            symbol = str(row[0]).upper()
            shares = float(row[1] or 0.0)
            info = prices.get(symbol)
            if info is None or getattr(info, "error", None):
                continue
            price = float(getattr(info, "price", 0.0) or 0.0)
            if price <= 0 or shares <= 0:
                continue
            out.append({"symbol": symbol, "current_value": shares * price})
        return out

    def _infer_annual_expenses(self, *, default_when_missing: float) -> float:
        """Sum monthly expenses across the household_planning sections.

        Falls back to ``default_when_missing`` when the user hasn't
        captured detailed expense rows yet — the simulation still runs,
        the row just gets flagged in the input snapshot for the UI.
        """
        with self.storage.connection() as conn:
            sums = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(monthly_payment,0)), 0)"
                " FROM household_housing_costs"
            ).fetchone()
            monthly_housing = float(sums[0] or 0.0) if sums else 0.0
            sums = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(monthly_payment,0)), 0)"
                " FROM household_debt_obligations"
            ).fetchone()
            monthly_debt = float(sums[0] or 0.0) if sums else 0.0
            sums = conn.execute(
                "SELECT COALESCE(SUM(COALESCE(premium_monthly,0)), 0)"
                " FROM household_insurance_policies"
            ).fetchone()
            monthly_insurance = float(sums[0] or 0.0) if sums else 0.0
        annual = (monthly_housing + monthly_debt + monthly_insurance) * 12
        if annual <= 0:
            return float(default_when_missing)
        # Add a 50% wedge for everyday spending (food, transport, etc.)
        # so the projection isn't dominated solely by fixed costs.
        return round(annual * 1.5, 2)

    def _infer_annual_contribution(self) -> float:
        with self.storage.connection() as conn:
            row = conn.execute(
                "SELECT monthly_savings_target FROM household_profiles"
                " ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()
        if not row or row[0] is None:
            return 0.0
        return round(float(row[0] or 0.0) * 12.0, 2)


# ----------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------


def _split_members(
    members: list[dict[str, Any]],
    anchor: date | int | None = None,
    *,
    current_year: int | None = None,
) -> tuple[int, int | None]:
    if anchor is None:
        anchor = current_year if current_year is not None else date.today()
    current_date = date(anchor, 12, 31) if isinstance(anchor, int) else anchor
    primary_age: int | None = None
    spouse_age: int | None = None
    for row in members:
        age = _member_age(row, current_date)
        if age is None:
            continue
        role = (row.get("role") or "").strip().lower()
        relationship = (row.get("relationship") or "").strip().lower()
        if row.get("is_dependent") or role in {"child", "dependent"} or relationship in {
            "child",
            "daughter",
            "son",
            "dependent",
        }:
            continue
        if primary_age is None and (
            role in {"primary", "self", "owner"}
            or relationship in {"father", "husband", "self", "owner"}
        ):
            primary_age = age
        elif spouse_age is None and (
            role in {"spouse", "partner"}
            or relationship in {"mother", "wife", "spouse", "partner"}
        ):
            spouse_age = age
        elif primary_age is None:
            primary_age = age
    return primary_age if primary_age is not None else 50, spouse_age


def _member_age(row: dict[str, Any], anchor: date) -> int | None:
    birth_year = row.get("birth_year")
    if birth_year is None:
        return None
    birth_month, birth_day = _member_birth_month_day(row)
    age = anchor.year - int(birth_year)
    if (
        birth_month is not None
        and birth_day is not None
        and (anchor.month, anchor.day) < (birth_month, birth_day)
    ):
        age -= 1
    return max(0, age)


def _member_birth_month_day(row: dict[str, Any]) -> tuple[int | None, int | None]:
    notes = str(row.get("notes") or "")
    iso_match = re.search(
        r"\b(?:dob|birth(?:day)?)\s*:\s*\d{4}-(\d{1,2})-(\d{1,2})\b",
        notes,
        re.IGNORECASE,
    )
    if iso_match:
        return int(iso_match.group(1)), int(iso_match.group(2))
    month_match = re.search(
        r"\b(?:dob|birth(?:day)?)\s*:\s*"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
        r"\s+(\d{1,2})\b",
        notes,
        re.IGNORECASE,
    )
    if not month_match:
        return None, None
    month_token = month_match.group(1).lower()[:3]
    month = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }[month_token]
    return month, int(month_match.group(2))


def _coerce_json(value: Any) -> dict[str, Any] | None:
    if value is None or isinstance(value, dict):
        return value
    raw: str | None = None
    if isinstance(value, str):
        raw = value
    elif isinstance(value, (bytes, bytearray)):
        try:
            raw = value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _bucket_type(asset_group: str, account_type: str) -> str:
    normalized_type = account_type.strip().lower().replace("-", "_").replace(" ", "_")
    bucket = "other"
    if "roth" in normalized_type:
        bucket = "roth"
    elif normalized_type in {"governmental_457b", "gov_457b", "457b_governmental"}:
        bucket = "governmental_457b"
    elif normalized_type == "hsa" or "health_savings" in normalized_type:
        bucket = "hsa"
    elif asset_group == "cash":
        bucket = "cash"
    elif asset_group in {"taxable", "brokerage"}:
        bucket = "taxable"
    elif asset_group == "retirement" or normalized_type in {
        "ira",
        "401k",
        "403b",
        "457",
        "457b",
        "457_b",
        "retirement",
        "traditional_ira",
    }:
        bucket = "pre_tax"
    return bucket


def _tax_context_from_profile(profile: Any, inputs: RetirementInputs) -> FederalTaxContext:
    filing_status, filing_status_source = _filing_status_from_profile(profile, inputs.spouse_age)
    return FederalTaxContext(
        filing_status=filing_status,
        filing_status_source=filing_status_source,
        state_tax_rate=_state_tax_rate_from_profile(profile),
        state_tax_source=_state_tax_source_from_profile(profile),
    )


def _bucket_balances(
    inputs: RetirementInputs,
    buckets: tuple[RetirementAccountBucket, ...],
) -> dict[str, float]:
    balances = dict.fromkeys(DEFAULT_DRAWDOWN_ORDER, 0.0)
    for bucket in buckets:
        balances[bucket.bucket_type] = balances.get(bucket.bucket_type, 0.0) + bucket.current_value
    if sum(balances.values()) <= 0 and inputs.portfolio_value > 0:
        balances["taxable"] = inputs.portfolio_value
    return balances


def _holding_field(holding: Any, field: str) -> Any:
    if isinstance(holding, dict):
        return holding.get(field)
    return getattr(holding, field, None)


def _normalized_asset_allocation(
    allocation: dict[str, float],
    cma: dict[str, Any],
) -> dict[str, float]:
    asset_classes = cma.get("asset_classes", {})
    cleaned: dict[str, float] = {}
    for asset_class, raw_weight in allocation.items():
        key = str(asset_class or "").strip()
        if key not in asset_classes:
            continue
        weight = float(raw_weight or 0.0)
        if weight <= 0:
            continue
        cleaned[key] = cleaned.get(key, 0.0) + (weight / 100.0 if weight > 1.0 else weight)
    total = sum(cleaned.values())
    if total <= 0:
        return {}
    return {asset_class: round(weight / total, 6) for asset_class, weight in cleaned.items()}


def _simulation_asset_classes(
    allocation: dict[str, float],
    bucket_return_allocations: dict[str, dict[str, float]],
    cma: dict[str, Any],
) -> list[str]:
    asset_classes = cma.get("asset_classes", {})
    wanted = set(_normalized_asset_allocation(allocation, cma))
    for bucket_allocation in bucket_return_allocations.values():
        wanted.update(_normalized_asset_allocation(bucket_allocation, cma))
    return [asset_class for asset_class in asset_classes if asset_class in wanted]


def _weights_for_classes(allocation: dict[str, float], classes: list[str]) -> np.ndarray:
    values = np.array([float(allocation.get(asset_class, 0.0) or 0.0) for asset_class in classes])
    total = float(np.sum(values))
    if total <= 0:
        return np.zeros(len(classes), dtype=np.float64)
    return values / total


def _cash_yield(value: float | None) -> float:
    if value is None:
        return DEFAULT_SPAXX_CASH_YIELD
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_SPAXX_CASH_YIELD
    if parsed <= 0:
        return DEFAULT_SPAXX_CASH_YIELD
    return min(parsed / 100.0 if parsed > 1.0 else parsed, 0.2)


def _optional_yield(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if parsed < 0:
        return None
    return min(parsed / 100.0 if parsed > 1.0 else parsed, 1.0)


def _cma_with_cash_yield(cma: dict[str, Any], cash_yield: float | None) -> dict[str, Any]:
    rate = _cash_yield(cash_yield)
    out = dict(cma)
    asset_classes = {
        str(asset_class): dict(meta)
        for asset_class, meta in (cma.get("asset_classes") or {}).items()
        if isinstance(meta, dict)
    }
    cash_meta = dict(asset_classes.get("cash", {}))
    cash_meta["expected_return"] = rate
    asset_classes["cash"] = cash_meta
    out["asset_classes"] = asset_classes
    return out


def _allocation_with_bucket_cash(
    allocation: dict[str, float],
    buckets: tuple[RetirementAccountBucket, ...],
) -> dict[str, float]:
    total = sum(float(bucket.current_value or 0.0) for bucket in buckets)
    if total <= 0:
        return allocation
    cash_value = sum(
        float(bucket.current_value or 0.0)
        for bucket in buckets
        if bucket.bucket_type == "cash"
    )
    non_cash_value = max(0.0, total - cash_value)
    values: dict[str, float] = {}
    source_allocation = allocation or ({"us_equity": 1.0} if non_cash_value > 0 else {})
    for asset_class, weight in source_allocation.items():
        values[asset_class] = values.get(asset_class, 0.0) + float(weight or 0.0) * non_cash_value
    if cash_value > 0:
        values["cash"] = values.get("cash", 0.0) + cash_value
    normalized_total = sum(value for value in values.values() if value > 0)
    if normalized_total <= 0:
        return allocation
    return {
        asset_class: round(value / normalized_total, 6)
        for asset_class, value in values.items()
        if value > 0
    }


def _income_yield(allocation: dict[str, float], cash_yield: float | None) -> float:
    yields = {**INCOME_YIELD_BY_ASSET_CLASS, "cash": _cash_yield(cash_yield)}
    total = 0.0
    total_weight = 0.0
    for asset_class, weight in allocation.items():
        w = float(weight or 0.0)
        if w <= 0:
            continue
        total += w * float(yields.get(asset_class, 0.0))
        total_weight += w
    if total_weight <= 0:
        return 0.0
    return total / total_weight


def _income_tax_drag_estimate(
    inputs: RetirementInputs,
    *,
    income_yield: float,
    holding_yields: list[dict[str, Any]],
    tax_context: FederalTaxContext | None,
    buckets: tuple[RetirementAccountBucket, ...],
    baseline_ordinary_income: float = 0.0,
) -> dict[str, Any]:
    tax_context = tax_context or _tax_context_from_profile(None, inputs)
    total_value = sum(float(bucket.current_value or 0.0) for bucket in buckets) or inputs.portfolio_value
    if total_value <= 0 or income_yield <= 0:
        return _empty_tax_drag()
    taxable_value = sum(
        float(bucket.current_value or 0.0)
        for bucket in buckets
        if bucket.bucket_type in {"cash", "taxable"}
    )
    if not buckets:
        taxable_value = inputs.portfolio_value
    taxable_share = max(0.0, min(taxable_value / total_value, 1.0))
    if taxable_share <= 0:
        return _empty_tax_drag(taxable_asset_share=0.0)

    rows = holding_yields or _asset_class_income_yield_rows(inputs.asset_allocation, inputs.cash_yield)
    ordinary_income = 0.0
    qualified_income = 0.0
    for row in rows:
        weight = float(row.get("weight") or 0.0)
        row_yield = float(row.get("income_yield") or 0.0)
        amount = total_value * taxable_share * weight * row_yield
        if row.get("tax_category") == "qualified_dividend":
            qualified_income += amount
        else:
            ordinary_income += amount

    taxable_income = ordinary_income + qualified_income
    base_tax = _federal_tax_estimate(
        tax_context,
        ordinary_income=max(0.0, baseline_ordinary_income),
        social_security_benefits=0.0,
        long_term_capital_gains=0.0,
        primary_age=inputs.primary_age,
        spouse_age=inputs.spouse_age,
        inflation_factor=1.0,
    )
    tax_with_income = _federal_tax_estimate(
        tax_context,
        ordinary_income=max(0.0, baseline_ordinary_income) + ordinary_income,
        social_security_benefits=0.0,
        long_term_capital_gains=qualified_income,
        primary_age=inputs.primary_age,
        spouse_age=inputs.spouse_age,
        inflation_factor=1.0,
    )
    tax = max(0.0, tax_with_income - base_tax)
    return {
        "taxable_asset_share": round(taxable_share, 6),
        "estimated_taxable_income": round(taxable_income, 2),
        "estimated_ordinary_income": round(ordinary_income, 2),
        "estimated_qualified_dividends": round(qualified_income, 2),
        "estimated_income_tax_drag": round(tax, 2),
        "estimated_income_tax_drag_rate": round(tax / taxable_income, 6) if taxable_income > 0 else 0.0,
        "baseline_ordinary_income": round(max(0.0, baseline_ordinary_income), 2),
        "income_tax_drag_method": (
            "Incremental federal estimate on taxable-account interest/dividends over entered current salary; "
            "retirement withdrawals and Social Security are modeled separately."
        ),
    }


def _empty_tax_drag(taxable_asset_share: float = 0.0) -> dict[str, Any]:
    return {
        "taxable_asset_share": taxable_asset_share,
        "estimated_taxable_income": 0.0,
        "estimated_ordinary_income": 0.0,
        "estimated_qualified_dividends": 0.0,
        "estimated_income_tax_drag": 0.0,
        "estimated_income_tax_drag_rate": 0.0,
        "baseline_ordinary_income": 0.0,
        "income_tax_drag_method": "No taxable income drag estimated.",
    }


def _asset_class_income_yield_rows(
    allocation: dict[str, float],
    cash_yield: float | None,
) -> list[dict[str, Any]]:
    yields = {**INCOME_YIELD_BY_ASSET_CLASS, "cash": _cash_yield(cash_yield)}
    return [
        {
            "asset_class": asset_class,
            "weight": float(weight or 0.0),
            "income_yield": float(yields.get(asset_class, 0.0)),
            "source": "asset_class_default",
            "tax_category": _income_tax_category_for_asset_class(asset_class),
        }
        for asset_class, weight in allocation.items()
        if float(weight or 0.0) > 0
    ]


def _income_tax_category(symbol: str) -> str:
    if symbol in CASH_EQUIVALENT_SYMBOLS:
        return "ordinary_income"
    ac_mod = import_module("app.portfolio.asset_classification")
    asset_class = ac_mod.ASSET_CLASS_BY_SYMBOL.get(symbol, "us_equity")
    return _income_tax_category_for_asset_class(asset_class)


def _income_tax_category_for_asset_class(asset_class: str) -> str:
    if asset_class in {"us_equity", "intl_equity"}:
        return "qualified_dividend"
    return "ordinary_income"


def _withdrawal_config_from_profile(
    profile: Any,
    healthcare_schedule: tuple[WithdrawalHealthcarePoint, ...],
) -> WithdrawalConfig:
    """Build the planner WithdrawalConfig from persisted profile columns."""
    if profile is None:
        return WithdrawalConfig(healthcare_schedule=healthcare_schedule)

    def value(name: str, default: Any) -> Any:
        raw = getattr(profile, name, None)
        return default if raw is None else raw

    return WithdrawalConfig(
        strategy="guardrails",
        initial_rate=float(value("withdrawal_initial_rate", 0.05)),
        decline_mode=str(value("withdrawal_decline_mode", "smooth")),
        discretionary_decline_rate=float(value("discretionary_decline_rate", 0.01)),
        phase=WithdrawalPhaseConfig(
            slow_go_age=int(value("phase_slow_go_age", 75)),
            no_go_age=int(value("phase_no_go_age", 85)),
            go_go_pct=float(value("phase_go_go_pct", 1.0)),
            slow_go_pct=float(value("phase_slow_go_pct", 0.85)),
            no_go_pct=float(value("phase_no_go_pct", 0.75)),
        ),
        bridge=WithdrawalBridgeConfig(
            mode=str(value("bridge_mode", "auto")),
            manual_amount=getattr(profile, "bridge_manual_amount", None),
            real_return=float(value("bridge_real_return", 0.01)),
            growth=str(value("bridge_growth", "fixed")),
        ),
        healthcare_schedule=healthcare_schedule,
        essential_floor=getattr(profile, "retirement_essential_floor_override", None),
        base_discretionary=getattr(profile, "retirement_discretionary_override", None),
    )


def _withdrawal_config_from_inputs(
    inputs: RetirementInputs,
    profile: Any,
    base: WithdrawalConfig,
) -> WithdrawalConfig:
    """Resolve floor/discretionary via the budget ratio (R7 baseline carve-out).

    ``e = monthly_essential_target / (essential + discretionary)`` (0.6 when
    the budget is unset; a NULL side is derived from
    ``target_retirement_spend`` minus the other) split of
    ``annual_expenses``; healthcare at the
    household retirement age is netted out of the essential portion so the
    year-0 spending total equals the retirement spend target exactly.
    """
    essential_raw = getattr(profile, "monthly_essential_target", None)
    discretionary_raw = getattr(profile, "monthly_discretionary_target", None)
    essential = float(essential_raw) if essential_raw is not None else None
    discretionary = float(discretionary_raw) if discretionary_raw is not None else None
    # An unset target is NULL, not an explicit $0 — when only one side of the
    # budget is captured, derive the other from the retirement spend target so
    # a lone essential figure doesn't collapse the discretionary layer to zero
    # (which would make every Monte Carlo shortfall a total failure).
    monthly_spend_raw = getattr(profile, "target_retirement_spend", None)
    monthly_spend = float(monthly_spend_raw) if monthly_spend_raw is not None else None
    if discretionary is None and essential is not None and monthly_spend is not None:
        discretionary = max(0.0, monthly_spend - essential)
    if essential is None and discretionary is not None and monthly_spend is not None:
        essential = max(0.0, monthly_spend - discretionary)
    if essential is not None and discretionary is not None and essential + discretionary > 0:
        essential_share = essential / (essential + discretionary)
    else:
        essential_share = 0.6
    total = inputs.annual_expenses
    retirement_age = _household_retirement_primary_age(inputs)
    healthcare_at_retirement = healthcare_ltc(
        EngineWithdrawalConfig(
            healthcare_schedule=tuple(
                EngineHealthcarePoint(age=point.age, real_amount=point.real_amount)
                for point in base.healthcare_schedule
            )
        ),
        retirement_age,
    )
    base_discretionary = (
        base.base_discretionary
        if base.base_discretionary is not None
        else round(max(0.0, (1.0 - essential_share) * total), 2)
    )
    essential_floor = (
        base.essential_floor
        if base.essential_floor is not None
        else round(max(0.0, essential_share * total - healthcare_at_retirement), 2)
    )
    return base.model_copy(
        update={"essential_floor": essential_floor, "base_discretionary": base_discretionary}
    )


def _withdrawal_summary(
    inputs: RetirementInputs,
    drawdown: list[RetirementDrawdownYear],
) -> dict[str, Any]:
    """Bridge size/length + first-year and post-SS withdrawal rates for the UI summary strip."""
    retirement_age = _household_retirement_primary_age(inputs)
    primary_claim, spouse_claim = _ss_claim_ages(inputs)
    earliest_claim = min(
        [primary_claim] + ([spouse_claim] if spouse_claim is not None else [])
    )
    first_retirement = next((row for row in drawdown if row.primary_age >= retirement_age), None)
    post_ss = next(
        (row for row in drawdown if row.primary_age >= max(earliest_claim, retirement_age)),
        None,
    )
    bridge_rows = [row for row in drawdown if row.bridge_draw > 0]
    bridge_size = (
        round(first_retirement.bridge_draw + first_retirement.bridge_balance, 2)
        if first_retirement is not None
        else 0.0
    )
    return {
        "withdrawal_strategy": inputs.withdrawal.strategy,
        "bridge_size": bridge_size,
        "bridge_length_years": len(bridge_rows),
        "first_year_withdrawal_rate": (
            first_retirement.withdrawal_rate if first_retirement is not None else 0.0
        ),
        "post_social_security_withdrawal_rate": (
            post_ss.withdrawal_rate if post_ss is not None else 0.0
        ),
    }


def _ss_claim_ages(inputs: RetirementInputs) -> tuple[int, int | None]:
    """Social-Security claim ages from income sources (primary, spouse).

    With no SS sources the primary claim age collapses to the household
    retirement age so the auto bridge sizes to zero (there is nothing to
    bridge *to*).
    """
    claim_ages = sorted(
        source.start_age
        for source in inputs.income_sources
        if (source.source_type or "").lower() == "social_security"
    )
    if not claim_ages:
        return _household_retirement_primary_age(inputs), None
    primary = claim_ages[0]
    spouse = claim_ages[-1] if len(claim_ages) > 1 else None
    return primary, spouse


def _engine_withdrawal_config(
    inputs: RetirementInputs,
    *,
    r_real: float,
    aca_plans: tuple[ACAYearPlan, ...] | None = None,
) -> EngineWithdrawalConfig:
    """Convert the contract ``WithdrawalConfig`` to the pure-engine config.

    Unresolved floors (``essential_floor is None``, e.g. the persisted
    ``/scenarios`` route) fall back to spend-the-gap semantics: whole
    ``annual_expenses`` as floor, no discretionary layer, no bridge.

    With ``aca_plans`` the healthcare schedule becomes one point per
    retirement age summing the manual (LTC) schedule's carried-forward
    value with the year's ACA planning net and Medicare premiums (members
    65+) — summed, not appended, because ``healthcare_ltc`` is
    last-point-wins, not additive. The essential floor was already
    resolved against the manual schedule alone, so the healthcare stream
    lands *on top* of the spending target and the auto bridge sizes to
    cover it pre-Social-Security.
    """
    wc = inputs.withdrawal
    retirement_age = _household_retirement_primary_age(inputs)
    primary_claim, spouse_claim = _ss_claim_ages(inputs)
    if wc.essential_floor is None:
        essential_floor = inputs.annual_expenses
        base_discretionary = 0.0
        bridge = EngineBridgeConfig(mode="manual", manual_amount=0.0)
    else:
        essential_floor = wc.essential_floor
        base_discretionary = wc.base_discretionary or 0.0
        bridge = EngineBridgeConfig(
            mode=wc.bridge.mode,
            manual_amount=wc.bridge.manual_amount,
            real_return=wc.bridge.real_return,
            growth=wc.bridge.growth,
        )
    healthcare_points = tuple(
        EngineHealthcarePoint(age=point.age, real_amount=point.real_amount)
        for point in wc.healthcare_schedule
    )
    spending_reductions = tuple(
        EngineSpendingReduction(age=point.start_age, real_amount=point.annual_amount)
        for point in inputs.spending_reductions
    )
    if aca_plans is not None:
        manual_only = EngineWithdrawalConfig(healthcare_schedule=healthcare_points)
        healthcare_points = tuple(
            EngineHealthcarePoint(
                age=inputs.primary_age + plan.year_index,
                real_amount=healthcare_ltc(manual_only, inputs.primary_age + plan.year_index)
                + plan.planning_net
                + plan.medicare_premium,
            )
            for plan in aca_plans
            if inputs.primary_age + plan.year_index >= retirement_age
        )
    return EngineWithdrawalConfig(
        strategy=wc.strategy,
        initial_rate=wc.initial_rate,
        decline_mode=wc.decline_mode,
        discretionary_decline_rate=wc.discretionary_decline_rate,
        phase=EnginePhaseConfig(
            slow_go_age=wc.phase.slow_go_age,
            no_go_age=wc.phase.no_go_age,
            go_go_pct=wc.phase.go_go_pct,
            slow_go_pct=wc.phase.slow_go_pct,
            no_go_pct=wc.phase.no_go_pct,
        ),
        bridge=bridge,
        healthcare_schedule=healthcare_points,
        spending_reductions=spending_reductions,
        essential_floor=essential_floor,
        base_discretionary=base_discretionary,
        retirement_age=retirement_age,
        horizon_years=inputs.horizon_years,
        horizon_end_age=inputs.primary_age + inputs.horizon_years,
        primary_ss_claim_age=primary_claim,
        spouse_ss_claim_age=spouse_claim,
        r=r_real,
    )


def _aca_year_plans(inputs: RetirementInputs) -> tuple[ACAYearPlan, ...] | None:
    """Deterministic per-year ACA facts, or ``None`` when the stream is off.

    Planning MAGI uses guaranteed income only — ACA MAGI counts the FULL
    Social Security benefit (taxable or not) plus ordinary sources;
    portfolio draws are unknown here and reconcile at the tax seam.
    """
    cfg = inputs.aca
    if cfg is None or cfg.tier == "none" or not cfg.persons:
        return None
    if cfg.chosen_age21_monthly is None or cfg.benchmark_age21_monthly is None:
        return None
    retirement_age = _household_retirement_primary_age(inputs)

    def planning_magi(year_index: int) -> float:
        inflation_factor = (1.0 + inputs.inflation_rate) ** year_index
        components = _income_components_for_age(
            inputs.income_sources,
            inputs.primary_age + year_index,
            inflation_factor=inflation_factor,
            calendar_year=inputs.as_of_date.year + year_index,
            social_security_payable_ratio=inputs.social_security_payable_ratio,
            social_security_depletion_year=inputs.social_security_depletion_year,
        )
        return components["total"] / inflation_factor

    return build_aca_year_plans(
        persons=tuple(
            ACAPerson(birth_year=person.birth_year, covered_until_year=person.covered_until_year)
            for person in cfg.persons
        ),
        start_year=inputs.as_of_date.year,
        horizon_years=inputs.horizon_years,
        retirement_year_index=max(0, retirement_age - inputs.primary_age),
        chosen_age21_monthly=cfg.chosen_age21_monthly,
        benchmark_age21_monthly=cfg.benchmark_age21_monthly,
        oop_monthly=cfg.oop_monthly,
        medicare_monthly_per_person=cfg.medicare_monthly_per_person or 0.0,
        real_inflation=cfg.healthcare_real_inflation,
        plan_anchor_year=cfg.plan_year or inputs.as_of_date.year,
        planning_magi_fn=planning_magi,
    )


def _aca_magi_nominal(
    outcome: WithdrawalOutcome,
    income_components: dict[str, float],
    gain_ratio: float,
) -> float:
    """Modeled ACA MAGI (nominal) for the year's realized draws.

    Ordinary income + full Social Security + ordinary-income bucket
    draws + the taxable draw's gain slice; Roth/cash/basis draws and
    bridge-sleeve draws stay out (interview decision 2).
    """
    draws = outcome.withdrawals
    ordinary_draws = sum(draws.get(bucket, 0.0) for bucket in _ORDINARY_INCOME_BUCKETS)
    gains = draws.get("taxable", 0.0) * gain_ratio
    return (
        income_components["ordinary"]
        + income_components["social_security"]
        + ordinary_draws
        + gains
    )


def _real_guaranteed_income_fn(inputs: RetirementInputs) -> Callable[[int], float]:
    """Real guaranteed income at a primary age, for bridge sizing."""

    def fn(age: int) -> float:
        year_index = max(0, age - inputs.primary_age)
        inflation_factor = (1.0 + inputs.inflation_rate) ** year_index
        components = _income_components_for_age(
            inputs.income_sources,
            age,
            inflation_factor=inflation_factor,
            calendar_year=inputs.as_of_date.year + year_index,
            social_security_payable_ratio=inputs.social_security_payable_ratio,
            social_security_depletion_year=inputs.social_security_depletion_year,
        )
        return components["total"] / inflation_factor

    return fn


def _carve_bridge_from_balances(balances: dict[str, float], target: float) -> float:
    """Carve the bridge sleeve out of cash, then taxable (R2: scalar, not a bucket).

    At t=0 real == nominal, so the carve is a straight subtraction. Returns
    the amount actually carved (capped by what those buckets hold).
    """
    remaining = max(0.0, target)
    for bucket in ("cash", "taxable"):
        if remaining <= 0:
            break
        take = min(balances.get(bucket, 0.0), remaining)
        if take > 0:
            balances[bucket] -= take
            remaining -= take
    return max(0.0, target) - remaining


def _effective_gain_ratio(inputs: RetirementInputs) -> float:
    """Lots-derived embedded-gain ratio when known, else planning default."""
    if inputs.taxable_gain_ratio is not None:
        return inputs.taxable_gain_ratio
    return TAXABLE_WITHDRAWAL_GAIN_RATIO


# Buckets whose draws are taxed as ordinary income (HSA is modeled as
# non-medical use).
_ORDINARY_INCOME_BUCKETS = frozenset({"pre_tax", "governmental_457b", "hsa"})


def _apply_tax_aware_withdrawals(
    balances: dict[str, float],
    *,
    spending: float,
    income_components: dict[str, float],
    primary_age: int,
    spouse_age: int | None,
    inflation_factor: float,
    tax_context: FederalTaxContext,
    gain_ratio: float = TAXABLE_WITHDRAWAL_GAIN_RATIO,
    external_taxed_income: float = 0.0,
) -> WithdrawalOutcome:
    """Greedy bucket-order withdrawals grossed up for federal tax + penalties.

    This is the Monte Carlo hot path (trials x years x probes): the search
    varies a single bucket at a time, so the tax/penalty contribution of all
    settled buckets is folded into scalars and each probe costs exactly one
    ``_federal_tax_estimate`` call plus arithmetic.

    ``external_taxed_income`` (nominal) stacks the brackets — draws are taxed
    at the marginal rate above it — but its own tax (``external_base_tax``,
    the tax on those wages alone) is never charged against the portfolio:
    the partial-retirement window feeds spouse take-home as the offset, so
    her wage tax already left her paycheck.
    """
    withdrawals = dict.fromkeys(DEFAULT_DRAWDOWN_ORDER, 0.0)
    income_ordinary = income_components["ordinary"]
    income_social_security = income_components["social_security"]
    income_total = income_components["total"]
    penalty_rates = {
        bucket: _early_withdrawal_penalty_rate(bucket, primary_age)
        for bucket in DEFAULT_DRAWDOWN_ORDER
    }

    def tax_for_amounts(ordinary_withdrawals: float, taxable_gains: float) -> float:
        return _federal_tax_estimate(
            tax_context,
            ordinary_income=external_taxed_income + income_ordinary + ordinary_withdrawals,
            social_security_benefits=income_social_security,
            long_term_capital_gains=taxable_gains,
            primary_age=primary_age,
            spouse_age=spouse_age,
            inflation_factor=inflation_factor,
        )

    external_base_tax = 0.0
    if external_taxed_income > 0.0:
        external_base_tax = _federal_tax_estimate(
            tax_context,
            ordinary_income=external_taxed_income,
            social_security_benefits=0.0,
            long_term_capital_gains=0.0,
            primary_age=primary_age,
            spouse_age=spouse_age,
            inflation_factor=inflation_factor,
        )

    def settled_bases() -> tuple[float, float, float, float]:
        ordinary = sum(withdrawals[b] for b in _ORDINARY_INCOME_BUCKETS)
        gains = withdrawals["taxable"] * gain_ratio
        penalty = sum(amount * penalty_rates[b] for b, amount in withdrawals.items())
        gross = sum(withdrawals.values())
        return ordinary, gains, penalty, gross

    rmd_amount = _rmd_amount(
        balances.get("pre_tax", 0.0) + balances.get("governmental_457b", 0.0),
        primary_age,
    )
    if rmd_amount > 0:
        remaining_rmd = rmd_amount
        for rmd_bucket in ("pre_tax", "governmental_457b"):
            if remaining_rmd <= 0:
                break
            gross = min(balances.get(rmd_bucket, 0.0), remaining_rmd)
            if gross <= 0:
                continue
            balances[rmd_bucket] -= gross
            withdrawals[rmd_bucket] += gross
            remaining_rmd -= gross

    ordinary_base, gains_base, penalty_base, gross_base = settled_bases()

    def surplus_for(bucket: str, extra: float) -> float:
        ordinary = ordinary_base + (extra if bucket in _ORDINARY_INCOME_BUCKETS else 0.0)
        gains = gains_base + (extra * gain_ratio if bucket == "taxable" else 0.0)
        penalty = penalty_base + extra * penalty_rates[bucket]
        tax = tax_for_amounts(ordinary, gains) - external_base_tax
        return income_total + gross_base + extra - tax - penalty - spending

    # ``extra = 0`` gives the same surplus for every bucket, so the running
    # deficit is carried across the loop instead of re-probed per bucket.
    current_surplus = surplus_for(DEFAULT_DRAWDOWN_ORDER[0], 0.0)
    for bucket in DEFAULT_DRAWDOWN_ORDER:
        if current_surplus >= 0:
            break
        available = balances.get(bucket, 0.0)
        if available <= 0:
            continue
        full_surplus = surplus_for(bucket, available)
        if full_surplus < 0:
            gross = available
            current_surplus = full_surplus
        else:
            # Root-find the gross draw with Illinois regula falsi: the
            # surplus is piecewise linear in the draw (brackets, LTCG
            # stacking, NIIT kinks), so the secant converges in a handful
            # of probes where plain bisection needs dozens. ``high`` always
            # over-funds — the over-draw is recycled into taxable as
            # surplus — so reaching the iteration cap can never produce a
            # false shortfall. Each probe is one full federal-stack
            # estimate, the preview's latency hot path.
            low, f_low = 0.0, current_surplus
            high, f_high = available, full_surplus
            # Illinois damping halves retained-endpoint f values to force
            # convergence; ``f_high_true`` keeps the real surplus at ``high``
            # for the running deficit carried out of the loop.
            f_high_true = full_surplus
            side = 0
            for _ in range(32):
                # Stop on the criterion that matters: the accepted draw
                # (``high``) over-funds by at most $1.
                if f_high_true <= 1.0 or high - low <= 1.0:
                    break
                denom = f_high - f_low
                mid = (low * f_high - high * f_low) / denom if denom > 0 else 0.0
                if not low < mid < high:
                    mid = (low + high) / 2.0
                f_mid = surplus_for(bucket, mid)
                if f_mid >= 0:
                    high, f_high = mid, f_mid
                    f_high_true = f_mid
                    if side == 1:
                        f_low *= 0.5
                    side = 1
                else:
                    low, f_low = mid, f_mid
                    if side == -1:
                        f_high *= 0.5
                    side = -1
            gross = high
            current_surplus = f_high_true
        balances[bucket] = available - gross
        withdrawals[bucket] += gross
        ordinary_base, gains_base, penalty_base, gross_base = settled_bases()

    tax_estimate = max(0.0, tax_for_amounts(ordinary_base, gains_base) - external_base_tax)
    return WithdrawalOutcome(
        withdrawals=withdrawals,
        tax_estimate=tax_estimate,
        penalty_estimate=penalty_base,
        rmd_amount=rmd_amount,
        shortfall=max(
            0.0,
            -(income_total + gross_base - tax_estimate - penalty_base - spending),
        ),
    )


def _run_tax_aware_monte_carlo(
    inputs: RetirementInputs,
    *,
    tax_context: FederalTaxContext,
    buckets: tuple[RetirementAccountBucket, ...],
    cma: dict[str, Any],
    trials: int,
    seed: int | None,
    bucket_return_allocations: dict[str, dict[str, float]] | None = None,
) -> SimulationOutputs:
    rng = np.random.default_rng(seed)
    gain_ratio = _effective_gain_ratio(inputs)
    bucket_return_allocations = bucket_return_allocations or {}
    if bucket_return_allocations:
        classes = _simulation_asset_classes(
            inputs.asset_allocation,
            bucket_return_allocations,
            cma,
        )
        weights = _weights_for_classes(inputs.asset_allocation, classes)
    else:
        classes, weights = _normalize_allocation(inputs.asset_allocation, cma)
    if not classes:
        classes = ["cash"]
        weights = np.array([1.0])
    cov = _covariance_matrix(classes, cma)
    mus = np.array([float(cma["asset_classes"][c]["expected_return"]) for c in classes])
    samples = rng.multivariate_normal(mus, cov, size=(trials, inputs.horizon_years))
    portfolio_returns = samples @ weights
    bucket_weight_vectors = {
        bucket: _weights_for_classes(allocation, classes)
        for bucket, allocation in bucket_return_allocations.items()
        if allocation
    }

    cash_return = float(cma.get("asset_classes", {}).get("cash", {}).get("expected_return", 0.02) or 0.02)
    starting_balances = _bucket_balances(inputs, buckets)
    contribution_bucket = _contribution_bucket(starting_balances)
    household_retirement_age = _household_retirement_primary_age(inputs)
    expected_nominal = float(mus @ weights)
    aca_plans = _aca_year_plans(inputs)
    cfg = _engine_withdrawal_config(
        inputs,
        r_real=(1.0 + expected_nominal) / (1.0 + inputs.inflation_rate) - 1.0,
        aca_plans=aca_plans,
    )
    # R2: the bridge is a scalar sleeve carved from cash+taxable once at
    # setup — invisible to RMD/greedy/volatility logic, untaxed on draw.
    bridge_initial = _carve_bridge_from_balances(
        starting_balances, bridge_initial_size(cfg, _real_guaranteed_income_fn(inputs))
    )
    bridge_rides_portfolio = cfg.bridge.growth == "portfolio"
    failure_year = np.full(trials, -1, dtype=np.int32)
    yearly_balances = np.empty((trials, inputs.horizon_years), dtype=np.float64)
    discretionary_paths = np.zeros((trials, inputs.horizon_years), dtype=np.float64)
    # Beyond-success-% framing accumulators (all real/today's dollars).
    years_short = np.zeros(trials, dtype=np.int32)
    floor_gap_real = np.zeros(trials, dtype=np.float64)
    penalty_real = np.zeros(trials, dtype=np.float64)
    first_warning_year = np.full(trials, -1, dtype=np.int32)

    # Income/inflation context is identical for every trial — compute the
    # per-year values once instead of once per trial (this loop is the
    # preview's latency hot path).
    year_contexts: list[tuple[float, int | None, dict[str, float]]] = []
    # Partial-retirement window (primary retired, spouse working): per-year
    # nominal gap drawn from the portfolio and nominal wages stacking the
    # brackets. All zeros when the feature is off.
    partial_gap_nominal = [0.0] * inputs.horizon_years
    partial_wages_nominal = [0.0] * inputs.horizon_years
    for year_index in range(inputs.horizon_years):
        inflation_factor = (1.0 + inputs.inflation_rate) ** year_index
        spouse_age = inputs.spouse_age + year_index if inputs.spouse_age is not None else None
        income_components = _income_components_for_age(
            inputs.income_sources,
            inputs.primary_age + year_index,
            inflation_factor=inflation_factor,
            calendar_year=inputs.as_of_date.year + year_index,
            social_security_payable_ratio=inputs.social_security_payable_ratio,
            social_security_depletion_year=inputs.social_security_depletion_year,
        )
        year_contexts.append((inflation_factor, spouse_age, income_components))
        partial = _partial_year_amounts_real(inputs, inputs.primary_age + year_index)
        if partial is not None:
            spend_real, net_real, gross_real = partial
            partial_gap_nominal[year_index] = max(0.0, spend_real - net_real) * inflation_factor
            partial_wages_nominal[year_index] = gross_real * inflation_factor
    returns_by_trial = portfolio_returns.tolist()

    # College overflow is trial-independent: the 529 sleeve grows at a fixed
    # real return and drains against the fixed schedule, so the nominal
    # portfolio hit per year is a precomputed constant (0 in working years —
    # salary covers any overflow before retirement).
    college_overflow_nominal = [0.0] * inputs.horizon_years
    if inputs.college_schedule:
        college_balance = inputs.college_529_value
        college_by_year = {row.calendar_year: row.real_amount for row in inputs.college_schedule}
        for year_index in range(inputs.horizon_years):
            if year_index > 0:
                college_balance *= 1.0 + inputs.college_529_real_return
            cost = college_by_year.get(inputs.as_of_date.year + year_index, 0.0)
            draw = min(college_balance, cost)
            college_balance -= draw
            overflow = cost - draw
            if overflow > 0 and inputs.primary_age + year_index >= household_retirement_age:
                college_overflow_nominal[year_index] = overflow * year_contexts[year_index][0]
    liquidity_by_year: dict[int, float] = {}
    for event in inputs.liquidity_events:
        liquidity_by_year[event.calendar_year] = (
            liquidity_by_year.get(event.calendar_year, 0.0) + event.real_amount
        )

    for trial in range(trials):
        balances = dict(starting_balances)
        bridge_balance = bridge_initial
        guardrails_state = (
            GuardrailsState(initial_rate=cfg.initial_rate) if cfg.strategy == "guardrails" else None
        )
        prev_return_negative = False
        trial_returns = returns_by_trial[trial]
        for year_index in range(inputs.horizon_years):
            primary_age = inputs.primary_age + year_index
            portfolio_return = trial_returns[year_index]
            for bucket in list(balances):
                bucket_weights = bucket_weight_vectors.get(bucket)
                annual_return = (
                    float(samples[trial, year_index] @ bucket_weights)
                    if bucket_weights is not None
                    else cash_return
                    if bucket == "cash"
                    else portfolio_return
                )
                balances[bucket] = max(0.0, balances[bucket] * (1.0 + annual_return))
            if year_index > 0:
                # The bridge is tracked in real dollars, so a portfolio-grown
                # bridge converts the sampled nominal return to real.
                bridge_balance *= 1.0 + (
                    (1.0 + portfolio_return) / (1.0 + inputs.inflation_rate) - 1.0
                    if bridge_rides_portfolio
                    else cfg.bridge.real_return
                )
            if primary_age < household_retirement_age and inputs.annual_contribution > 0:
                balances[contribution_bucket] = balances.get(contribution_bucket, 0.0) + inputs.annual_contribution

            inflation_factor, spouse_age, income_components = year_contexts[year_index]
            liquidity_real = liquidity_by_year.get(inputs.as_of_date.year + year_index, 0.0)
            if liquidity_real > 0:
                balances["taxable"] = balances.get("taxable", 0.0) + liquidity_real * inflation_factor
            income = income_components["total"]

            wy = None
            # Partial-retirement window years fund the spend-minus-net gap
            # through the seam; overwritten when the engine runs.
            spending = partial_gap_nominal[year_index]
            if primary_age >= household_retirement_age:
                portfolio_bal_real = sum(balances.values()) / inflation_factor
                if guardrails_state is not None:
                    guardrails_capacity_and_update(
                        portfolio_bal_real,
                        guardrails_state,
                        prev_return_negative,
                        inputs.inflation_rate,
                    )
                wy = step_year(
                    cfg,
                    year_index=year_index,
                    age=primary_age,
                    portfolio_bal_real=portfolio_bal_real,
                    bridge_bal_real=bridge_balance,
                    guaranteed_real=income / inflation_factor,
                    strategy_state=guardrails_state,
                )
                bridge_balance = wy.bridge_balance_end
                spending = wy.portfolio_draw * inflation_factor + income + college_overflow_nominal[year_index]
                discretionary_paths[trial, year_index] = wy.discretionary_funded
                if (
                    first_warning_year[trial] < 0
                    and wy.discretionary_target > 0.01
                    and wy.discretionary_funded <= 0.01
                ):
                    first_warning_year[trial] = year_index

            if (
                wy is None
                and primary_age < RMD_START_AGE
                and partial_gap_nominal[year_index] <= 0.0
            ):
                # Pre-retirement, pre-RMD, no partial-window gap: no spending
                # need and no forced distribution — the tax seam is a
                # guaranteed no-op (tax on income alone never exceeds the
                # income), so skip its federal-stack probes entirely.
                failed = False
            else:
                # ACA true-up (premium years): reprice the subsidy off the
                # trial's realized MAGI and re-run the seam with the delta
                # vs the planning net already in the engine floor. Cliff
                # trials pay the full gross premium here.
                aca_plan = (
                    aca_plans[year_index]
                    if aca_plans is not None
                    and wy is not None
                    and aca_plans[year_index].gross_premium > 0
                    else None
                )
                pre_seam_balances = dict(balances) if aca_plan is not None else None
                outcome = _apply_tax_aware_withdrawals(
                    balances,
                    spending=spending,
                    income_components=income_components,
                    primary_age=primary_age,
                    spouse_age=spouse_age,
                    inflation_factor=inflation_factor,
                    tax_context=tax_context,
                    gain_ratio=gain_ratio,
                    external_taxed_income=partial_wages_nominal[year_index],
                )
                if aca_plan is not None and pre_seam_balances is not None:
                    credit = premium_tax_credit_annual(
                        magi_annual=_aca_magi_nominal(outcome, income_components, gain_ratio)
                        / inflation_factor,
                        household_size=aca_plan.household_size,
                        benchmark_annual=aca_plan.benchmark_premium,
                    ).credit
                    actual_net = max(0.0, aca_plan.gross_premium - credit) + aca_plan.oop
                    delta = actual_net - aca_plan.planning_net
                    if abs(delta) > 0.005:
                        balances = pre_seam_balances
                        spending += delta * inflation_factor
                        outcome = _apply_tax_aware_withdrawals(
                            balances,
                            spending=spending,
                            income_components=income_components,
                            primary_age=primary_age,
                            spouse_age=spouse_age,
                            inflation_factor=inflation_factor,
                            tax_context=tax_context,
                            gain_ratio=gain_ratio,
                        )
                if wy is not None or partial_gap_nominal[year_index] > 0.0:
                    gross_withdrawal = sum(outcome.withdrawals.values())
                    surplus_net = (
                        income + gross_withdrawal - outcome.tax_estimate - outcome.penalty_estimate - spending
                    )
                    if surplus_net > 0.01:
                        balances["taxable"] = balances.get("taxable", 0.0) + surplus_net
                failed = outcome.shortfall > 1.0 or (wy is not None and wy.failed)
                penalty_real[trial] += outcome.penalty_estimate / inflation_factor
                if failed:
                    years_short[trial] += 1
                    floor_gap_real[trial] += outcome.shortfall / inflation_factor
            if failed and failure_year[trial] < 0:
                failure_year[trial] = year_index
            prev_return_negative = portfolio_return < 0
            # The bridge sleeve is real household money — report it (nominal)
            # so percentile bands and ending balances don't show a phantom
            # drop equal to the carve. Engine semantics are unchanged.
            yearly_balances[trial, year_index] = max(
                0.0, sum(balances.values()) + bridge_balance * inflation_factor
            )

    success_count = int(np.sum(failure_year < 0))
    success_probability = success_count / trials
    median_ending = float(np.median(yearly_balances[:, -1]))
    sor_mask = (failure_year >= 0) & (failure_year < SEQUENCE_OF_RETURNS_HORIZON)
    sequence_risk = float(np.sum(sor_mask)) / trials

    percentiles: dict[str, float] = {}
    paths: dict[str, list[float]] = {}
    for label, q in PERCENTILE_KEYS:
        col = np.percentile(yearly_balances, q, axis=0)
        percentiles[label] = float(col[-1])
        paths[label] = [float(v) for v in col]

    failure_distribution: dict[str, int] = {}
    failures = failure_year[failure_year >= 0]
    if failures.size:
        bins = np.bincount(failures, minlength=inputs.horizon_years)
        for idx, count in enumerate(bins):
            if count:
                failure_distribution[f"year_{idx + 1}"] = int(count)

    median_discretionary = np.median(discretionary_paths, axis=0)

    # Beyond-success-% framing. The bridge carve keeps the start total intact
    # (carved sleeve + remaining buckets == original balances at t=0 real).
    failed_mask = failure_year >= 0
    failed_count = int(np.sum(failed_mask))
    start_balance_real = float(sum(starting_balances.values()) + bridge_initial)
    final_inflation = (1.0 + inputs.inflation_rate) ** (inputs.horizon_years - 1)
    end_above_start_share = float(
        np.mean(yearly_balances[:, -1] / final_inflation >= start_balance_real)
    )
    penalty_mask = penalty_real > 1.0
    framing: dict[str, Any] = {
        "median_years_short": None,
        "median_floor_gap_real": None,
        "tail_floor_gap_real": None,
        "median_warning_years": None,
        "penalty_trials_share": round(float(np.mean(penalty_mask)), 6),
        "median_penalty_paid_real": (
            round(float(np.median(penalty_real[penalty_mask])), 2)
            if bool(np.any(penalty_mask))
            else None
        ),
        "end_above_start_share": round(end_above_start_share, 6),
        "start_balance_real": round(start_balance_real, 2),
    }
    if failed_count:
        framing["median_years_short"] = round(float(np.median(years_short[failed_mask])), 1)
        framing["median_floor_gap_real"] = round(float(np.median(floor_gap_real[failed_mask])), 2)
        framing["tail_floor_gap_real"] = round(
            float(np.percentile(floor_gap_real[failed_mask], 90.0)), 2
        )
        # Warning window: years between the first fully-trimmed discretionary
        # year and the first floor miss. A failing year always trims to zero,
        # so the window is >= 0; trials with no discretionary configured have
        # no warning light at all and count as 0.
        fw = first_warning_year[failed_mask]
        fy = failure_year[failed_mask]
        warning = np.where((fw >= 0) & (fw <= fy), fy - fw, 0)
        framing["median_warning_years"] = round(float(np.median(warning)), 1)

    return SimulationOutputs(
        success_probability=round(success_probability, 6),
        median_ending_balance=round(median_ending, 2),
        sequence_of_returns_risk=round(sequence_risk, 6),
        percentiles={k: round(v, 2) for k, v in percentiles.items()},
        failure_year_distribution=failure_distribution,
        ending_balance_paths={k: [round(x, 2) for x in v] for k, v in paths.items()},
        median_discretionary_path=[round(float(v), 2) for v in median_discretionary],
        outcome_framing=framing,
    )


def _account_rule_explanations(
    buckets: tuple[RetirementAccountBucket, ...],
) -> tuple[RetirementAccountRule, ...]:
    """One concise rule card per bucket type present in the plan."""
    rules: list[RetirementAccountRule] = []
    seen: set[str] = set()
    for bucket in sorted(buckets, key=lambda b: b.withdrawal_priority):
        bucket_type = bucket.bucket_type
        if bucket_type in seen:
            continue
        seen.add(bucket_type)
        explanation = BUCKET_RULE_EXPLANATIONS.get(bucket_type)
        if explanation is None:
            continue
        rules.append(
            RetirementAccountRule(
                bucket_type=bucket_type,
                label=BUCKET_LABELS.get(bucket_type, bucket.label),
                tax_treatment=BUCKET_TAX_TREATMENT_LABELS.get(
                    bucket.tax_treatment, bucket.tax_treatment
                ),
                early_access=explanation["early_access"],
                rmd=explanation["rmd"],
            )
        )
    return tuple(rules)


def _tax_assumptions(
    context: FederalTaxContext,
    *,
    buckets: tuple[RetirementAccountBucket, ...] = (),
    inputs: RetirementInputs | None = None,
    gain_ratio_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    warnings = []
    if context.filing_status_source != "saved":
        warnings.append("Set filing status in saved assumptions to remove filing-status inference.")
    if context.state_tax_rate > 0:
        warnings.append("State tax is not included in the federal retirement drawdown tax estimate yet.")
    if any(bucket.bucket_type == "governmental_457b" for bucket in buckets):
        warnings.append(
            "Governmental 457(b) is modeled as penalty-free after the plan owner separates from service; "
            "confirm Pinellas plan distribution rules before relying on in-service access."
        )
    if inputs and inputs.social_security_payable_ratio < 1.0:
        percent = round(inputs.social_security_payable_ratio * 100)
        year = inputs.social_security_depletion_year or DEFAULT_SOCIAL_SECURITY_DEPLETION_YEAR
        warnings.append(f"Social Security is modeled at {percent}% of scheduled benefits starting in {year}.")
    capital_gains_zero_rate_limit, capital_gains_twenty_rate_threshold = LONG_TERM_CAPITAL_GAINS_BRACKETS_2026[
        context.filing_status
    ]
    lots_derived_gain_ratio = inputs is not None and inputs.taxable_gain_ratio is not None
    effective_gain_ratio = (
        inputs.taxable_gain_ratio
        if lots_derived_gain_ratio and inputs is not None
        else TAXABLE_WITHDRAWAL_GAIN_RATIO
    )
    if lots_derived_gain_ratio:
        gain_ratio_source = "tax_lots"
        gain_ratio_detail = (
            f"Embedded gain estimated from your taxable cost basis "
            f"({round(effective_gain_ratio * 100)}% of taxable withdrawals taxed as long-term gains)."
        )
    else:
        gain_ratio_source = "planning_assumption"
        gain_ratio_detail = (
            f"No taxable cost-basis lots found; assuming {round(effective_gain_ratio * 100)}% "
            "of each taxable withdrawal is a long-term gain."
        )
    return {
        "tax_year": FEDERAL_TAX_YEAR,
        "filing_status": context.filing_status,
        "filing_status_label": FILING_STATUS_LABELS[context.filing_status],
        "filing_status_source": context.filing_status_source,
        "standard_deduction": STANDARD_DEDUCTION_2026[context.filing_status],
        "additional_age_65_deduction": ADDITIONAL_STANDARD_DEDUCTION_65_2026[context.filing_status],
        "capital_gains_zero_rate_limit": capital_gains_zero_rate_limit,
        "capital_gains_twenty_rate_threshold": capital_gains_twenty_rate_threshold,
        "taxable_withdrawal_gain_ratio": round(effective_gain_ratio, 6),
        "taxable_withdrawal_gain_ratio_source": gain_ratio_source,
        "taxable_withdrawal_gain_ratio_detail": gain_ratio_detail,
        "taxable_cost_basis": (gain_ratio_meta or {}).get("cost_basis"),
        "taxable_market_value": (gain_ratio_meta or {}).get("market_value"),
        "state_tax_rate": context.state_tax_rate,
        "state_tax_source": context.state_tax_source,
        "withdrawal_order": list(DEFAULT_DRAWDOWN_ORDER),
        "withdrawal_order_label": "Cash, taxable brokerage, governmental 457(b), pre-tax, Roth, HSA, then other.",
        "governmental_457b_penalty_rate": 0.0,
        "pre_tax_early_withdrawal_penalty_rate": 0.10,
        "hsa_non_medical_penalty_rate_before_65": 0.20,
        "social_security_payable_ratio": inputs.social_security_payable_ratio if inputs else 1.0,
        "social_security_depletion_year": inputs.social_security_depletion_year if inputs else None,
        "method": (
            "Federal taxes are derived yearly from ordinary income, taxable Social Security, "
            "pre-tax/457(b) withdrawals, estimated taxable-brokerage gains, 2026 brackets, "
            "standard deduction, age-65 standard deduction, and the saved Social Security payable ratio."
        ),
        "manual_rate_used": False,
        "warnings": warnings,
    }


def _filing_status_from_profile(profile: Any, spouse_age: int | None) -> tuple[str, str]:
    raw = str(getattr(profile, "filing_status", "") or "").strip().lower()
    normalized = re.sub(r"[^a-z]+", "_", raw).strip("_")
    if normalized in {"married_filing_jointly", "married_jointly", "mfj", "joint"}:
        return "married_filing_jointly", "saved"
    if normalized in {"married_filing_separately", "married_separately", "mfs"}:
        return "married_filing_separately", "saved"
    if normalized in {"head_of_household", "hoh"}:
        return "head_of_household", "saved"
    if normalized in {"single"}:
        return "single", "saved"
    if spouse_age is not None:
        return "married_filing_jointly", "inferred_from_spouse"
    return "single", "default"


def _state_tax_rate_from_profile(profile: Any) -> float:
    state = str(getattr(profile, "state_of_residence", "") or "").strip().upper()
    if state in NO_STATE_INCOME_TAX_STATES:
        return 0.0
    value = getattr(profile, "marginal_state_tax_rate", None)
    if value is None:
        return 0.0
    parsed = float(value or 0.0)
    if parsed > 1:
        parsed /= 100.0
    return max(0.0, min(parsed, 0.2))


def _state_tax_source_from_profile(profile: Any) -> str:
    state = str(getattr(profile, "state_of_residence", "") or "").strip().upper()
    if state in NO_STATE_INCOME_TAX_STATES:
        return f"{state}_no_state_income_tax"
    return "saved_marginal_state_tax_rate" if getattr(profile, "marginal_state_tax_rate", None) is not None else "not_set"


def _social_security_payable_ratio(value: float | None) -> float:
    if value is None:
        return DEFAULT_SOCIAL_SECURITY_PAYABLE_RATIO
    parsed = float(value or 0.0)
    if parsed > 1.0:
        parsed /= 100.0
    return max(0.0, min(parsed, 1.0))


def _spouse_retirement_primary_age(inputs: RetirementInputs) -> int | None:
    if inputs.spouse_retirement_age is None or inputs.spouse_age is None:
        return None
    return inputs.primary_age + max(0, inputs.spouse_retirement_age - inputs.spouse_age)


def _household_retirement_primary_age(inputs: RetirementInputs) -> int:
    spouse_primary_age = _spouse_retirement_primary_age(inputs)
    if spouse_primary_age is None:
        return inputs.retirement_age
    return max(inputs.retirement_age, spouse_primary_age)


def _partial_year_amounts_real(
    inputs: RetirementInputs, primary_age: int
) -> tuple[float, float, float] | None:
    """(spend, spouse net, spouse gross) annual REAL $ for a partial-retirement year.

    A partial-retirement year is one where the primary has retired but the
    spouse is still working: ``spouse_net_monthly_income`` gates the feature
    (None == off == legacy behavior). Spend falls back to ``annual_expenses``
    when no window-specific override is set.
    """
    if inputs.spouse_net_monthly_income is None:
        return None
    if not inputs.retirement_age <= primary_age < _household_retirement_primary_age(inputs):
        return None
    spend = (
        inputs.partial_retirement_monthly_spend * 12.0
        if inputs.partial_retirement_monthly_spend is not None
        else inputs.annual_expenses
    )
    net = inputs.spouse_net_monthly_income * 12.0
    gross = inputs.spouse_gross_annual_income or 0.0
    return spend, net, gross


def _contribution_bucket(balances: dict[str, float]) -> str:
    for bucket in ("pre_tax", "governmental_457b", "taxable", "cash", "roth"):
        if balances.get(bucket, 0.0) > 0:
            return bucket
    return "taxable"


def _income_components_for_age(
    income_sources: tuple[RetirementIncomeSource, ...],
    primary_age: int,
    *,
    inflation_factor: float,
    calendar_year: int,
    social_security_payable_ratio: float,
    social_security_depletion_year: int | None,
) -> dict[str, float]:
    total = 0.0
    social_security = 0.0
    ordinary = 0.0
    for source in income_sources:
        if primary_age < source.start_age:
            continue
        annual = source.monthly_amount * 12.0
        amount = annual * inflation_factor if source.inflation_adjusted else annual
        if (source.source_type or "").lower() == "social_security":
            if (
                social_security_depletion_year is not None
                and calendar_year >= social_security_depletion_year
            ):
                amount *= social_security_payable_ratio
            social_security += amount
        else:
            ordinary += amount
        total += amount
    return {"total": total, "social_security": social_security, "ordinary": ordinary}


def _taxable_social_security(
    *,
    filing_status: str,
    social_security_benefits: float,
    other_income: float,
) -> float:
    if social_security_benefits <= 0:
        return 0.0
    if filing_status == "married_filing_jointly":
        base_amount = 32_000.0
        adjusted_base = 44_000.0
    elif filing_status == "married_filing_separately":
        base_amount = 0.0
        adjusted_base = 0.0
    else:
        base_amount = 25_000.0
        adjusted_base = 34_000.0
    provisional_income = other_income + social_security_benefits * 0.5
    if provisional_income <= base_amount:
        return 0.0
    if provisional_income <= adjusted_base:
        return min(social_security_benefits * 0.5, (provisional_income - base_amount) * 0.5)
    lower_tier_taxable = min(social_security_benefits * 0.5, (adjusted_base - base_amount) * 0.5)
    return min(
        social_security_benefits * 0.85,
        lower_tier_taxable + (provisional_income - adjusted_base) * 0.85,
    )


def _federal_tax_estimate(
    context: FederalTaxContext,
    *,
    ordinary_income: float,
    social_security_benefits: float,
    long_term_capital_gains: float,
    primary_age: int,
    spouse_age: int | None,
    inflation_factor: float,
) -> float:
    status = context.filing_status
    taxable_social_security = _taxable_social_security(
        filing_status=status,
        social_security_benefits=social_security_benefits,
        other_income=ordinary_income + long_term_capital_gains,
    )
    gross_ordinary = ordinary_income + taxable_social_security
    standard_deduction = STANDARD_DEDUCTION_2026[status] * inflation_factor
    age_65_count = int(primary_age >= 65)
    if status == "married_filing_jointly" and spouse_age is not None:
        age_65_count += int(spouse_age >= 65)
    additional_deduction = ADDITIONAL_STANDARD_DEDUCTION_65_2026[status] * inflation_factor * age_65_count
    total_deduction = standard_deduction + additional_deduction
    taxable_ordinary = max(0.0, gross_ordinary - total_deduction)
    deduction_remaining = max(0.0, total_deduction - gross_ordinary)
    taxable_capital_gains = max(0.0, long_term_capital_gains - deduction_remaining)
    ordinary_tax = _progressive_tax(
        taxable_ordinary,
        ORDINARY_TAX_BRACKETS_2026[status],
        inflation_factor=inflation_factor,
    )
    capital_gains_tax = _long_term_capital_gains_tax(
        filing_status=status,
        taxable_ordinary=taxable_ordinary,
        taxable_capital_gains=taxable_capital_gains,
        inflation_factor=inflation_factor,
    )
    niit = _niit_tax(
        filing_status=status,
        modified_agi=gross_ordinary + long_term_capital_gains,
        net_investment_income=long_term_capital_gains,
        inflation_factor=inflation_factor,
    )
    return max(0.0, ordinary_tax + capital_gains_tax + niit)


def _progressive_tax(
    taxable_income: float,
    brackets: tuple[tuple[float, float], ...],
    *,
    inflation_factor: float,
) -> float:
    tax = 0.0
    lower = 0.0
    for upper, rate in brackets:
        scaled_upper = upper if upper == float("inf") else upper * inflation_factor
        if taxable_income <= lower:
            break
        taxed = min(taxable_income, scaled_upper) - lower
        if taxed > 0:
            tax += taxed * rate
        lower = scaled_upper
    return tax


def _long_term_capital_gains_tax(
    *,
    filing_status: str,
    taxable_ordinary: float,
    taxable_capital_gains: float,
    inflation_factor: float,
) -> float:
    if taxable_capital_gains <= 0:
        return 0.0
    zero_rate_limit, twenty_rate_limit = LONG_TERM_CAPITAL_GAINS_BRACKETS_2026[filing_status]
    zero_rate_limit *= inflation_factor
    twenty_rate_limit *= inflation_factor
    remaining = taxable_capital_gains
    zero_rate_amount = min(remaining, max(0.0, zero_rate_limit - taxable_ordinary))
    remaining -= zero_rate_amount
    fifteen_rate_amount = min(remaining, max(0.0, twenty_rate_limit - max(taxable_ordinary, zero_rate_limit)))
    remaining -= fifteen_rate_amount
    return fifteen_rate_amount * 0.15 + max(0.0, remaining) * 0.20


def _niit_tax(
    *,
    filing_status: str,
    modified_agi: float,
    net_investment_income: float,
    inflation_factor: float,
) -> float:
    threshold = NIIT_THRESHOLDS_2026[filing_status] * inflation_factor
    return min(max(0.0, net_investment_income), max(0.0, modified_agi - threshold)) * 0.038


def _append_preview_social_security(
    inputs: RetirementInputs,
    *,
    primary_monthly: float | None,
    spouse_monthly: float | None,
    primary_annual_earnings: float | None,
    spouse_annual_earnings: float | None,
    primary_start_age: int | None,
    spouse_start_age: int | None,
) -> RetirementInputs:
    primary_claim_age = primary_start_age or SSA_FULL_RETIREMENT_AGE
    spouse_claim_age = spouse_start_age or SSA_FULL_RETIREMENT_AGE
    estimated_primary_monthly = primary_monthly or _estimate_social_security_monthly(
        primary_annual_earnings,
        claim_age=primary_claim_age,
        stop_work_age=inputs.retirement_age,
    )
    estimated_spouse_monthly = spouse_monthly or _estimate_social_security_monthly(
        spouse_annual_earnings,
        claim_age=spouse_claim_age,
        stop_work_age=inputs.spouse_retirement_age or inputs.retirement_age,
    )
    provided = any(
        value is not None and value > 0
        for value in (estimated_primary_monthly, estimated_spouse_monthly)
    )
    if not provided:
        return inputs

    sources = [
        source
        for source in inputs.income_sources
        if (source.source_type or "").lower() != "social_security"
    ]
    if estimated_primary_monthly is not None and estimated_primary_monthly > 0:
        sources.append(
            RetirementIncomeSource(
                label="Social Security - primary",
                source_type="social_security",
                owner_name="primary",
                start_age=primary_claim_age,
                monthly_amount=estimated_primary_monthly,
                inflation_adjusted=True,
            )
        )
    if (
        estimated_spouse_monthly is not None
        and estimated_spouse_monthly > 0
        and inputs.spouse_age is not None
    ):
        primary_timeline_age = inputs.primary_age + max(0, spouse_claim_age - inputs.spouse_age)
        sources.append(
            RetirementIncomeSource(
                label=f"Social Security - spouse at {spouse_claim_age}",
                source_type="social_security",
                owner_name="spouse",
                start_age=primary_timeline_age,
                monthly_amount=estimated_spouse_monthly,
                inflation_adjusted=True,
            )
        )
    return inputs.model_copy(update={"income_sources": tuple(sources)})


def _estimate_social_security_monthly(
    annual_earnings: float | None,
    *,
    claim_age: int,
    stop_work_age: int | None = None,
) -> float | None:
    if annual_earnings is None or annual_earnings <= 0:
        return None
    aime = min(float(annual_earnings), SSA_2026_TAXABLE_WAGE_BASE) / 12.0
    if stop_work_age is not None:
        # AIME averages the best 35 years; an early retiree fills the
        # missing years with zeros. Career assumed to start at 22, and
        # earnings after the claim age never enter the average.
        years_worked = max(0.0, float(min(stop_work_age, claim_age) - SSA_ASSUMED_CAREER_START_AGE))
        aime *= min(years_worked, 35.0) / 35.0
    pia = (
        min(aime, SSA_2026_FIRST_BEND_POINT) * 0.90
        + max(min(aime, SSA_2026_SECOND_BEND_POINT) - SSA_2026_FIRST_BEND_POINT, 0.0) * 0.32
        + max(aime - SSA_2026_SECOND_BEND_POINT, 0.0) * 0.15
    )
    if claim_age < SSA_FULL_RETIREMENT_AGE:
        months_early = max(0, (SSA_FULL_RETIREMENT_AGE - claim_age) * 12)
        first_36 = min(months_early, 36)
        extra = max(months_early - 36, 0)
        factor = 1.0 - (first_36 * (5.0 / 900.0)) - (extra * (5.0 / 1200.0))
    else:
        months_late = min(max(0, (claim_age - SSA_FULL_RETIREMENT_AGE) * 12), 36)
        factor = 1.0 + months_late * (2.0 / 300.0)
    return round(max(pia * factor, 0.0), 2)


def _summarize_holdings_coverage(
    rows: list[RetirementHoldingsCoverageAccount],
) -> RetirementHoldingsCoverage:
    if not rows:
        return RetirementHoldingsCoverage()
    total_value = round(sum(row.current_value for row in rows), 2)
    exact_value = round(sum(row.exact_value for row in rows), 2)
    inferred_value = round(sum(row.inferred_value for row in rows), 2)
    cash_value = round(sum(row.cash_value for row in rows), 2)
    exact_share = round(exact_value / total_value, 6) if total_value > 0 else 0.0
    if inferred_value <= 0.01:
        status = "exact"
        label = "Exact holdings"
        detail = "All modeled account value has exact holdings or cash coverage."
    elif exact_value > 0:
        status = "partial"
        label = "Partial holdings"
        detail = "Some account value has exact holdings or cash; the rest uses account-level assumptions."
    else:
        status = "account_value_only"
        label = "Account value only"
        detail = "No exact holdings are linked; allocation uses account-level assumptions."
    return RetirementHoldingsCoverage(
        status=status,
        label=label,
        detail=detail,
        total_value=total_value,
        exact_value=exact_value,
        inferred_value=inferred_value,
        cash_value=cash_value,
        exact_share=exact_share,
        accounts=tuple(rows),
    )


def _class_values_from_holdings(
    ac_mod: Any,
    classifier: Any,
    holdings: list[dict[str, Any]],
) -> dict[str, float]:
    if not holdings:
        return {}
    bucketed = classifier.classify_value(
        ac_mod.HoldingValue(symbol=row["symbol"], value=row["current_value"])
        for row in holdings
        if float(row.get("current_value") or 0.0) > 0
    )
    values = dict(bucketed.by_class)
    unclassified = float(values.pop("unclassified", 0.0) or 0.0)
    if unclassified > 0:
        values["us_equity"] = values.get("us_equity", 0.0) + unclassified
    return {
        asset_class: float(value or 0.0)
        for asset_class, value in values.items()
        if float(value or 0.0) > 0
    }


def _values_to_allocation(values: dict[str, float], cma: dict[str, Any]) -> dict[str, float]:
    return _normalized_asset_allocation(values, cma)


def _non_cash_fallback_allocation(
    allocation: dict[str, float],
    cma: dict[str, Any],
) -> dict[str, float]:
    cleaned = {
        asset_class: float(weight or 0.0)
        for asset_class, weight in allocation.items()
        if asset_class != "cash" and float(weight or 0.0) > 0
    }
    if not cleaned:
        cleaned = {"us_equity": 1.0}
    return _normalized_asset_allocation(cleaned, cma)


def _account_allocation_status(
    *,
    exact_value: float,
    inferred_value: float,
    priced_position_count: int,
) -> tuple[str, str, str]:
    if inferred_value <= 0.01 and exact_value > 0:
        return (
            "exact_allocation",
            "Exact allocation",
            (
                f"{priced_position_count} priced position"
                f"{'s' if priced_position_count != 1 else ''} drive this account allocation."
            ),
        )
    if exact_value > 0:
        return (
            "partial_allocation",
            "Partial allocation",
            (
                f"{priced_position_count} priced position"
                f"{'s' if priced_position_count != 1 else ''} plus account-level fallback assumptions."
            ),
        )
    return (
        "account_value_only",
        "Account value only",
        "No exact holdings are linked; allocation uses account-level fallback assumptions.",
    )


def _summarize_account_allocation_coverage(
    rows: list[RetirementAccountAllocationAccount],
    cma: dict[str, Any],
) -> RetirementAccountAllocationCoverage:
    if not rows:
        return RetirementAccountAllocationCoverage()
    total_value = round(sum(row.current_value for row in rows), 2)
    exact_value = round(sum(row.exact_value for row in rows), 2)
    inferred_value = round(sum(row.inferred_value for row in rows), 2)
    cash_value = round(sum(row.cash_value for row in rows), 2)
    exact_share = round(exact_value / total_value, 6) if total_value > 0 else 0.0
    values_by_class: dict[str, float] = {}
    for row in rows:
        for asset_class, weight in row.allocation.items():
            values_by_class[asset_class] = values_by_class.get(asset_class, 0.0) + (
                row.current_value * float(weight or 0.0)
            )
    if inferred_value <= 0.01:
        status = "exact"
        label = "Exact account allocation"
        detail = "All modeled account allocation comes from exact holdings or cash."
    elif exact_value > 0:
        status = "partial"
        label = "Partial account allocation"
        detail = "Exact holdings and cash are used first; account-value-only balances use fallback assumptions."
    else:
        status = "account_value_only"
        label = "Account-value-only allocation"
        detail = "No exact holdings are linked; all allocation uses account-level fallback assumptions."
    return RetirementAccountAllocationCoverage(
        status=status,
        label=label,
        detail=detail,
        total_value=total_value,
        exact_value=exact_value,
        inferred_value=inferred_value,
        cash_value=cash_value,
        exact_share=exact_share,
        asset_allocation=_values_to_allocation(values_by_class, cma),
        accounts=tuple(rows),
    )


def _asset_class_label(asset_class: str) -> str:
    labels = {
        "us_equity": "US stocks",
        "intl_equity": "international stocks",
        "bonds": "bonds",
        "cash": "cash",
        "real_estate": "real estate",
        "alts": "alternatives",
        "unclassified": "unclassified assets",
    }
    return labels.get(asset_class, asset_class.replace("_", " "))


def _strategy_bucket_for_asset_class(asset_class: str) -> str:
    if asset_class == "cash":
        return "now"
    if asset_class == "bonds":
        return "soon"
    return "later"


def _target_ramp(years_to_retirement: float, start_years: float) -> float:
    if years_to_retirement <= 0:
        return 1.0
    if start_years <= 0:
        return 1.0
    # Start a visible glide path at the boundary year instead of waiting
    # until just inside it: 5y-to-go carries 1/5 of the cash target, 15y
    # carries 1/15 of the stability target.
    return max(0.0, min((start_years - years_to_retirement + 1.0) / start_years, 1.0))


def _real_portfolio_need(row: RetirementDrawdownYear, inflation_rate: float) -> float:
    inflation_factor = (1.0 + inflation_rate) ** row.year_index
    gross_real = row.gross_withdrawal / inflation_factor if inflation_factor > 0 else row.gross_withdrawal
    return max(0.0, gross_real + row.bridge_draw)


def _strategy_status(
    *,
    current_value: float,
    target_value: float,
    total_value: float,
) -> tuple[str, str, str]:
    tolerance = max(1_000.0, target_value * 0.10, total_value * 0.01)
    gap = current_value - target_value
    if target_value <= 0.01:
        if current_value <= tolerance:
            return "aligned", "Not needed yet", "No current target under this retirement timeline."
        return (
            "overfilled",
            "Above target",
            f"Redirect about ${abs(gap):,.0f} toward buckets with current targets.",
        )
    if current_value <= 0.01:
        return "empty", "Empty", f"Add about ${target_value:,.0f}."
    if gap < -tolerance:
        return "underfilled", "Needs funding", f"Increase by about ${abs(gap):,.0f}."
    if gap > tolerance:
        return "overfilled", "Above target", f"Decrease by about ${abs(gap):,.0f}."
    return "aligned", "Aligned", "Within the strategy band."


def _bucket_strategy_current_values(
    holdings: tuple[RetirementBucketStrategyHolding, ...],
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    values = {"now": 0.0, "soon": 0.0, "later": 0.0}
    allocation_values: dict[str, dict[str, float]] = {
        "now": {},
        "soon": {},
        "later": {},
    }
    for holding in holdings:
        bucket_id = _strategy_bucket_for_asset_class(holding.asset_class)
        value = float(holding.current_value or 0.0)
        values[bucket_id] += value
        allocation_values[bucket_id][holding.asset_class] = (
            allocation_values[bucket_id].get(holding.asset_class, 0.0) + value
        )
    return values, allocation_values


def _build_retirement_bucket_strategy(
    inputs: RetirementInputs,
    *,
    drawdown: list[RetirementDrawdownYear],
    account_allocation_coverage: RetirementAccountAllocationCoverage,
    holdings: tuple[RetirementBucketStrategyHolding, ...],
) -> RetirementBucketStrategy:
    total = round(account_allocation_coverage.total_value or inputs.portfolio_value, 2)
    retirement_age = _household_retirement_primary_age(inputs)
    years_to_retirement = max(0.0, float(retirement_age - inputs.primary_age))
    if total <= 0:
        return RetirementBucketStrategy(
            retirement_age=retirement_age,
            years_to_retirement=round(years_to_retirement, 1),
        )

    retirement_rows = [row for row in drawdown if row.primary_age >= retirement_age]
    real_needs = [
        _real_portfolio_need(row, inputs.inflation_rate)
        for row in retirement_rows[:6]
    ]
    first_year_need = next((need for need in real_needs if need > 0.01), 0.0)
    if first_year_need <= 0.01 and inputs.annual_expenses > 0:
        first_year_need = inputs.annual_expenses
    annual_need = first_year_need
    soon_full_target = sum(real_needs[1:6])
    if soon_full_target <= 0.01 and annual_need > 0:
        soon_full_target = annual_need * 5.0

    cash_ramp = _target_ramp(years_to_retirement, 5.0)
    stable_ramp = _target_ramp(years_to_retirement, 15.0)
    now_target = min(total, max(0.0, annual_need * cash_ramp))
    soon_target = min(max(0.0, total - now_target), max(0.0, soon_full_target * stable_ramp))
    later_target = max(0.0, total - now_target - soon_target)
    targets = {
        "now": round(now_target, 2),
        "soon": round(soon_target, 2),
        "later": round(later_target, 2),
    }
    target_years = {
        "now": round(cash_ramp, 2),
        "soon": round(5.0 * stable_ramp, 2),
        "later": 0.0,
    }
    current_values, allocation_values = _bucket_strategy_current_values(holdings)
    holdings_by_bucket: dict[str, list[RetirementBucketStrategyHolding]] = {
        "now": [],
        "soon": [],
        "later": [],
    }
    for holding in holdings:
        holdings_by_bucket[_strategy_bucket_for_asset_class(holding.asset_class)].append(holding)

    buckets: list[RetirementBucketStrategyBucket] = []
    rebalance_actions: list[str] = []
    for bucket_id in ("now", "soon", "later"):
        current_value = round(current_values[bucket_id], 2)
        target_value = targets[bucket_id]
        status, label, action = _strategy_status(
            current_value=current_value,
            target_value=target_value,
            total_value=total,
        )
        if status in {"underfilled", "overfilled", "empty"} and target_value > 0.01:
            rebalance_actions.append(f"{STRATEGY_BUCKET_LABELS[bucket_id]}: {action}")
        bucket_holdings = tuple(
            holding.model_copy(
                update={
                    "share_of_bucket": (
                        round(holding.current_value / current_value, 6)
                        if current_value > 0
                        else 0.0
                    )
                }
            )
            for holding in sorted(
                holdings_by_bucket[bucket_id],
                key=lambda row: row.current_value,
                reverse=True,
            )
        )
        allocation_total = sum(allocation_values[bucket_id].values())
        asset_allocation = {
            asset_class: round(value / allocation_total, 6)
            for asset_class, value in sorted(allocation_values[bucket_id].items())
            if allocation_total > 0 and value > 0
        }
        buckets.append(
            RetirementBucketStrategyBucket(
                bucket_id=bucket_id,
                label=STRATEGY_BUCKET_LABELS[bucket_id],
                time_horizon=STRATEGY_BUCKET_HORIZONS[bucket_id],
                purpose=STRATEGY_BUCKET_PURPOSES[bucket_id],
                current_value=current_value,
                target_value=target_value,
                target_years=target_years[bucket_id],
                current_share=round(current_value / total, 6) if total > 0 else 0.0,
                target_share=round(target_value / total, 6) if total > 0 else 0.0,
                fill_ratio=round(current_value / target_value, 6) if target_value > 0 else 0.0,
                gap_value=round(current_value - target_value, 2),
                status=status,
                status_label=label,
                action=action,
                asset_allocation=asset_allocation,
                holdings=bucket_holdings,
            )
        )

    diff_total = sum(abs(bucket.current_value - bucket.target_value) for bucket in buckets)
    alignment_score = max(0.0, min(1.0, 1.0 - diff_total / (2.0 * total)))
    priority_buckets = [bucket for bucket in buckets if bucket.bucket_id in {"now", "soon"}]
    if any(bucket.status in {"underfilled", "empty"} for bucket in priority_buckets):
        overall_status = "underfilled"
        status_label = "Needs bucket funding"
    elif any(bucket.status == "overfilled" for bucket in priority_buckets):
        overall_status = "overfilled"
        status_label = "Bucket mix high in safe assets"
    elif alignment_score >= 0.9:
        overall_status = "aligned"
        status_label = "Aligned"
    else:
        overall_status = "underfilled"
        status_label = "Rebalance suggested"

    if years_to_retirement <= 0:
        timeline = "already in the modeled retirement window"
    else:
        timeline = f"{years_to_retirement:.0f} years from full household retirement"
    detail = (
        f"Targets are based on {timeline}, modeled portfolio withdrawals after scheduled income, "
        "and a simple 1-year cash / 5-year bond / remaining growth framework."
    )
    return RetirementBucketStrategy(
        status=overall_status,
        status_label=status_label,
        detail=detail,
        years_to_retirement=round(years_to_retirement, 1),
        retirement_age=retirement_age,
        annual_portfolio_need=round(annual_need, 2),
        target_total=total,
        current_total=round(sum(current_values.values()), 2),
        alignment_score=round(alignment_score, 6),
        buckets=tuple(buckets),
        rebalance_actions=tuple(rebalance_actions[:4]),
        methodology=(
            "Now: target up to one year of modeled portfolio withdrawals in cash, ramping in over the final five years before full household retirement.",
            "Soon: target up to five more years of modeled portfolio withdrawals in bonds, ramping in over the final fifteen years.",
            "Later: remaining assets stay in growth assets so long-horizon money is not dragged down by excess cash.",
            "Current bucket values come from exact holdings/cash where available; account-value-only balances inherit the modeled fallback allocation.",
        ),
        monte_carlo_detail=(
            "Success odds use the same current account buckets: cash earns the cash yield, "
            "and account buckets with known/inferred allocations use their bucket-specific return mix."
        ),
    )


def _bucket_return_allocations(
    coverage: RetirementAccountAllocationCoverage,
    cma: dict[str, Any],
) -> dict[str, dict[str, float]]:
    values: dict[str, dict[str, float]] = {}
    for account in coverage.accounts:
        if account.current_value <= 0:
            continue
        bucket_values = values.setdefault(account.bucket_type, {})
        for asset_class, weight in account.allocation.items():
            bucket_values[asset_class] = bucket_values.get(asset_class, 0.0) + (
                account.current_value * float(weight or 0.0)
            )
    return {
        bucket: _values_to_allocation(bucket_values, cma)
        for bucket, bucket_values in values.items()
        if sum(bucket_values.values()) > 0
    }


def _rmd_amount(pre_tax_balance: float, primary_age: int) -> float:
    if primary_age < RMD_START_AGE or pre_tax_balance <= 0:
        return 0.0
    # Exact IRS Uniform Lifetime Table divisor. The real table is convex, so a
    # linear slope-1 approximation over-states RMDs sharply with age (and would
    # force-liquidate the account near 100); use the published divisors.
    divisor = IRS_UNIFORM_LIFETIME_DIVISORS.get(
        min(primary_age, 120), IRS_UNIFORM_LIFETIME_DIVISORS[120]
    )
    return pre_tax_balance / divisor


def _early_withdrawal_penalty_rate(bucket: str, primary_age: int) -> float:
    # Integer ages compare against 59.5 so the modeled cutoff matches the rule
    # text shown to users ("before 59½") rather than a bare magic number.
    if bucket == "pre_tax" and primary_age < EARLY_WITHDRAWAL_PENALTY_AGE:
        return 0.10
    # Non-medical HSA use: 20% penalty before 65 (the penalty, unlike pre-tax,
    # ends at the Medicare age, not 59½).
    if bucket == "hsa" and primary_age < 65:
        return 0.20
    return 0.0


def _first_depletion_age(
    drawdown: list[RetirementDrawdownYear],
    retirement_age: int,
) -> int | None:
    for row in drawdown:
        if row.primary_age >= retirement_age and row.ending_balance <= 1.0:
            return row.primary_age
    return None


def _failure_age_distribution(
    sim: SimulationOutputs,
    inputs: RetirementInputs,
) -> dict[str, int]:
    """Re-key ``failure_year_distribution`` (``year_N``) by primary age."""
    out: dict[str, int] = {}
    for key, count in sim.failure_year_distribution.items():
        year_number = int(key.removeprefix("year_"))
        out[str(inputs.primary_age + year_number - 1)] = int(count)
    return out
