"""Spending actuals derived from the deduped Money ledger (retirement item D part b).

Monthly run-rates feed the retirement planner: total spend vs. the plan's
spending target, and a healthcare out-of-pocket baseline for the ACA
estimator. Rates are computed over the trailing contiguous run of complete
calendar months with substantive ledger coverage, so the current partial
month and straggler months (a lone forwarded receipt) don't dilute them.

Healthcare gets a merchant-level breakdown — variants of the same practice
("ALL SMILES ORTHO LARGO | Sale" vs "All Smiles Ortho Clear") fold into one
group via the dedup service's fingerprint-prefix matcher — so the UI can let
the user exclude items that end before retirement (e.g. ortho) when seeding
the editable OOP baseline.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from importlib import import_module
from typing import Any

from pydantic import BaseModel, Field

from app.services.household_transaction_dedup_service import (
    merchant_key,
    merchants_compatible,
)

# A complete month needs this many ledger rows to count as covered; below it
# the ledger only has incidental rows (one forwarded receipt), not the
# household's actual spend, and including it would understate the run-rate.
MIN_ROWS_PER_COVERED_MONTH = 20

_HEALTHCARE_CATEGORY = "healthcare"


class SpendingActualsMerchant(BaseModel):
    label: str
    monthly_average: float
    total: float
    transaction_count: int
    first_date: str
    last_date: str
    months_seen: int


class SpendingActualsCategory(BaseModel):
    category: str
    essentiality: str
    monthly_average: float
    total: float
    transaction_count: int


class SpendingActuals(BaseModel):
    generated_at: str
    first_month: str | None = None
    last_month: str | None = None
    coverage_months: int = 0
    total_monthly_spend: float = 0.0
    healthcare_monthly: float = 0.0
    source_label: str
    categories: list[SpendingActualsCategory] = Field(default_factory=list)
    healthcare_merchants: list[SpendingActualsMerchant] = Field(default_factory=list)


def _month_key(value: date) -> str:
    return value.strftime("%Y-%m")


def _previous_month(month: str) -> str:
    year, mm = int(month[:4]), int(month[5:7])
    if mm == 1:
        return f"{year - 1}-12"
    return f"{year}-{mm - 1:02d}"


def _coverage_window(rows: list[dict[str, Any]], *, today: date) -> list[str]:
    """Trailing contiguous run of complete, substantively covered months."""
    current_month = _month_key(today)
    counts: dict[str, int] = {}
    for row in rows:
        month = _month_key(row["date"])
        if month < current_month:
            counts[month] = counts.get(month, 0) + 1
    covered = {m for m, n in counts.items() if n >= MIN_ROWS_PER_COVERED_MONTH}
    if not covered:
        return []
    window: list[str] = []
    month = max(covered)
    while month in covered:
        window.append(month)
        month = _previous_month(month)
    return sorted(window)


def _signed_amount(row: dict[str, Any]) -> float:
    return float(row.get("signed_amount", row["amount"]))


def _merchant_groups(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Group rows whose merchant fingerprints are dedup-compatible."""
    groups: list[tuple[list[str], list[dict[str, Any]]]] = []
    for row in rows:
        key = merchant_key({"raw_merchant": str(row.get("merchant") or row.get("description") or "")})
        for keys, members in groups:
            if any(merchants_compatible(key, existing) for existing in keys):
                keys.append(key)
                members.append(row)
                break
        else:
            groups.append(([key], [row]))
    return [members for _, members in groups]


def _group_label(rows: list[dict[str, Any]]) -> str:
    labels = [str(row.get("merchant") or row.get("description") or "") for row in rows]
    counts: dict[str, int] = {}
    for label in labels:
        counts[label] = counts.get(label, 0) + 1
    # Most frequent label wins; ties prefer the shortest (least decorated) one.
    return min(counts, key=lambda label: (-counts[label], len(label)))


def derive_spending_actuals(
    rows: list[dict[str, Any]],
    *,
    today: date,
) -> SpendingActuals:
    generated_at = datetime.now(UTC).isoformat()
    window = _coverage_window(rows, today=today)
    if not window:
        return SpendingActuals(
            generated_at=generated_at,
            source_label="No complete months of Money transaction coverage yet.",
        )

    window_set = set(window)
    window_rows = [row for row in rows if _month_key(row["date"]) in window_set]
    coverage_months = len(window)

    total_spend = sum(_signed_amount(row) for row in window_rows)

    category_totals: dict[tuple[str, str], float] = {}
    category_counts: dict[tuple[str, str], int] = {}
    for row in window_rows:
        key = (str(row["category"]), str(row["essentiality"]))
        category_totals[key] = category_totals.get(key, 0.0) + _signed_amount(row)
        category_counts[key] = category_counts.get(key, 0) + 1

    healthcare_rows = [
        row
        for row in window_rows
        if str(row["category"]).strip().lower() == _HEALTHCARE_CATEGORY
    ]
    healthcare_total = sum(_signed_amount(row) for row in healthcare_rows)

    merchants: list[SpendingActualsMerchant] = []
    for group in _merchant_groups(healthcare_rows):
        group_total = sum(_signed_amount(row) for row in group)
        dates = sorted(row["date"] for row in group)
        merchants.append(
            SpendingActualsMerchant(
                label=_group_label(group),
                monthly_average=round(group_total / coverage_months, 2),
                total=round(group_total, 2),
                transaction_count=len(group),
                first_date=dates[0].isoformat(),
                last_date=dates[-1].isoformat(),
                months_seen=len({_month_key(d) for d in dates}),
            )
        )
    merchants.sort(key=lambda m: m.monthly_average, reverse=True)

    first_month, last_month = window[0], window[-1]
    return SpendingActuals(
        generated_at=generated_at,
        first_month=first_month,
        last_month=last_month,
        coverage_months=coverage_months,
        total_monthly_spend=round(total_spend / coverage_months, 2),
        healthcare_monthly=round(healthcare_total / coverage_months, 2),
        source_label=(
            f"Derived from deduped Money transactions, {first_month} to {last_month} "
            f"({coverage_months} complete months)."
        ),
        categories=[
            SpendingActualsCategory(
                category=category,
                essentiality=essentiality,
                monthly_average=round(amount / coverage_months, 2),
                total=round(amount, 2),
                transaction_count=category_counts[(category, essentiality)],
            )
            for (category, essentiality), amount in sorted(
                category_totals.items(), key=lambda item: item[1], reverse=True
            )
        ],
        healthcare_merchants=merchants,
    )


class RetirementSpendingActualsService:
    """Fetch deduped spend rows and derive retirement-facing run-rates."""

    def build(self) -> SpendingActuals:
        # Deferred so importing this module doesn't pull the whole Money stack.
        module = import_module("app.services.household_transaction_service")
        transaction_service = module.HouseholdTransactionService()
        today = date.today()
        rows = transaction_service._spend_rows_between(
            start_date=None,
            end_date=today,
        )
        return derive_spending_actuals(rows, today=today)
