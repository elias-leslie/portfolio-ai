"""Pure helpers for household dashboard sections."""

from __future__ import annotations

from collections.abc import Callable

from app.models.household_finance import HouseholdDocument

ResolvedNumericValue = Callable[[str], float | int | None]

# Retained because next_best_action still reads a score to decide whether to
# stop prompting for setup. The score itself now comes from
# `_household_coverage.py`, which measures what the system can see rather than
# what the household has typed in.
VISIBILITY_STRONG_THRESHOLD = 80


def next_best_action(
    documents: list[HouseholdDocument],
    visibility_score: int,
    *,
    questions: list[str],
    resolved_numeric_value: ResolvedNumericValue,
) -> str:
    action = "Review this month's pacing and savings opportunities instead of collecting more setup data."
    has_docs = bool(documents)
    if questions:
        action = questions[0]
    elif not has_docs:
        action = (
            "Drop in recent financial evidence so Jenny can map accounts, cash flow, "
            "and portfolio activity."
        )
    elif resolved_numeric_value("monthly_net_income_target") is None:
        # Documents exist — Jenny is working on it, don't blame the user
        action = "Jenny is building your income profile from uploaded evidence."
    elif (
        resolved_numeric_value("monthly_essential_target") is None
        or resolved_numeric_value("monthly_discretionary_target") is None
    ):
        action = "Jenny is analyzing your evidence to establish spending guardrails."
    elif (
        resolved_numeric_value("target_retirement_spend") is None
        or resolved_numeric_value("target_retirement_age") is None
    ):
        action = "Set a retirement age and spending target so Jenny can model readiness."
    elif visibility_score < VISIBILITY_STRONG_THRESHOLD:
        action = "Jenny is refining your financial picture as more data flows in."
    return action


def budget_input_status(
    resolved_numeric_value: ResolvedNumericValue,
    documents: list[HouseholdDocument],
) -> dict[str, object]:
    missing_inputs: list[str] = []
    priorities: list[str] = []
    has_docs = bool(documents)

    # When documents exist, Jenny can infer income/essential/discretionary —
    # don't create homework items for inferable fields.
    if resolved_numeric_value("monthly_net_income_target") is None:
        if has_docs:
            priorities.append("Jenny is working on inferring income from your uploaded evidence.")
        else:
            missing_inputs.append("Monthly income target")
            priorities.append("Upload paystubs, deposit screenshots, or answer Jenny's income question.")
    if resolved_numeric_value("monthly_essential_target") is None:
        if has_docs:
            priorities.append("Jenny is analyzing evidence to establish essential spending baselines.")
        else:
            missing_inputs.append("Essential spending target")
            priorities.append("Jenny still needs bills and core spending data to infer the essentials budget.")
    if resolved_numeric_value("monthly_discretionary_target") is None:
        if has_docs:
            priorities.append("Jenny is categorizing transactions to separate discretionary from essentials.")
        else:
            missing_inputs.append("Discretionary spending target")
            priorities.append("Feed more card and checking data so Jenny can separate flexible spend from essentials.")
    if not has_docs:
        missing_inputs.append("Recent financial evidence")
        priorities.append("Upload the last 90 days of statements, exports, or screenshots to turn targets into monitored reality.")

    return {
        "budget_ready": not missing_inputs,
        "missing_inputs": missing_inputs,
        "priorities": priorities or ["Keep evidence intake current so Jenny can monitor pacing and savings."],
    }


def retirement_ready(
    resolved_numeric_value: ResolvedNumericValue,
    documents: list[HouseholdDocument],
) -> bool:
    return (
        resolved_numeric_value("target_retirement_age") is not None
        and resolved_numeric_value("target_retirement_spend") is not None
        and resolved_numeric_value("monthly_essential_target") is not None
        and bool(documents)
    )


def retirement_strengths(
    retirement_assets: float,
    taxable_assets: float,
    cash_reserve: float,
    resolved_numeric_value: ResolvedNumericValue,
) -> list[str]:
    strengths: list[str] = []
    if retirement_assets > 0:
        strengths.append("Retirement accounts are already visible in the same system as your portfolio.")
    if taxable_assets > 0:
        strengths.append("Taxable assets are tracked, which helps bridge flexibility before retirement accounts are tapped.")
    if cash_reserve > 0:
        strengths.append("Tracked cash provides a starting point for emergency-fund and withdrawal sequencing analysis.")
    if resolved_numeric_value("target_retirement_age") is not None:
        strengths.append("A target retirement age is saved, so future planning can anchor to a real timeline.")
    if not strengths:
        strengths.append("As soon as assets and targets are tracked here, Jenny can unify investing and retirement planning.")
    return strengths


def retirement_blockers(
    resolved_numeric_value: ResolvedNumericValue,
    documents: list[HouseholdDocument],
) -> list[str]:
    blockers: list[str] = []
    if resolved_numeric_value("target_retirement_age") is None:
        blockers.append("No target retirement age yet.")
    if resolved_numeric_value("target_retirement_spend") is None:
        blockers.append("No target retirement spending figure yet.")
    if resolved_numeric_value("monthly_essential_target") is None:
        blockers.append("Essential spending is not defined, so baseline retirement needs are unclear.")
    if not documents:
        blockers.append("No household statements uploaded yet, so actual spend drift is still invisible.")
    return blockers


def retirement_next_steps(
    resolved_numeric_value: ResolvedNumericValue,
    documents: list[HouseholdDocument],
) -> list[str]:
    next_steps: list[str] = []
    if not documents:
        next_steps.append("Upload recent household statements to establish a spending baseline.")
    if resolved_numeric_value("target_retirement_age") is None:
        next_steps.append("Set the age or date range you want to retire.")
    if resolved_numeric_value("target_retirement_spend") is None:
        next_steps.append("Set a target monthly retirement spending figure.")
    if resolved_numeric_value("monthly_savings_target") is None:
        next_steps.append("Add a monthly savings target so Jenny can monitor whether the plan is being funded.")
    if not next_steps:
        next_steps.append("Start scenario planning: early retirement, higher health costs, and lower-return years.")
    return next_steps
