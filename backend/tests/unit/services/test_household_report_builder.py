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


def test_build_household_reports_excludes_future_dated_rows_from_current_facts() -> None:
    today = date.today()

    reports = build_household_reports(
        report_rows=[
            {
                "date": today - timedelta(days=3),
                "merchant": "Publix",
                "description": "Groceries",
                "amount": 120.0,
                "category": "Groceries",
                "essentiality": "essential",
                "account_label": "Joint Checking",
                "document_id": "doc-current",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
            {
                "date": today + timedelta(days=120),
                "merchant": "Future Walmart",
                "description": "Misdated receipt",
                "amount": 999.0,
                "category": "Retail",
                "essentiality": "discretionary",
                "account_label": "Credit Card",
                "document_id": "doc-future",
                "document_type": "receipt",
                "source_type": "receipt",
                "source_kind": "transaction",
            },
        ],
        cadence_for_dates=lambda dates: {"label": "monthly"} if len(dates) > 1 else None,
        merchant_recommendation=lambda *, merchant, category, cadence: f"{merchant}:{category}:{cadence}",
    )

    assert reports.executive.average_monthly_spend == 120.0
    assert reports.executive.average_monthly_discretionary == 0.0
    assert reports.executive.tracked_expense_count == 1
    assert reports.category_breakdown[0].category == "Groceries"
    assert [point.total_spend for point in reports.monthly_spend_trend] == [120.0]
    assert [txn.merchant for txn in reports.recent_transactions] == ["Publix"]


def test_build_household_reports_limits_executive_summary_to_recent_months() -> None:
    reports = build_household_reports(
        report_rows=[
            {
                "date": date(2025, 1, 15),
                "merchant": "History January",
                "description": "Old spend",
                "amount": 100.0,
                "category": "Legacy",
                "essentiality": "discretionary",
                "account_label": "Checking",
                "document_id": "doc-jan",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
            {
                "date": date(2025, 2, 15),
                "merchant": "History February",
                "description": "Old spend",
                "amount": 200.0,
                "category": "Legacy",
                "essentiality": "discretionary",
                "account_label": "Checking",
                "document_id": "doc-feb",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
            {
                "date": date(2025, 3, 15),
                "merchant": "Recent March",
                "description": "Recent spend",
                "amount": 300.0,
                "category": "Current",
                "essentiality": "essential",
                "account_label": "Checking",
                "document_id": "doc-mar",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
            {
                "date": date(2025, 4, 15),
                "merchant": "Recent April",
                "description": "Recent spend",
                "amount": 400.0,
                "category": "Current",
                "essentiality": "essential",
                "account_label": "Checking",
                "document_id": "doc-apr",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
            {
                "date": date(2025, 5, 15),
                "merchant": "Recent May",
                "description": "Recent spend",
                "amount": 500.0,
                "category": "Current",
                "essentiality": "essential",
                "account_label": "Checking",
                "document_id": "doc-may",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
            {
                "date": date(2025, 6, 15),
                "merchant": "Recent June",
                "description": "Recent spend",
                "amount": 600.0,
                "category": "Current",
                "essentiality": "essential",
                "account_label": "Checking",
                "document_id": "doc-jun",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
            {
                "date": date(2025, 7, 15),
                "merchant": "Recent July",
                "description": "Recent spend",
                "amount": 700.0,
                "category": "Current",
                "essentiality": "essential",
                "account_label": "Checking",
                "document_id": "doc-jul",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
            {
                "date": date(2025, 8, 15),
                "merchant": "Recent August",
                "description": "Recent spend",
                "amount": 800.0,
                "category": "Current",
                "essentiality": "essential",
                "account_label": "Checking",
                "document_id": "doc-aug",
                "document_type": "statement",
                "source_type": "bank",
                "source_kind": "transaction",
            },
        ],
        cadence_for_dates=lambda dates: {"label": "monthly"} if len(dates) > 1 else None,
        merchant_recommendation=lambda *, merchant, category, cadence: f"{merchant}:{category}:{cadence}",
    )

    assert reports.executive.coverage_months == 6
    assert reports.executive.average_monthly_spend == 550.0
    assert reports.executive.average_monthly_essentials == 550.0
    assert reports.category_breakdown[0].category == "Current"
    assert reports.category_breakdown[0].total_spend == 3300.0
    assert reports.monthly_spend_trend[0].month == "2025-03"
    assert reports.monthly_spend_trend[-1].month == "2025-08"


def test_build_household_reports_emits_price_insights_from_repeated_import_items() -> None:
    reports = build_household_reports(
        report_rows=[
            {
                "date": date(2026, 2, 5),
                "merchant": "Amazon",
                "description": "Nate's 100% Pure, Raw & Unfiltered Honey - 32oz",
                "amount": 13.99,
                "category": "Household shopping",
                "essentiality": "mixed",
                "account_label": None,
                "document_id": "doc-old",
                "document_type": "import",
                "source_type": "amazon_order_history",
                "source_kind": "import",
                "metadata": {
                    "ASIN": "B00CMQD3VS",
                    "Unit Price": "13.99",
                    "Product Name": "Nate's 100% Pure, Raw & Unfiltered Honey - 32oz",
                },
            },
            {
                "date": date(2026, 3, 2),
                "merchant": "Amazon",
                "description": "Nate's 100% Pure, Raw & Unfiltered Honey - 32oz",
                "amount": 14.26,
                "category": "Household shopping",
                "essentiality": "mixed",
                "account_label": None,
                "document_id": "doc-new",
                "document_type": "import",
                "source_type": "amazon_order_history",
                "source_kind": "import",
                "metadata": {
                    "ASIN": "B00CMQD3VS",
                    "Unit Price": "14.26",
                    "Product Name": "Nate's 100% Pure, Raw & Unfiltered Honey - 32oz",
                },
            },
        ],
        cadence_for_dates=lambda dates: {"label": "monthly"} if len(dates) > 1 else None,
        merchant_recommendation=lambda *, merchant, category, cadence: f"{merchant}:{category}:{cadence}",
    )

    assert len(reports.price_insights) == 1
    assert reports.price_insights[0].merchant == "Amazon"
    assert reports.price_insights[0].latest_price == 14.26
    assert reports.price_insights[0].previous_price == 13.99
    assert reports.price_insights[0].price_change == 0.27
    assert reports.price_insights[0].latest_unit_label == "32 oz"
    assert reports.price_insights[0].unit_price_change_pct == 1.9
    assert reports.price_insights[0].shrinkflation_flag is False


def test_build_household_reports_flags_shrinkflation_when_size_drops_without_price_relief() -> None:
    reports = build_household_reports(
        report_rows=[
            {
                "date": date(2026, 1, 8),
                "merchant": "Amazon",
                "description": "Triscuit Reduced Fat Whole Grain Wheat Crackers, 12 oz",
                "amount": 3.89,
                "category": "Household shopping",
                "essentiality": "mixed",
                "account_label": None,
                "document_id": "doc-before",
                "document_type": "import",
                "source_type": "amazon_order_history",
                "source_kind": "import",
                "metadata": {
                    "Unit Price": "3.89",
                    "Product Name": "Triscuit Reduced Fat Whole Grain Wheat Crackers, 12 oz",
                },
            },
            {
                "date": date(2026, 3, 8),
                "merchant": "Amazon",
                "description": "Triscuit Reduced Fat Whole Grain Wheat Crackers, 10.5 oz",
                "amount": 3.89,
                "category": "Household shopping",
                "essentiality": "mixed",
                "account_label": None,
                "document_id": "doc-after",
                "document_type": "import",
                "source_type": "amazon_order_history",
                "source_kind": "import",
                "metadata": {
                    "Unit Price": "3.89",
                    "Product Name": "Triscuit Reduced Fat Whole Grain Wheat Crackers, 10.5 oz",
                },
            },
        ],
        cadence_for_dates=lambda dates: {"label": "monthly"} if len(dates) > 1 else None,
        merchant_recommendation=lambda *, merchant, category, cadence: f"{merchant}:{category}:{cadence}",
    )

    assert len(reports.price_insights) == 1
    insight = reports.price_insights[0]
    assert insight.signal_type == "shrinkflation"
    assert insight.shrinkflation_flag is True
    assert insight.latest_unit_label == "10.5 oz"
    assert insight.previous_unit_label == "12 oz"
    assert insight.size_change_pct == -12.5
    assert insight.unit_price_change_pct == 14.3


def test_build_household_reports_uses_cached_product_enrichment_measure_when_title_lacks_size() -> None:
    reports = build_household_reports(
        report_rows=[
            {
                "date": date(2026, 2, 5),
                "merchant": "Amazon",
                "description": "Honey reorder",
                "amount": 13.99,
                "category": "Household shopping",
                "essentiality": "mixed",
                "account_label": None,
                "document_id": "doc-old",
                "document_type": "import",
                "source_type": "amazon_order_history",
                "source_kind": "import",
                "metadata": {
                    "ASIN": "B00CMQD3VS",
                    "Unit Price": "13.99",
                    "Product Name": "Honey reorder",
                    "product_enrichment": {
                        "package_measure": {
                            "display_label": "32 oz",
                            "normalized_quantity": 32,
                            "normalized_unit": "weight_oz",
                            "raw_quantity": 32,
                            "raw_unit": "oz",
                        }
                    },
                },
            },
            {
                "date": date(2026, 3, 2),
                "merchant": "Amazon",
                "description": "Honey reorder",
                "amount": 14.26,
                "category": "Household shopping",
                "essentiality": "mixed",
                "account_label": None,
                "document_id": "doc-new",
                "document_type": "import",
                "source_type": "amazon_order_history",
                "source_kind": "import",
                "metadata": {
                    "ASIN": "B00CMQD3VS",
                    "Unit Price": "14.26",
                    "Product Name": "Honey reorder",
                    "product_enrichment": {
                        "package_measure": {
                            "display_label": "32 oz",
                            "normalized_quantity": 32,
                            "normalized_unit": "weight_oz",
                            "raw_quantity": 32,
                            "raw_unit": "oz",
                        }
                    },
                },
            },
        ],
        cadence_for_dates=lambda dates: {"label": "monthly"} if len(dates) > 1 else None,
        merchant_recommendation=lambda *, merchant, category, cadence: f"{merchant}:{category}:{cadence}",
    )

    assert len(reports.price_insights) == 1
    assert reports.price_insights[0].latest_unit_label == "32 oz"
    assert reports.price_insights[0].unit_price_change_pct == 1.9
