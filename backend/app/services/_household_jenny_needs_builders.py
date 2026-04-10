"""Sub-builders for Jenny needs sections — extracted from _household_dashboard_builders."""
from __future__ import annotations

from typing import Any

from app.models.household_finance import JennyNeed
from app.services._money_workspace_routes import (
    MONEY_ACCOUNT_COVERAGE_ROUTE,
    MONEY_DATE_QUALITY_ROUTE,
    MONEY_EVIDENCE_ROUTE,
    money_planning_focus_route,
)

# Minimum months of statement coverage before Jenny considers data sufficient
MIN_COVERAGE_MONTHS = 3
# Maximum days since latest statement before data is considered stale
STATEMENT_STALENESS_DAYS = 45


def _jenny_statement_needs(coverage_months: int, days_since_latest: int | None) -> list[JennyNeed]:
    """Critical: upload financial evidence when coverage is insufficient."""
    statements_satisfied = (
        coverage_months >= MIN_COVERAGE_MONTHS
        and days_since_latest is not None
        and days_since_latest < STATEMENT_STALENESS_DAYS
    )
    if statements_satisfied:
        return []
    if coverage_months > 0 and days_since_latest is not None:
        detail = (
            f"Currently {coverage_months} month{'s' if coverage_months != 1 else ''} of data, "
            f"most recent {days_since_latest} days ago. More coverage improves accuracy."
        )
    else:
        detail = (
            "Jenny needs at least 3 months of recent financial evidence to build "
            "accurate spending baselines."
        )
    return [JennyNeed(
        id="need_statements", need_type="provide", title="Upload financial evidence",
        detail=detail, priority="critical", status="unsatisfied",
        recurrence="periodic", action_href=MONEY_EVIDENCE_ROUTE,
    )]


def _jenny_confirmation_needs(
    confirmed_facts: dict[str, str], planning: Any, profile: Any
) -> list[JennyNeed]:
    """High-priority confirmation needs: accounts, scope, income, planning gaps, missing docs."""
    needs: list[JennyNeed] = []
    if "account_completeness" not in confirmed_facts:
        needs.append(JennyNeed(
            id="need_account_completeness", need_type="confirm",
            title="Are all accounts covered?",
            detail=(
                "Confirm that your uploaded evidence covers all active bank, card, "
                "brokerage, and retirement accounts."
            ),
            priority="high", status="unsatisfied", recurrence="one_time",
            field_name="account_completeness",
            action_href=MONEY_ACCOUNT_COVERAGE_ROUTE,
        ))
    if "household_scope" not in confirmed_facts:
        needs.append(JennyNeed(
            id="need_household_scope", need_type="confirm",
            title="Who is in this household?",
            detail="Confirm whether this is a single-person or multi-person household so Jenny sizes the budget correctly.",
            priority="high", status="unsatisfied", recurrence="one_time",
            field_name="household_scope",
        ))
    if "income_sources" not in confirmed_facts and not planning.income_sources:
        needs.append(JennyNeed(
            id="need_income_sources", need_type="confirm",
            title="Confirm income sources",
            detail="Tell Jenny about your income sources (salary, freelance, etc.) so she can track completeness.",
            priority="high", status="unsatisfied", recurrence="one_time",
            field_name="income_sources",
        ))
    for section in [s for s in planning.summary.sections if s.status == "missing"][:3]:
        needs.append(JennyNeed(
            id=f"need_planning_{section.section}", need_type="set",
            title=f"Complete {section.label.lower()} planning",
            detail=section.detail,
            priority="high" if section.section in {"household", "income", "housing", "debt"} else "medium",
            status="unsatisfied", recurrence="one_time",
            action_href=money_planning_focus_route(section.section),
        ))
    for req in [r for r in planning.document_requirements if r.status == "missing"][:4]:
        needs.append(JennyNeed(
            id=f"need_document_{req.id}", need_type="provide",
            title=f"Upload {req.label}",
            detail=req.rationale or "Jenny needs this document to validate your planning assumptions.",
            priority=req.priority if req.priority in {"critical", "high", "medium", "low"} else "medium",
            status="unsatisfied", recurrence="as_needed", action_href=MONEY_EVIDENCE_ROUTE,
        ))
    return needs


