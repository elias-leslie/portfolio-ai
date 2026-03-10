"""Unit tests for household transaction report helpers."""

from __future__ import annotations

from datetime import date, timedelta

from app.services._household_report_builder import (
    build_household_reports,
    collapse_report_rows,
)


def test_collapse_report_rows_prefers_import_row_over_matching_transaction() -> None:
    shared_date = date(2026, 3, 1)

    collapsed = collapse_report_rows(
        [
            {
                "date": shared_date,
                "merchant": "Walmart (Store #5831, Largo, FL)",
                "description": "Imported Walmart order",
                "amount": 164.14,
                "category": "Household shopping",
                "essentiality": "mixed",
                "account_label": None,
                "document_id": "import-doc",
                "document_type": "import",
                "source_type": "amazon_order_history",
                "source_kind": "import",
            },
            {
                "date": shared_date,
                "merchant": "WM SUPERCENTER #5831 LARGO FL",
                "description": "Walmart receipt",
                "amount": 164.14,
                "category": "Retail",
                "essentiality": "discretionary",
                "account_label": "Visa",
                "document_id": "receipt-doc",
                "document_type": "receipt",
                "source_type": "receipt",
                "source_kind": "transaction",
            },
        ]
    )

    assert len(collapsed) == 1
    assert collapsed[0]["source_kind"] == "import"
    assert collapsed[0]["document_id"] == "import-doc"


def test_build_household_reports_uses_today_for_recent_spend_window() -> None:
    today = date.today()

    reports = build_household_reports(
        report_rows=[
            {
                "date": today - timedelta(days=5),
                "merchant": "Publix",
                "description": "Groceries",
                "amount": 120.0,
                "category": "Groceries",
                "essentiality": "essential",
                "account_label": "Joint Checking",
                "document_id": "doc-recent",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
            {
                "date": today - timedelta(days=45),
                "merchant": "Target",
                "description": "Household goods",
                "amount": 80.0,
                "category": "Retail",
                "essentiality": "discretionary",
                "account_label": "Joint Checking",
                "document_id": "doc-old",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
        ],
        cadence_for_dates=lambda dates: {"label": "monthly"} if len(dates) > 1 else None,
        merchant_recommendation=lambda *, merchant, category, cadence: f"{merchant}:{category}:{cadence}",
    )

    assert reports.executive.recent_30_day_spend == 120.0
    assert reports.executive.average_monthly_spend == 100.0
    assert reports.executive.coverage_months == 2
    assert reports.category_breakdown[0].total_spend == 120.0
    assert reports.category_breakdown[0].monthly_average == 60.0
    assert reports.merchant_highlights[0].merchant == "Publix"
    assert reports.merchant_highlights[0].average_ticket == 120.0
    assert reports.recent_transactions[0].date == (today - timedelta(days=5)).isoformat()
    assert reports.recent_transactions[0].essentiality == "essential"
    assert [point.month for point in reports.monthly_spend_trend] == sorted(
        point.month for point in reports.monthly_spend_trend
    )
