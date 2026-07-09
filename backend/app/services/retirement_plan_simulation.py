"""Tax-aware Monte Carlo execution for retirement plans."""

from __future__ import annotations

from typing import Any

import numpy as np

from app.portfolio.contracts.retirement import RetirementAccountBucket, RetirementInputs
from app.services._aca_estimator import premium_tax_credit_annual
from app.services._retirement_simulation import (
    PERCENTILE_KEYS,
    SEQUENCE_OF_RETURNS_HORIZON,
    SimulationOutputs,
    _covariance_matrix,
    _normalize_allocation,
)
from app.services._withdrawal_engine import (
    GuardrailsState,
    bridge_initial_size,
    guardrails_capacity_and_update,
    step_year,
)
from app.services.retirement_planning_assumptions import (
    _ORDINARY_INCOME_BUCKETS,
    DEFAULT_DRAWDOWN_ORDER,
    RMD_START_AGE,
    TAXABLE_WITHDRAWAL_GAIN_RATIO,
    FederalTaxContext,
    WithdrawalOutcome,
    _aca_magi_nominal,
    _aca_year_plans,
    _bucket_balances,
    _carve_bridge_from_balances,
    _contribution_bucket,
    _early_withdrawal_penalty_rate,
    _effective_gain_ratio,
    _engine_withdrawal_config,
    _federal_tax_estimate,
    _household_retirement_primary_age,
    _income_components_for_age,
    _partial_year_amounts_real,
    _real_guaranteed_income_fn,
    _rmd_amount,
    _simulation_asset_classes,
    _weights_for_classes,
)


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
