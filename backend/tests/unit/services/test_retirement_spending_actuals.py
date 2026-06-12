"""Unit tests for the deduped spend/healthcare run-rate derivation (item D-b)."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.services.retirement_spending_actuals_service import (
    MIN_ROWS_PER_COVERED_MONTH,
    derive_spending_actuals,
)

TODAY = date(2026, 6, 11)


def _row(
    day: date,
    amount: float,
    *,
    merchant: str = "Publix",
    category: str = "Groceries",
    essentiality: str = "essential",
) -> dict[str, Any]:
    return {
        "date": day,
        "merchant": merchant,
        "description": merchant,
        "amount": amount,
        "signed_amount": amount,
        "category": category,
        "essentiality": essentiality,
    }


def _filler_month(year: int, month: int, *, count: int = MIN_ROWS_PER_COVERED_MONTH) -> list[dict[str, Any]]:
    return [_row(date(year, month, min(d + 1, 28)), 10.0) for d in range(count)]


def test_window_skips_partial_current_month_and_straggler_months() -> None:
    rows = [
        # Straggler month far back: one forwarded receipt, not real coverage.
        _row(date(2025, 12, 5), 40.0),
        *_filler_month(2026, 3),
        *_filler_month(2026, 4),
        *_filler_month(2026, 5),
        # Current (partial) month must not dilute the run-rate.
        _row(date(2026, 6, 2), 999.0),
    ]

    actuals = derive_spending_actuals(rows, today=TODAY)

    assert actuals.first_month == "2026-03"
    assert actuals.last_month == "2026-05"
    assert actuals.coverage_months == 3
    # 3 filler months x 20 rows x $10 = $600 over 3 months.
    assert actuals.total_monthly_spend == 200.0


def test_window_is_trailing_contiguous_run() -> None:
    # January is covered but February is not — the gap cuts January off.
    rows = _filler_month(2026, 1) + _filler_month(2026, 3) + _filler_month(2026, 4)

    actuals = derive_spending_actuals(rows, today=TODAY)

    assert actuals.first_month == "2026-03"
    assert actuals.coverage_months == 2


def test_no_covered_months_returns_empty_actuals() -> None:
    rows = [_row(date(2026, 5, 1), 50.0)]

    actuals = derive_spending_actuals(rows, today=TODAY)

    assert actuals.coverage_months == 0
    assert actuals.total_monthly_spend == 0.0
    assert actuals.categories == []
    assert "No complete months" in actuals.source_label


def test_healthcare_run_rate_and_merchant_grouping() -> None:
    rows = _filler_month(2026, 4) + _filler_month(2026, 5)
    # Ortho variants across sources/kids must fold into ONE group.
    for month in (4, 5):
        rows.append(
            _row(
                date(2026, month, 3),
                132.08,
                merchant="ALL SMILES ORTHO LARGO | Sale",
                category="Healthcare",
            )
        )
        rows.append(
            _row(
                date(2026, month, 3),
                132.08,
                merchant="All Smiles Ortho Clear",
                category="Healthcare",
            )
        )
    # Distinct pharmacy merchants must stay separate groups.
    rows.append(_row(date(2026, 4, 10), 20.0, merchant="Walgreens", category="Healthcare"))
    rows.append(_row(date(2026, 5, 12), 30.0, merchant="CVS", category="Healthcare"))

    actuals = derive_spending_actuals(rows, today=TODAY)

    assert actuals.healthcare_monthly == round((132.08 * 4 + 50.0) / 2, 2)
    labels = {m.label for m in actuals.healthcare_merchants}
    assert len(actuals.healthcare_merchants) == 3
    assert "Walgreens" in labels
    assert "CVS" in labels
    ortho = actuals.healthcare_merchants[0]
    assert ortho.monthly_average == round(132.08 * 4 / 2, 2)
    assert ortho.transaction_count == 4
    assert ortho.months_seen == 2
    # Categories include healthcare with the same total.
    healthcare_categories = [c for c in actuals.categories if c.category == "Healthcare"]
    assert len(healthcare_categories) == 1
    assert healthcare_categories[0].total == round(132.08 * 4 + 50.0, 2)


def test_refunds_net_against_run_rate() -> None:
    rows = _filler_month(2026, 5)
    refund = _row(date(2026, 5, 20), -50.0, merchant="Walgreens", category="Healthcare")
    refund["signed_amount"] = -50.0
    rows.append(_row(date(2026, 5, 18), 80.0, merchant="Walgreens", category="Healthcare"))
    rows.append(refund)

    actuals = derive_spending_actuals(rows, today=TODAY)

    assert actuals.healthcare_monthly == 30.0
    assert actuals.healthcare_merchants[0].total == 30.0