def _jenny_account_question_needs(
    detected_accounts: list[dict[str, str]], questions: list[Any]
) -> list[JennyNeed]:
    """High-priority detected-account needs and medium open-question needs."""
    needs: list[JennyNeed] = []
    for account in detected_accounts:
        institution = account.get("institution", "Unknown")
        partial = account.get("partial_account", "")
        acct_key = account.get("key", institution)
        label = f"{institution} ...{partial}" if partial else institution
        needs.append(JennyNeed(
            id=f"need_account_{acct_key}", need_type="provide",
            title=f"Add evidence for {label}",
            detail=(
                f"Jenny spotted references to {label} in your transactions but has no "
                "supporting evidence for it yet."
            ),
            priority="high", status="unsatisfied", recurrence="one_time", action_href=MONEY_EVIDENCE_ROUTE,
        ))
    for q in [q for q in questions if q.status == "open"][:3]:
        needs.append(JennyNeed(
            id=f"need_question_{q.id}", need_type="confirm",
            title="Review Jenny's finding",
            detail=q.question, priority="medium", status="unsatisfied",
            recurrence="as_needed", related_question_id=q.id,
            question_format=q.question_format if q.question_format != "short_text" else None,
            options=q.options,
        ))
    return needs


def _jenny_retirement_category_needs(
    profile: Any, categorization_queue: list[Any]
) -> list[JennyNeed]:
    """Medium-priority retirement and category-review needs."""
    needs: list[JennyNeed] = []
    if profile.target_retirement_age is None:
        needs.append(JennyNeed(
            id="need_retirement_age", need_type="set",
            title="Set retirement age",
            detail="Jenny needs a target retirement age to run scenario planning.",
            priority="medium", status="unsatisfied", recurrence="one_time",
            field_name="target_retirement_age",
        ))
    if profile.target_retirement_spend is None:
        needs.append(JennyNeed(
            id="need_retirement_spend", need_type="set",
            title="Set retirement spending target",
            detail="Define a monthly retirement spending target so Jenny can project readiness.",
            priority="medium", status="unsatisfied", recurrence="one_time",
            field_name="target_retirement_spend",
        ))
    if categorization_queue:
        count = len(categorization_queue)
        needs.append(JennyNeed(
            id="need_category_corrections", need_type="review",
            title="Review spending categories",
            detail=f"{count} transaction{'s' if count != 1 else ''} need category confirmation so Jenny can trust the budget lanes.",
            priority="medium", status="unsatisfied", recurrence="as_needed",
        ))
    return needs


def _jenny_transaction_date_quality_needs(freshness: dict[str, Any]) -> list[JennyNeed]:
    future_count = int(freshness.get("future_transaction_count") or 0)
    if future_count <= 0:
        return []

    latest_future_date = freshness.get("latest_future_date")
    date_detail = f" through {latest_future_date}" if latest_future_date else ""
    return [JennyNeed(
        id="need_transaction_date_quality",
        need_type="review",
        title="Review future-dated transactions",
        detail=(
            f"{future_count} transaction{'s' if future_count != 1 else ''}{date_detail} "
            "have dates after today and are excluded from current spending, freshness, and budget calculations until corrected."
        ),
        priority="high",
        status="unsatisfied",
        recurrence="as_needed",
        action_href=MONEY_DATE_QUALITY_ROUTE,
    )]


def _jenny_freshness_needs(documents: list[Any], days_since_latest: int | None) -> list[JennyNeed]:
    """Low-priority freshness need when evidence exists but is stale."""
    if documents and days_since_latest is not None and days_since_latest >= STATEMENT_STALENESS_DAYS:
        return [JennyNeed(
            id="need_freshness", need_type="provide",
            title="Add newer evidence",
            detail=(
                f"The most recent transaction is {days_since_latest} days old. "
                "Fresher evidence keeps pacing accurate."
            ),
            priority="low", status="unsatisfied", recurrence="periodic", action_href=MONEY_EVIDENCE_ROUTE,
        )]
    return []
