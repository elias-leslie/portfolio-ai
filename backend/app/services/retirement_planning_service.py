"""Retirement Monte Carlo planning service (F5 single source of truth).

Coordinates household and portfolio readers, the focused retirement
assumption/simulation/strategy modules, and persistence of ``ScenarioSummary``
and ``ScenarioResults`` rows. The router and CLI remain thin shims.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from importlib import import_module
from typing import Any

from app.portfolio.contracts.retirement import (
    RetirementACAConfig,
    RetirementACAPerson,
    RetirementAccountAllocationAccount,
    RetirementAccountAllocationCoverage,
    RetirementAccountBucket,
    RetirementBucketStrategy,
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
    WithdrawalConfig,
    WithdrawalHealthcarePoint,
)
from app.services._aca_estimator import (
    MEDICARE_DEFAULT_MONTHLY_PER_PERSON,
    household_premium_monthly,
    premium_tax_credit_annual,
)
from app.services._retirement_simulation import (
    SimulationOutputs,
)
from app.services._withdrawal_engine import (
    GuardrailsState,
    bridge_initial_size,
    guardrails_capacity_and_update,
    step_year,
)
from app.services.aca_marketplace_ingest_service import (
    DEFAULT_COUNTIES as DEFAULT_ACA_COUNTIES,
)
from app.services.retirement_plan_simulation import (
    _apply_tax_aware_withdrawals,
    _run_tax_aware_monte_carlo,
)
from app.services.retirement_planning_assumptions import (
    BUCKET_LABELS,
    BUCKET_TAX_TREATMENTS,
    BUCKET_WITHDRAWAL_PRIORITY,
    CASH_EQUIVALENT_SYMBOLS,
    DEFAULT_DRAWDOWN_ORDER,
    DEFAULT_HOLDING_INCOME_YIELDS,
    DEFAULT_HORIZON_YEARS,
    DEFAULT_LIST_LIMIT,
    DEFAULT_PREVIEW_TRIALS,
    DEFAULT_RETIREMENT_AGE,
    DEFAULT_SOCIAL_SECURITY_DEPLETION_YEAR,
    DEFAULT_SPAXX_CASH_YIELD_AS_OF,
    DEFAULT_SPAXX_CASH_YIELD_SOURCE,
    DEFAULT_TRIALS,
    INCOME_YIELD_BY_ASSET_CLASS,
    MAX_LIST_LIMIT,
    MAX_TRIALS,
    TAXABLE_WITHDRAWAL_GAIN_RATIO,
    FederalTaxContext,
    _aca_magi_nominal,
    _aca_year_plans,
    _account_rule_explanations,
    _aggregate_income_yield_freshness,
    _allocation_with_bucket_cash,
    _append_preview_social_security,
    _bucket_balances,
    _bucket_type,
    _carve_bridge_from_balances,
    _cash_yield,
    _cma_with_cash_yield,
    _coerce_json,
    _contribution_bucket,
    _early_withdrawal_penalty_rate,
    _effective_gain_ratio,
    _engine_withdrawal_config,
    _estimate_social_security_monthly,
    _federal_tax_estimate,
    _holding_field,
    _household_retirement_primary_age,
    _income_components_for_age,
    _income_tax_category,
    _income_tax_drag_estimate,
    _income_yield,
    _normalized_asset_allocation,
    _optional_yield,
    _partial_year_amounts_real,
    _real_guaranteed_income_fn,
    _rmd_amount,
    _social_security_payable_ratio,
    _split_members,
    _tax_assumptions,
    _tax_context_from_profile,
    _withdrawal_config_from_inputs,
    _withdrawal_config_from_profile,
    _withdrawal_summary,
    _yield_freshness,
    load_cma,
)
from app.services.retirement_planning_strategy import (
    _account_allocation_status,
    _asset_class_label,
    _bucket_return_allocations,
    _build_retirement_bucket_strategy,
    _class_values_from_holdings,
    _failure_age_distribution,
    _first_depletion_age,
    _non_cash_fallback_allocation,
    _summarize_account_allocation_coverage,
    _summarize_holdings_coverage,
    _values_to_allocation,
)

__all__ = [
    "DEFAULT_DRAWDOWN_ORDER",
    "DEFAULT_LIST_LIMIT",
    "DEFAULT_PREVIEW_TRIALS",
    "DEFAULT_SPAXX_CASH_YIELD_AS_OF",
    "DEFAULT_TRIALS",
    "MAX_LIST_LIMIT",
    "MAX_TRIALS",
    "TAXABLE_WITHDRAWAL_GAIN_RATIO",
    "RetirementPlanningService",
    "_account_rule_explanations",
    "_aggregate_income_yield_freshness",
    "_append_preview_social_security",
    "_early_withdrawal_penalty_rate",
    "_effective_gain_ratio",
    "_estimate_social_security_monthly",
    "_failure_age_distribution",
    "_federal_tax_estimate",
    "_rmd_amount",
    "_split_members",
    "_tax_assumptions",
    "_tax_context_from_profile",
    "_withdrawal_config_from_inputs",
    "_yield_freshness",
]

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
