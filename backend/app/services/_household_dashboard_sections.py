"""Pure helpers for household dashboard sections."""

from __future__ import annotations

from collections.abc import Callable

from app.models.household_finance import HouseholdDocument, HouseholdOpportunity

ResolvedNumericValue = Callable[[str], float | int | None]


def compute_visibility_score(
    *,
    account_count: int,
    position_count: int,
    cash_reserve: float,
    retirement_assets: float,
    taxable_assets: float,
    resolved_numeric_value: ResolvedNumericValue,
    document_count: int,
) -> int:
    score = 0
    if account_count > 0:
        score += 20
    if position_count > 0:
        score += 20
    if retirement_assets > 0:
        score += 10
    if taxable_assets > 0:
        score += 10
    if cash_reserve > 0:
        score += 10
    if resolved_numeric_value("monthly_net_income_target") is not None:
        score += 10
    if (
        resolved_numeric_value("monthly_essential_target") is not None
        and resolved_numeric_value("monthly_discretionary_target") is not None
    ):
        score += 10
    if (
        resolved_numeric_value("target_retirement_spend") is not None
        and resolved_numeric_value("target_retirement_age") is not None
    ):
        score += 5
    if document_count > 0:
        score += 5
    return score


def visibility_label(score: int) -> str:
    if score >= 80:
        return "Strong household visibility"
    if score >= 50:
        return "Partial money visibility"
    return "Early household setup"


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
        action = "Upload recent bank and credit-card statements so Jenny can see actual cash flow."
    elif resolved_numeric_value("monthly_net_income_target") is None:
        # Documents exist — Jenny is working on it, don't blame the user
        action = "Jenny is building your income profile from uploaded documents."
    elif (
        resolved_numeric_value("monthly_essential_target") is None
        or resolved_numeric_value("monthly_discretionary_target") is None
    ):
        action = "Jenny is analyzing your statements to establish spending guardrails."
    elif (
        resolved_numeric_value("target_retirement_spend") is None
        or resolved_numeric_value("target_retirement_age") is None
    ):
        action = "Set a retirement age and spending target so Jenny can model readiness."
    elif visibility_score < 80:
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
            priorities.append("Jenny is working on inferring income from your uploaded documents.")
        else:
            missing_inputs.append("Monthly income target")
            priorities.append("Upload paystubs, deposit screenshots, or answer Jenny's income question.")
    if resolved_numeric_value("monthly_essential_target") is None:
        if has_docs:
            priorities.append("Jenny is analyzing statements to establish essential spending baselines.")
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
        missing_inputs.append("Recent statements and receipts")
        priorities.append("Upload the last 90 days of statements to turn targets into monitored reality.")

    return {
        "budget_ready": not missing_inputs,
        "missing_inputs": missing_inputs,
        "priorities": priorities or ["Keep statement imports current so Jenny can monitor pacing and savings."],
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


def build_opportunities(
    *,
    resolved_numeric_value: ResolvedNumericValue,
    documents: list[HouseholdDocument],
    taxable_assets: float,
    retirement_assets: float,
) -> list[HouseholdOpportunity]:
    opportunities: list[HouseholdOpportunity] = []
    if not documents:
        opportunities.append(
            HouseholdOpportunity(
                title="Build a statement-first data foundation",
                category="data_foundation",
                impact="High",
                detail=(
                    "Bank and card statements unlock real budgeting, recurring-charge detection, "
                    "merchant comparisons, and future card optimization."
                ),
                next_step="Import 90 days of checking and primary credit-card statements.",
            )
        )
    if (
        resolved_numeric_value("monthly_essential_target") is None
        or resolved_numeric_value("monthly_discretionary_target") is None
    ):
        if documents:
            opportunities.append(
                HouseholdOpportunity(
                    title="Budget guardrails in progress",
                    category="budget_control",
                    impact="Medium",
                    detail="Jenny is analyzing your statements to establish spending guardrails. More months of data will improve accuracy.",
                    next_step="No action needed — Jenny is processing your documents.",
                )
            )
        else:
            opportunities.append(
                HouseholdOpportunity(
                    title="Turn Jenny into a budget guardrail",
                    category="budget_control",
                    impact="High",
                    detail="Jenny can only alert on overspend pace after she has enough evidence to infer your budget guardrails.",
                    next_step="Upload 90 days of checking and credit-card statements.",
                )
            )
    if retirement_assets > 0 and resolved_numeric_value("target_retirement_spend") is None:
        opportunities.append(
            HouseholdOpportunity(
                title="Connect retirement assets to a real spending target",
                category="retirement",
                impact="High",
                detail="Retirement balances are visible, but readiness still depends on what life actually costs.",
                next_step="Add a target retirement spending figure and keep statements current.",
            )
        )
    if documents and taxable_assets >= 0:
        opportunities.append(
            HouseholdOpportunity(
                title="Prepare for merchant and rewards optimization",
                category="savings",
                impact="Medium",
                detail="Once spending data is stable, Jenny can start comparing merchants, brands, and card usage.",
                next_step="Keep uploading statements and receipts so category patterns become trustworthy.",
            )
        )
    return opportunities

