"""Unit tests for household transaction report helpers."""

from __future__ import annotations

from datetime import date, timedelta

from app.services._household_report_builder import (
    build_household_reports,
    collapse_report_rows,
    report_row_exclusion_reason,
    report_rows_overlap,
)


def test_collapse_report_rows_prefers_import_row_over_matching_transaction() -> None:
    shared_date = date(2026, 3, 1)

    collapsed = collapse_report_rows(
        [
            {
                "date": shared_date,
                "merchant": "Walmart (Store #5831, Anytown, ST)",
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
                "merchant": "WM SUPERCENTER #5831 ANYTOWN ST",
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


def test_collapse_report_rows_keeps_plain_transaction_variants_for_db_dedup() -> None:
    # Statement-activity vs statement-PDF variants of one charge are owned by
    # household_transaction_dedup_service at the DB layer (removed=TRUE rows
    # never reach this builder). Collapsing them again here merged legitimate
    # same-day same-amount pairs, so the report layer must keep both.
    shared_date = date(2026, 4, 8)

    collapsed = collapse_report_rows(
        [
            {
                "date": shared_date,
                "merchant": "Spotify USA | Sale",
                "description": "Spotify USA | Sale",
                "amount": 21.58,
                "category": "Subscriptions",
                "essentiality": "discretionary",
                "household_account_id": "acct-1",
                "account_label": "Amazon Chase (CC)",
                "document_id": "activity-doc",
                "document_type": "statement",
                "source_type": "credit_card",
                "source_kind": "transaction",
                "source_document_filename": "activity.csv",
                "row_hash": "hash-activity",
            },
            {
                "date": shared_date,
                "merchant": "Spotify USA 877-7781161 NY",
                "description": "Spotify USA 877-7781161 NY",
                "amount": 21.58,
                "category": "Subscriptions",
                "essentiality": "discretionary",
                "household_account_id": "acct-1",
                "account_label": "Amazon Chase (CC)",
                "document_id": "statement-doc",
                "document_type": "statement",
                "source_type": "credit_card",
                "source_kind": "transaction",
                "source_document_filename": "statement.pdf",
                "row_hash": "hash-statement",
            },
        ]
    )

    assert len(collapsed) == 2


def test_collapse_report_rows_keeps_statement_and_plaid_rows_for_db_dedup() -> None:
    # Cross-source statement/Plaid duplicates are the DB dedup service's
    # fuzzy-date arm; the report layer no longer second-guesses it.
    collapsed = collapse_report_rows(
        [
            {
                "date": date(2026, 4, 25),
                "merchant": "KANES FURNITURE 04 | Sale",
                "description": "KANES FURNITURE 04 | Sale",
                "amount": 855.99,
                "category": "Home",
                "essentiality": "discretionary",
                "household_account_id": "acct-1",
                "account_label": "Amazon Chase (CC)",
                "document_id": "statement-doc",
                "document_type": "statement",
                "source_type": "credit_card",
                "source_kind": "transaction",
                "source_document_filename": "statement.pdf",
                "row_hash": "hash-statement",
            },
            {
                "date": date(2026, 4, 26),
                "merchant": "Kanes Furniture",
                "description": "KANES FURNITURE 04",
                "amount": 855.99,
                "category": "Home",
                "essentiality": "discretionary",
                "household_account_id": "acct-1",
                "account_label": "Amazon Chase (CC)",
                "document_id": "plaid-doc",
                "document_type": "api_sync",
                "source_type": "plaid",
                "source_kind": "transaction",
                "source_document_filename": "plaid-sync",
                "row_hash": "hash-plaid",
            },
        ]
    )

    assert len(collapsed) == 2


def test_collapse_report_rows_keeps_same_source_nearby_repeat_charges() -> None:
    collapsed = collapse_report_rows(
        [
            {
                "date": date(2026, 4, 25),
                "merchant": "Chipotle",
                "description": "Chipotle",
                "amount": 16.82,
                "category": "Dining",
                "essentiality": "discretionary",
                "household_account_id": "acct-1",
                "account_label": "Amazon Chase (CC)",
                "document_id": "plaid-doc",
                "document_type": "api_sync",
                "source_type": "plaid",
                "source_kind": "transaction",
                "row_hash": "hash-1",
            },
            {
                "date": date(2026, 4, 26),
                "merchant": "Chipotle",
                "description": "Chipotle",
                "amount": 16.82,
                "category": "Dining",
                "essentiality": "discretionary",
                "household_account_id": "acct-1",
                "account_label": "Amazon Chase (CC)",
                "document_id": "plaid-doc",
                "document_type": "api_sync",
                "source_type": "plaid",
                "source_kind": "transaction",
                "row_hash": "hash-2",
            },
        ]
    )

    assert len(collapsed) == 2


def _report_row(
    *,
    row_date: date,
    merchant: str,
    amount: float,
    category: str,
    essentiality: str,
    signed_amount: float | None = None,
    document_id: str = "doc",
) -> dict[str, object]:
    return {
        "date": row_date,
        "merchant": merchant,
        "description": merchant,
        "amount": amount,
        "signed_amount": amount if signed_amount is None else signed_amount,
        "category": category,
        "essentiality": essentiality,
        "account_label": "Joint Checking",
        "document_id": document_id,
        "document_type": "statement",
        "source_type": "bank",
        "source_kind": "transaction",
    }


def test_build_household_reports_uses_today_for_recent_spend_window() -> None:
    today = date.today()
    previous_month_day = today.replace(day=1) - timedelta(days=1)
    earlier_month_day = previous_month_day.replace(day=1) - timedelta(days=1)

    reports = build_household_reports(
        report_rows=[
            _report_row(
                row_date=today, merchant="Publix", amount=120.0,
                category="Groceries", essentiality="essential", document_id="doc-recent",
            ),
            _report_row(
                row_date=previous_month_day, merchant="Target", amount=80.0,
                category="Retail", essentiality="discretionary", document_id="doc-prev",
            ),
            _report_row(
                row_date=earlier_month_day, merchant="Target", amount=100.0,
                category="Retail", essentiality="discretionary", document_id="doc-earlier",
            ),
        ],
        cadence_for_dates=lambda dates: {"label": "monthly"} if len(dates) > 1 else None,
        merchant_recommendation=lambda *, merchant, category, cadence: f"{merchant}:{category}:{cadence}",
    )

    expected_recent = 120.0 + (
        80.0 if (today - previous_month_day).days <= 29 else 0.0
    )
    assert reports.executive.recent_30_day_spend == expected_recent
    # Averages divide by complete months only; the current partial month stays
    # a trend point but never a denominator.
    assert reports.executive.average_monthly_spend == 90.0
    assert reports.executive.average_monthly_discretionary == 90.0
    assert reports.executive.average_monthly_essentials == 0.0
    assert reports.executive.coverage_months == 3
    assert "(current partial month excluded)" in reports.executive.summary
    assert reports.category_breakdown[0].category == "Retail"
    assert reports.category_breakdown[0].total_spend == 180.0
    assert reports.category_breakdown[0].monthly_average == 90.0
    assert reports.category_breakdown[1].category == "Groceries"
    assert reports.category_breakdown[1].monthly_average == 0.0
    assert reports.merchant_highlights[0].merchant == "Target"
    assert reports.merchant_highlights[0].average_ticket == 90.0
    assert reports.recent_transactions[0].date == today.isoformat()
    assert reports.recent_transactions[0].essentiality == "essential"
    assert [point.month for point in reports.monthly_spend_trend] == sorted(
        point.month for point in reports.monthly_spend_trend
    )
    # Completed-month comparison is server-owned (was frontend client-clock math).
    assert reports.month_comparison is not None
    assert reports.month_comparison.latest_month == previous_month_day.strftime("%Y-%m")
    assert reports.month_comparison.previous_month == earlier_month_day.strftime("%Y-%m")
    assert reports.month_comparison.change == -20.0
    assert reports.month_comparison.change_pct == -20.0


def test_build_household_reports_nets_refunds_out_of_spend_math() -> None:
    previous_month_day = date.today().replace(day=1) - timedelta(days=1)
    refund_day = previous_month_day.replace(day=1)

    reports = build_household_reports(
        report_rows=[
            _report_row(
                row_date=refund_day, merchant="Target", amount=200.0,
                category="Retail", essentiality="discretionary", document_id="doc-buy",
            ),
            _report_row(
                row_date=previous_month_day, merchant="Target", amount=50.0,
                signed_amount=-50.0,
                category="Retail", essentiality="discretionary", document_id="doc-refund",
            ),
        ],
        cadence_for_dates=lambda _dates: None,
        merchant_recommendation=lambda **_kwargs: "",
    )

    month_key = previous_month_day.strftime("%Y-%m")
    trend = {point.month: point.total_spend for point in reports.monthly_spend_trend}
    assert trend[month_key] == 150.0
    assert reports.executive.average_monthly_spend == 150.0
    assert reports.executive.average_monthly_discretionary == 150.0
    assert reports.category_breakdown[0].total_spend == 150.0
    assert reports.merchant_highlights[0].total_spend == 150.0


def test_report_rows_overlap_treats_receipt_sourced_statement_rows_as_receipts() -> None:
    # Receipt-parsed rows sometimes persist with document_type='statement';
    # the source_system still marks them as receipt evidence, which this
    # layer owns reconciling against their Plaid twins.
    receipt_row = {
        "date": date(2026, 5, 4),
        "merchant": "Ulta Beauty",
        "description": "Ulta Beauty purchase",
        "amount": 34.96,
        "category": "Personal Care",
        "essentiality": "discretionary",
        "household_account_id": "acct-1",
        "account_label": "Chase Prime Visa",
        "document_id": "receipt-doc",
        "document_type": "statement",
        "source_type": "receipt",
        "source_kind": "transaction",
        "source_system": "receipt_transaction",
        "row_hash": "hash-receipt",
    }
    plaid_row = {
        "date": date(2026, 5, 6),
        "merchant": "Ulta Beauty",
        "description": "ULTA #123",
        "amount": 34.96,
        "category": "Personal Care",
        "essentiality": "discretionary",
        "household_account_id": "acct-1",
        "account_label": "Chase Prime Visa",
        "document_id": "plaid-doc",
        "document_type": "api_sync",
        "source_type": "plaid",
        "source_kind": "transaction",
        "source_system": "plaid",
        "row_hash": "hash-plaid",
    }

    assert report_rows_overlap(receipt_row, plaid_row)
    assert report_row_exclusion_reason(receipt_row, plaid_row) == "duplicate_of_receipt"
    collapsed = collapse_report_rows([receipt_row, plaid_row])
    assert len(collapsed) == 1
    # The plaid row survives: it carries the categorization pipeline's
    # category and a clean merchant label; the receipt is absorbed evidence.
    assert collapsed[0]["document_id"] == "plaid-doc"


def test_collapse_blocks_cross_account_twins_and_caps_absorption() -> None:
    def _charge(account: str, row_hash: str, day: int) -> dict:
        return {
            "date": date(2026, 5, day),
            "merchant": "Ulta Beauty",
            "description": f"ULTA #{row_hash}",
            "amount": 34.96,
            "category": "Personal Care",
            "essentiality": "discretionary",
            "household_account_id": account,
            "account_label": f"Card {account}",
            "document_id": f"doc-{row_hash}",
            "document_type": "api_sync",
            "source_type": "plaid",
            "source_kind": "transaction",
            "source_system": "plaid",
            "row_hash": row_hash,
        }

    receipt_row = {
        "date": date(2026, 5, 4),
        "merchant": "Ulta Beauty",
        "description": "Ulta Beauty purchase",
        "amount": 34.96,
        "category": "Household",
        "essentiality": "mixed",
        "household_account_id": "acct-1",
        "account_label": "Card acct-1",
        "document_id": "receipt-doc",
        "document_type": "receipt",
        "source_type": "receipt",
        "source_kind": "transaction",
        "source_system": "receipt_transaction",
        "row_hash": "hash-receipt",
    }
    same_account_charge = _charge("acct-1", "hash-a", 5)
    other_account_charge = _charge("acct-2", "hash-b", 5)

    # A charge on a different known account is a different purchase — the
    # receipt must not absorb it, and one receipt absorbs at most one charge.
    assert not report_rows_overlap(receipt_row, other_account_charge)
    collapsed = collapse_report_rows(
        [receipt_row, same_account_charge, other_account_charge]
    )
    assert sorted(row["row_hash"] for row in collapsed) == ["hash-a", "hash-b"]

    # One import row documents one order: it absorbs at most one plain
    # charge, so a second real same-amount charge nearby still counts.
    import_row = {
        "date": date(2026, 5, 4),
        "merchant": "Ulta Beauty",
        "description": "Ulta Beauty order",
        "amount": 34.96,
        "category": "Household shopping",
        "essentiality": "mixed",
        "household_account_id": None,
        "document_id": "import-doc",
        "document_type": "import",
        "source_type": "import",
        "source_kind": "import",
        "row_hash": "hash-import",
    }
    twin_charge = _charge("acct-1", "hash-twin", 5)
    second_charge = _charge("acct-1", "hash-second", 5)
    collapsed_with_import = collapse_report_rows(
        [import_row, twin_charge, second_charge]
    )
    surviving_hashes = {row["row_hash"] for row in collapsed_with_import}
    assert "hash-import" in surviving_hashes
    assert len(surviving_hashes & {"hash-twin", "hash-second"}) == 1


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
