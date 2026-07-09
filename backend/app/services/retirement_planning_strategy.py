"""Coverage and now/soon/later strategy calculations for retirement plans."""

from __future__ import annotations

from typing import Any

from app.portfolio.contracts.retirement import (
    RetirementAccountAllocationAccount,
    RetirementAccountAllocationCoverage,
    RetirementBucketStrategy,
    RetirementBucketStrategyBucket,
    RetirementBucketStrategyHolding,
    RetirementDrawdownYear,
    RetirementHoldingsCoverage,
    RetirementHoldingsCoverageAccount,
    RetirementInputs,
)
from app.services._retirement_simulation import SimulationOutputs
from app.services.retirement_planning_assumptions import (
    STRATEGY_BUCKET_HORIZONS,
    STRATEGY_BUCKET_LABELS,
    STRATEGY_BUCKET_PURPOSES,
    _household_retirement_primary_age,
    _normalized_asset_allocation,
)


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
