"""Helpers for assembling household transaction reports."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import date
from typing import Any

from app.models.household_finance import (
    HouseholdCategoryBreakdown,
    HouseholdExecutiveReport,
    HouseholdMerchantInsight,
    HouseholdMonthlyTrendPoint,
    HouseholdRecentTransaction,
    HouseholdReports,
)

_EXECUTIVE_WINDOW_MONTHS = 6


def _transaction_date(row: dict[str, Any]) -> date | None:
    raw_date = row.get("date")
    if isinstance(raw_date, date):
        return raw_date
    if hasattr(raw_date, "date"):
        return raw_date.date()
    return None


def _is_current_transaction(row: dict[str, Any], *, today: date) -> bool:
    transaction_date = _transaction_date(row)
    return transaction_date is not None and transaction_date <= today


def _merchant_root(merchant: str) -> str:
    normalized = merchant.strip().lower()
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def _merchant_aliases(raw_merchant: str) -> set[str]:
    root = _merchant_root(raw_merchant)
    aliases: set[str] = {root, root.replace(" ", "")} if root else set()
    collapsed = root.replace(" ", "") if root else ""
    if "walmart" in collapsed or "wmsupercenter" in collapsed:
        aliases.update({"walmart", "wal mart", "walmart supercenter", "wm supercenter", "wmsupercenter"})
    if "amazon" in collapsed or "amzn" in collapsed:
        aliases.update({"amazon", "amzn", "amazon mktpl", "amazoncom", "amazon com"})
    if "wholefoods" in collapsed:
        aliases.update({"whole foods", "wholefoods"})
    return {alias for alias in aliases if alias}


def report_rows_overlap(existing_row: dict[str, Any], candidate_row: dict[str, Any]) -> bool:
    if existing_row.get("date") != candidate_row.get("date"):
        return False
    if abs(float(existing_row.get("amount", 0.0)) - float(candidate_row.get("amount", 0.0))) > 0.005:
        return False

    existing_aliases = _merchant_aliases(str(existing_row.get("merchant") or ""))
    candidate_aliases = _merchant_aliases(str(candidate_row.get("merchant") or ""))
    if not (existing_aliases and candidate_aliases and existing_aliases.intersection(candidate_aliases)):
        return False

    source_kinds = {str(existing_row.get("source_kind") or ""), str(candidate_row.get("source_kind") or "")}
    if "import" in source_kinds:
        return True

    document_types = {str(existing_row.get("document_type") or ""), str(candidate_row.get("document_type") or "")}
    return "receipt" in document_types and len(document_types) > 1


def report_row_priority(row: dict[str, Any]) -> tuple[int, str]:
    if row.get("source_kind") == "import":
        return (0, str(row.get("document_id") or ""))

    document_type = str(row.get("document_type") or "")
    if document_type == "receipt":
        return (1, str(row.get("document_id") or ""))

    return (2, str(row.get("document_id") or ""))


def collapse_report_rows(report_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    collapsed_rows: list[dict[str, Any]] = []
    for row in sorted(report_rows, key=report_row_priority):
        if any(report_rows_overlap(existing_row, row) for existing_row in collapsed_rows):
            continue
        collapsed_rows.append(row)
    return collapsed_rows


def build_household_reports(
    *,
    report_rows: list[dict[str, Any]],
    cadence_for_dates: Callable[[list[date]], dict[str, object] | None],
    merchant_recommendation: Callable[..., str],
) -> HouseholdReports:
    today = date.today()
    current_rows = [row for row in report_rows if _is_current_transaction(row, today=today)]
    expense_only = [row for row in collapse_report_rows(current_rows) if row["amount"] > 0]
    if not expense_only:
        return HouseholdReports(
            executive=HouseholdExecutiveReport(
                headline="Jenny needs more transaction evidence to build a cash-flow report.",
                summary="Upload recent statements and receipts so the transaction ledger can estimate real household spending.",
                average_monthly_spend=0.0,
                average_monthly_essentials=0.0,
                average_monthly_discretionary=0.0,
                recent_30_day_spend=0.0,
                recurring_merchant_count=0,
                tracked_expense_count=0,
                coverage_months=0,
            )
        )

    monthly_totals: dict[str, float] = {}
    monthly_counts: dict[str, int] = {}
    recent_cutoff = today.toordinal() - 30

    for row in expense_only:
        month_key = row["date"].strftime("%Y-%m")
        monthly_totals[month_key] = monthly_totals.get(month_key, 0.0) + row["amount"]
        monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1

    recent_month_keys = sorted(monthly_totals.keys())[-_EXECUTIVE_WINDOW_MONTHS:]
    recent_month_set = set(recent_month_keys)
    recent_rows = [
        row
        for row in expense_only
        if row["date"].strftime("%Y-%m") in recent_month_set
    ]
    category_totals: dict[tuple[str, str], float] = {}
    merchant_totals: dict[str, dict[str, Any]] = {}

    for row in recent_rows:
        category_key = (row["category"], row["essentiality"])
        category_totals[category_key] = category_totals.get(category_key, 0.0) + row["amount"]
        merchant_state = merchant_totals.setdefault(
            row["merchant"],
            {"amount": 0.0, "count": 0, "category": row["category"], "dates": []},
        )
        merchant_state["amount"] += row["amount"]
        merchant_state["count"] += 1
        merchant_state["dates"].append(row["date"])

    coverage_months = max(len(recent_month_keys), 1)
    total_spend = sum(monthly_totals[month_key] for month_key in recent_month_keys)
    essential_spend = sum(
        amount for (_, essentiality), amount in category_totals.items() if essentiality == "essential"
    )
    discretionary_spend = sum(
        amount for (_, essentiality), amount in category_totals.items() if essentiality == "discretionary"
    )
    recent_30_day_spend = sum(
        row["amount"] for row in recent_rows if row["date"].toordinal() >= recent_cutoff
    )
    recurring_merchant_count = sum(
        1
        for state in merchant_totals.values()
        if (cadence_for_dates(state["dates"]) or {}).get("label", "one-off") != "one-off"
    )

    executive = HouseholdExecutiveReport(
        headline="Jenny now has a real household spending ledger to work from.",
        summary=(
            f"Average monthly spend is ${total_spend / coverage_months:,.0f} across "
            f"{coverage_months} recent tracked month{'s' if coverage_months != 1 else ''}, "
            f"with {recurring_merchant_count} recurring merchant patterns already visible."
        ),
        average_monthly_spend=round(total_spend / coverage_months, 2),
        average_monthly_essentials=round(essential_spend / coverage_months, 2),
        average_monthly_discretionary=round(discretionary_spend / coverage_months, 2),
        recent_30_day_spend=round(recent_30_day_spend, 2),
        recurring_merchant_count=recurring_merchant_count,
        tracked_expense_count=len(recent_rows),
        coverage_months=coverage_months,
    )

    category_breakdown = [
        HouseholdCategoryBreakdown(
            category=category,
            essentiality=essentiality,
            monthly_average=round(amount / coverage_months, 2),
            share_of_spend=round(amount / total_spend if total_spend > 0 else 0.0, 4),
            total_spend=round(amount, 2),
        )
        for (category, essentiality), amount in sorted(
            category_totals.items(), key=lambda item: item[1], reverse=True
        )[:6]
    ]

    merchant_highlights = []
    for merchant, state in sorted(merchant_totals.items(), key=lambda item: item[1]["amount"], reverse=True)[:6]:
        cadence_data = cadence_for_dates(state["dates"])
        cadence = str(cadence_data["label"]) if cadence_data else "one-off"
        merchant_highlights.append(
            HouseholdMerchantInsight(
                merchant=merchant,
                total_spend=round(state["amount"], 2),
                average_ticket=round(state["amount"] / state["count"], 2),
                transaction_count=state["count"],
                cadence=cadence,
                category=str(state["category"]),
                recommendation=merchant_recommendation(
                    merchant=merchant,
                    category=str(state["category"]),
                    cadence=cadence,
                ),
            )
        )

    monthly_spend_trend = [
        HouseholdMonthlyTrendPoint(
            month=month,
            total_spend=round(monthly_totals[month], 2),
            transaction_count=monthly_counts[month],
        )
        for month in recent_month_keys
    ]

    recent_transactions = [
        HouseholdRecentTransaction(
            date=row["date"].isoformat(),
            merchant=row["merchant"],
            description=row["description"],
            amount=round(row["amount"], 2),
            category=row["category"],
            essentiality=row["essentiality"],
            account_label=row["account_label"],
            source_document_id=row["document_id"],
        )
        for row in sorted(recent_rows, key=lambda item: item["date"], reverse=True)[:10]
    ]

    return HouseholdReports(
        executive=executive,
        category_breakdown=category_breakdown,
        merchant_highlights=merchant_highlights,
        monthly_spend_trend=monthly_spend_trend,
        recent_transactions=recent_transactions,
    )
