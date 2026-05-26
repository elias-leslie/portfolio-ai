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
from dataclasses import dataclass
from datetime import UTC, date, datetime
from importlib import import_module
from pathlib import Path
from typing import Any

import yaml

from app.logging_config import get_logger
from app.portfolio.contracts.retirement import (
    RetirementAccountBucket,
    RetirementDrawdownYear,
    RetirementIncomeSource,
    RetirementInputs,
    RetirementLeverImpact,
    RetirementPreview,
    ScenarioResults,
    ScenarioSummary,
)
from app.services._retirement_simulation import (
    SimulationOutputs,
    income_streams_from_inputs,
    run_monte_carlo,
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
DEFAULT_DRAWDOWN_ORDER = (
    "cash",
    "taxable",
    "governmental_457b",
    "pre_tax",
    "hsa",
    "roth",
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
TAXABLE_WITHDRAWAL_GAIN_RATIO = 0.15
FEDERAL_TAX_YEAR = 2026
SSA_2026_TAXABLE_WAGE_BASE = 184_500.0
SSA_2026_FIRST_BEND_POINT = 1_286.0
SSA_2026_SECOND_BEND_POINT = 7_749.0
SSA_FULL_RETIREMENT_AGE = 67
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


def load_cma(path: Path | None = None) -> dict[str, Any]:
    """Load the long-term return estimates YAML.

    Module-level function so the simulation engine and tests can drive
    it without a service instance.
    """
    target = path or CMA_PATH
    with target.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


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
        retirement_age: int | None = None,
        horizon_years: int | None = None,
        inflation_rate: float | None = None,
        primary_age: int | None = None,
        spouse_age: int | None = None,
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

        return RetirementInputs(
            household_id=household_id,
            primary_age=primary,
            spouse_age=spouse,
            retirement_age=retirement_age or DEFAULT_RETIREMENT_AGE,
            horizon_years=horizon_years or DEFAULT_HORIZON_YEARS,
            annual_expenses=annual_expenses,
            annual_contribution=annual_contribution,
            portfolio_value=portfolio_value,
            asset_allocation=allocation,
            income_sources=income_sources,
            inflation_rate=(
                inflation_rate
                if inflation_rate is not None
                else float(self._cma.get("inflation_rate", 0.025))
            ),
            as_of_date=anchor,
        )

    def run_simulation(
        self,
        inputs: RetirementInputs,
        *,
        trials: int = DEFAULT_TRIALS,
        seed: int | None = None,
    ) -> SimulationOutputs:
        """Run the Monte Carlo without persisting; pure compute."""
        trials = max(1, min(trials, MAX_TRIALS))
        return run_monte_carlo(
            portfolio_value=inputs.portfolio_value,
            asset_allocation=inputs.asset_allocation,
            annual_expenses=inputs.annual_expenses,
            annual_contribution=inputs.annual_contribution,
            inflation_rate=inputs.inflation_rate,
            horizon_years=inputs.horizon_years,
            primary_age=inputs.primary_age,
            retirement_age=inputs.retirement_age,
            income_sources=income_streams_from_inputs(list(inputs.income_sources)),
            cma=self._cma,
            trials=trials,
            seed=seed,
        )

    def preview(
        self,
        household_id: str,
        *,
        annual_expenses: float | None = None,
        monthly_spend: float | None = None,
        retirement_age: int | None = None,
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

        inputs = self.build_inputs(
            household_id,
            annual_expenses=annual_expenses,
            annual_contribution=annual_contribution,
            retirement_age=retirement_age,
            horizon_years=horizon_years,
            inflation_rate=inflation_rate,
            primary_age=primary_age,
            spouse_age=spouse_age,
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
        bucket_total = round(sum(bucket.current_value for bucket in buckets), 2)
        if bucket_total > 0:
            inputs = inputs.model_copy(update={"portfolio_value": bucket_total})
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

        tax_context = _tax_context_from_profile(profile, inputs)
        sim = self.run_simulation(inputs, trials=trials, seed=seed)
        drawdown = self._drawdown_schedule(
            inputs,
            buckets=buckets,
            tax_context=tax_context,
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
            tax_assumptions=_tax_assumptions(tax_context),
            drawdown_schedule=tuple(drawdown),
            lever_impacts=self._lever_impacts(inputs, sim.success_probability, trials=trials, seed=seed),
            first_depletion_age=_first_depletion_age(drawdown, inputs.retirement_age),
            estimated_monthly_contribution_gap=_monthly_contribution_gap(
                inputs, annual_return=self._expected_return(inputs.asset_allocation)
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

    def _account_buckets_from_dashboard(self, dashboard: Any) -> tuple[RetirementAccountBucket, ...]:
        buckets: list[RetirementAccountBucket] = []
        for account in getattr(dashboard, "accounts", []) or []:
            asset_group = str(getattr(account, "asset_group", "") or "").lower()
            if asset_group in {"credit", "debt"}:
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

    def _drawdown_schedule(
        self,
        inputs: RetirementInputs,
        *,
        buckets: tuple[RetirementAccountBucket, ...],
        tax_context: FederalTaxContext | None = None,
        ordinary_tax_rate: float | None = None,
        capital_gains_rate: float | None = None,
    ) -> list[RetirementDrawdownYear]:
        del ordinary_tax_rate, capital_gains_rate  # kept for older direct unit-call compatibility
        tax_context = tax_context or _tax_context_from_profile(None, inputs)
        annual_return = self._expected_return(inputs.asset_allocation)
        balances = dict.fromkeys(DEFAULT_DRAWDOWN_ORDER, 0.0)
        for bucket in buckets:
            balances[bucket.bucket_type] = balances.get(bucket.bucket_type, 0.0) + bucket.current_value
        if sum(balances.values()) <= 0 and inputs.portfolio_value > 0:
            balances["taxable"] = inputs.portfolio_value

        contribution_bucket = _contribution_bucket(balances)
        rows: list[RetirementDrawdownYear] = []
        for year_index in range(inputs.horizon_years):
            primary_age = inputs.primary_age + year_index
            if year_index > 0:
                for bucket in list(balances):
                    balances[bucket] = max(0.0, balances[bucket] * (1.0 + annual_return))
                if primary_age < inputs.retirement_age and inputs.annual_contribution > 0:
                    balances[contribution_bucket] = balances.get(contribution_bucket, 0.0) + inputs.annual_contribution

            inflation_factor = (1.0 + inputs.inflation_rate) ** year_index
            spending = inputs.annual_expenses * inflation_factor if primary_age >= inputs.retirement_age else 0.0
            spouse_age = inputs.spouse_age + year_index if inputs.spouse_age is not None else None
            income_components = _income_components_for_age(
                inputs.income_sources,
                primary_age,
                inflation_factor=inflation_factor,
            )
            income = income_components["total"]
            withdrawals = dict.fromkeys(DEFAULT_DRAWDOWN_ORDER, 0.0)

            def tax_for(
                candidate_withdrawals: dict[str, float],
                *,
                income_components: dict[str, float] = income_components,
                primary_age: int = primary_age,
                spouse_age: int | None = spouse_age,
                inflation_factor: float = inflation_factor,
            ) -> float:
                ordinary_withdrawals = candidate_withdrawals.get("pre_tax", 0.0) + candidate_withdrawals.get(
                    "governmental_457b", 0.0
                )
                taxable_gains = candidate_withdrawals.get("taxable", 0.0) * TAXABLE_WITHDRAWAL_GAIN_RATIO
                return _federal_tax_estimate(
                    tax_context,
                    ordinary_income=income_components["ordinary"] + ordinary_withdrawals,
                    social_security_benefits=income_components["social_security"],
                    long_term_capital_gains=taxable_gains,
                    primary_age=primary_age,
                    spouse_age=spouse_age,
                    inflation_factor=inflation_factor,
                )

            def penalty_for(
                candidate_withdrawals: dict[str, float],
                *,
                primary_age: int = primary_age,
            ) -> float:
                return sum(
                    amount * _early_withdrawal_penalty_rate(bucket, primary_age)
                    for bucket, amount in candidate_withdrawals.items()
                )

            def surplus_cash(
                candidate_withdrawals: dict[str, float],
                *,
                income: float = income,
                spending: float = spending,
            ) -> float:
                gross_withdrawals = sum(candidate_withdrawals.values())
                return income + gross_withdrawals - tax_for(candidate_withdrawals) - penalty_for(candidate_withdrawals) - spending

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

            for bucket in DEFAULT_DRAWDOWN_ORDER:
                if surplus_cash(withdrawals) >= 0:
                    break
                available = balances.get(bucket, 0.0)
                if available <= 0:
                    continue
                candidate = dict(withdrawals)
                candidate[bucket] = candidate.get(bucket, 0.0) + available
                if surplus_cash(candidate) < 0:
                    gross = available
                else:
                    low = 0.0
                    high = available
                    for _ in range(24):
                        midpoint = (low + high) / 2.0
                        candidate = dict(withdrawals)
                        candidate[bucket] = candidate.get(bucket, 0.0) + midpoint
                        if surplus_cash(candidate) >= 0:
                            high = midpoint
                        else:
                            low = midpoint
                    gross = high
                balances[bucket] = available - gross
                withdrawals[bucket] += gross

            ending_balance = round(sum(balances.values()), 2)
            gross_withdrawal = round(sum(withdrawals.values()), 2)
            tax_estimate = tax_for(withdrawals)
            penalty_estimate = penalty_for(withdrawals)
            rows.append(
                RetirementDrawdownYear(
                    year_index=year_index,
                    calendar_year=inputs.as_of_date.year + year_index,
                    primary_age=primary_age,
                    spending_need=round(spending, 2),
                    income=round(income, 2),
                    gross_withdrawal=gross_withdrawal,
                    tax_estimate=round(tax_estimate, 2),
                    penalty_estimate=round(penalty_estimate, 2),
                    net_withdrawal=round(
                        max(0.0, gross_withdrawal - tax_estimate - penalty_estimate),
                        2,
                    ),
                    ending_balance=ending_balance,
                    rmd_amount=round(rmd_amount, 2),
                    rmd_applied=rmd_amount > 0,
                    withdrawals_by_bucket={k: round(v, 2) for k, v in withdrawals.items()},
                    balances_by_bucket={k: round(v, 2) for k, v in balances.items()},
                )
            )
        return rows

    def _expected_return(self, allocation: dict[str, float]) -> float:
        asset_classes = self._cma.get("asset_classes", {})
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

    def _lever_impacts(
        self,
        inputs: RetirementInputs,
        base_success_probability: float,
        *,
        trials: int,
        seed: int | None,
    ) -> tuple[RetirementLeverImpact, ...]:
        scenarios = [
            (
                "retire_later",
                "Retire 2 years later",
                f"Age {min(inputs.retirement_age + 2, 120)}",
                inputs.model_copy(update={"retirement_age": min(inputs.retirement_age + 2, 120)}),
            ),
            (
                "spend_less",
                "Spend 10% less",
                f"${inputs.annual_expenses * 0.9 / 12:,.0f}/mo",
                inputs.model_copy(update={"annual_expenses": round(inputs.annual_expenses * 0.9, 2)}),
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
            sim = self.run_simulation(lever_inputs, trials=lever_trials, seed=seed)
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


def _tax_assumptions(context: FederalTaxContext) -> dict[str, Any]:
    warnings = []
    if context.filing_status_source != "saved":
        warnings.append("Set filing status in saved assumptions to remove filing-status inference.")
    if context.state_tax_rate > 0:
        warnings.append("State tax is not included in the federal retirement drawdown tax estimate yet.")
    capital_gains_zero_rate_limit, capital_gains_twenty_rate_threshold = LONG_TERM_CAPITAL_GAINS_BRACKETS_2026[
        context.filing_status
    ]
    return {
        "tax_year": FEDERAL_TAX_YEAR,
        "filing_status": context.filing_status,
        "filing_status_label": FILING_STATUS_LABELS[context.filing_status],
        "filing_status_source": context.filing_status_source,
        "standard_deduction": STANDARD_DEDUCTION_2026[context.filing_status],
        "additional_age_65_deduction": ADDITIONAL_STANDARD_DEDUCTION_65_2026[context.filing_status],
        "capital_gains_zero_rate_limit": capital_gains_zero_rate_limit,
        "capital_gains_twenty_rate_threshold": capital_gains_twenty_rate_threshold,
        "taxable_withdrawal_gain_ratio": TAXABLE_WITHDRAWAL_GAIN_RATIO,
        "state_tax_rate": context.state_tax_rate,
        "state_tax_source": context.state_tax_source,
        "withdrawal_order": list(DEFAULT_DRAWDOWN_ORDER),
        "withdrawal_order_label": "Cash, taxable brokerage, governmental 457(b), pre-tax, HSA, Roth, then other.",
        "method": (
            "Federal taxes are derived yearly from ordinary income, taxable Social Security, "
            "pre-tax/457(b) withdrawals, estimated taxable-brokerage gains, 2026 brackets, "
            "standard deduction, and age-65 standard deduction."
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
) -> dict[str, float]:
    total = 0.0
    social_security = 0.0
    ordinary = 0.0
    for source in income_sources:
        if primary_age < source.start_age:
            continue
        annual = source.monthly_amount * 12.0
        amount = annual * inflation_factor if source.inflation_adjusted else annual
        total += amount
        if (source.source_type or "").lower() == "social_security":
            social_security += amount
        else:
            ordinary += amount
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
    )
    estimated_spouse_monthly = spouse_monthly or _estimate_social_security_monthly(
        spouse_annual_earnings,
        claim_age=spouse_claim_age,
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
) -> float | None:
    if annual_earnings is None or annual_earnings <= 0:
        return None
    aime = min(float(annual_earnings), SSA_2026_TAXABLE_WAGE_BASE) / 12.0
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


def _rmd_amount(pre_tax_balance: float, primary_age: int) -> float:
    if primary_age < RMD_START_AGE or pre_tax_balance <= 0:
        return 0.0
    # Lightweight planning estimate from the IRS Uniform Lifetime Table shape.
    divisor = max(27.4 - (primary_age - 72), 2.0)
    return pre_tax_balance / divisor


def _early_withdrawal_penalty_rate(bucket: str, primary_age: int) -> float:
    if bucket == "pre_tax" and primary_age < 60:
        return 0.10
    return 0.0


def _first_depletion_age(
    drawdown: list[RetirementDrawdownYear],
    retirement_age: int,
) -> int | None:
    for row in drawdown:
        if row.primary_age >= retirement_age and row.ending_balance <= 1.0:
            return row.primary_age
    return None


def _monthly_contribution_gap(
    inputs: RetirementInputs,
    *,
    annual_return: float,
) -> float:
    years_to_retire = max(inputs.retirement_age - inputs.primary_age, 1)
    target_assets = inputs.annual_expenses * 25.0
    growth = (1.0 + annual_return) ** years_to_retire
    if annual_return > 0:
        contribution_future_value = inputs.annual_contribution * ((growth - 1.0) / annual_return)
    else:
        contribution_future_value = inputs.annual_contribution * years_to_retire
    projected_assets = inputs.portfolio_value * growth + contribution_future_value
    gap = max(0.0, target_assets - projected_assets)
    return round(gap / (years_to_retire * 12.0), 2)
