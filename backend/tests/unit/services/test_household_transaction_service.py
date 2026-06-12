"""Unit tests for household transaction extraction and normalization."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.services._household_merchants import _effective_transaction_classification
from app.services._household_report_builder import _merchant_aliases
from app.services._household_spend_filters import is_budget_driving_expense
from app.services._household_transaction_parsers import (
    extract_transactions,
    parse_chase_statement,
    parse_ofx_transactions,
    parse_wells_fargo_statement,
)
from app.services.household_transaction_service import HouseholdTransactionService


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any] | None]] = []
        self.committed = False

    def execute(self, sql: str, params: list[Any] | None = None) -> _FakeConnection:
        self.executed.append((sql, params))
        return self

    def fetchone(self) -> tuple[bool]:
        return (True,)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return []

    def commit(self) -> None:
        self.committed = True


class _FakeStorage:
    def __init__(self) -> None:
        self.conn = _FakeConnection()

    @contextmanager
    def connection(self):
        yield self.conn


class _SequenceConnection:
    def __init__(self, responses: list[list[tuple[Any, ...]]]) -> None:
        self._responses = responses

    def execute(
        self,
        sql: str,
        params: list[Any] | None = None,
    ) -> SimpleNamespace:
        del sql, params
        rows = self._responses.pop(0) if self._responses else []
        return SimpleNamespace(
            fetchall=lambda: rows,
            fetchone=lambda: rows[0] if rows else None,
        )


class _SequenceStorage:
    def __init__(self, responses: list[list[tuple[Any, ...]]]) -> None:
        self.conn = _SequenceConnection(responses)

    @contextmanager
    def connection(self):
        yield self.conn


class _MerchantOverrideConnection:
    def __init__(self) -> None:
        self.insert_params: list[Any] | None = None
        self.committed = False

    def execute(self, sql: str, params: list[Any] | None = None) -> Any:
        if "FROM household_merchants" in sql:
            return SimpleNamespace(
                fetchone=lambda: (
                    "merchant-1",
                    "Chase Credit Crd Epay 260215 9126729844 Alex Demo",
                    "Bills",
                    "essential",
                    {},
                )
            )
        if "INSERT INTO household_transactions" in sql:
            self.insert_params = params
            return SimpleNamespace(fetchone=lambda: (True,))
        if "DELETE FROM household_transactions" in sql:
            return SimpleNamespace(fetchall=lambda: [])
        return SimpleNamespace(fetchone=lambda: None, fetchall=lambda: [])

    def commit(self) -> None:
        self.committed = True


class _MerchantOverrideStorage:
    def __init__(self) -> None:
        self.conn = _MerchantOverrideConnection()

    @contextmanager
    def connection(self):
        yield self.conn


def test_parse_chase_statement_extracts_walmart_activity_lines() -> None:
    transactions = parse_chase_statement(
        (
            "ALEX DEMO Page 2 of 4 Statement Date: 01/11/26\n"
            "Date of\n"
            "Transaction Merchant  Name or Transaction Description $ Amount\n"
            "12/11 & WAL-MART #5831 ANYTOWN ST 149.21\n"
            "12/12 & WM SUPERCENTER #5831 ANYTOWN ST 30.00\n"
            "12/23 & Payment Thank You-Mobile -5757.53\n"
        ),
        "Chase Amazon card",
    )

    assert len(transactions) == 3
    assert transactions[0].raw_merchant == "WAL-MART #5831 ANYTOWN ST"
    assert float(transactions[0].amount) == 149.21
    assert transactions[0].flow_type == "expense"
    assert transactions[2].flow_type == "payment"


def test_parse_wells_fargo_statement_extracts_payroll_and_spotify() -> None:
    transactions = parse_wells_fargo_statement(
        (
            "February 25, 2026 Page 2 of 5\n"
            "Transaction history\n"
            "2/4   Recurring Payment authorized on 02/03 Spotify P3Efef4F77\n"
            "NEW York NY S346034529890991 Card 2873\n"
            "19.31    8,200.63\n"
            "2/6   Pinellas County Payroll 260206 8859 Leslie Jordan Demo  2,900.41       11,101.04\n"
            "Totals $6,307.15 $13,431.52\n"
        ),
        "Wells Fargo Everyday Checking",
    )

    assert len(transactions) == 2
    assert transactions[0].flow_type == "expense"
    assert transactions[0].category == "Subscriptions"
    assert transactions[1].flow_type == "income"
    assert transactions[1].category == "Income"


def test_parse_wells_fargo_statement_reclassifies_transfers_benefits_and_card_payments() -> None:
    transactions = parse_wells_fargo_statement(
        (
            "February 25, 2026 Page 2 of 5\n"
            "Transaction history\n"
            "2/17   Chase Credit Crd Epay 260215 9126729844 Alex Demo  5,645.34       1,100.00\n"
            "2/18   Paypal Inst Xfer 260218 Tbl.Leslie Alex Demo  3,520.25       1,200.00\n"
            "2/18   Zelle From Michael Wiley on 02/18 Ref # Wfct0Ztbcn6L  506.31       1,706.31\n"
            "2/18   FL Deo Ui Benefit 260214 xxxxx5852 Alex Demo  247.00       1,953.31\n"
            "Totals $9,918.90 $5,959.62\n"
        ),
        "Wells Fargo Everyday Checking",
    )

    assert [transaction.flow_type for transaction in transactions] == [
        "transfer_out",
        "transfer_out",
        "transfer_in",
        "income",
    ]
    assert [transaction.category for transaction in transactions] == [
        "Transfers",
        "Transfers",
        "Transfers",
        "Income",
    ]


def test_parse_wells_fargo_statement_treats_payables_as_income() -> None:
    transactions = parse_wells_fargo_statement(
        (
            "January 27, 2026 Page 2 of 5\n"
            "Transaction history\n"
            "1/20   Pinellas Cty Sch Payables 260120 E575048859 Jordan Demo  248.00       4,218.13\n"
            "Totals $248.00 $4,218.13\n"
        ),
        "Wells Fargo Everyday Checking",
    )

    assert len(transactions) == 1
    assert transactions[0].flow_type == "income"
    assert transactions[0].category == "Income"


def test_parse_ofx_transactions_extracts_credit_card_expenses_and_payments() -> None:
    transactions = parse_ofx_transactions(
        (
            "<OFX><CREDITCARDMSGSRSV1><CCSTMTTRNRS><BANKTRANLIST>"
            "<STMTTRN><DTPOSTED>20260301</DTPOSTED><TRNAMT>-14.99</TRNAMT>"
            "<FITID>abc123</FITID><NAME>Spotify</NAME></STMTTRN>"
            "<STMTTRN><DTPOSTED>20260302</DTPOSTED><TRNAMT>1200.00</TRNAMT>"
            "<FITID>def456</FITID><NAME>Payment Thank You</NAME></STMTTRN>"
            "</BANKTRANLIST></CCSTMTTRNRS></CREDITCARDMSGSRSV1></OFX>"
        ),
        "Primary card",
        "credit_card",
    )

    assert len(transactions) == 2
    assert transactions[0].flow_type == "expense"
    assert float(transactions[0].amount) == 14.99
    assert transactions[0].metadata is not None
    assert transactions[0].metadata["fitid"] == "abc123"
    assert transactions[1].flow_type == "payment"
    assert float(transactions[1].amount) == 1200.00


def test_extract_transactions_treats_credit_card_csv_returns_as_refunds(tmp_path: Path) -> None:
    csv_path = tmp_path / "credit-card-activity.csv"
    csv_path.write_text(
        (
            "Date,Description,Amount\n"
            "04/02/2026,AMAZON MKTPLACE PMTS | Return,30.82\n"
            "04/01/2026,Amazon.com*B1234 | Sale,-79.98\n"
        ),
        encoding="utf-8",
    )

    transactions = extract_transactions(
        filename=csv_path.name,
        source_type="credit_card",
        document_type="statement",
        extracted_text="credit card csv preview",
        structured_data={},
        account_label="Amazon Chase (CC)",
        review_summary="Credit card export.",
        stored_path=csv_path,
    )

    assert len(transactions) == 2
    assert transactions[0].flow_type == "refund"
    assert float(transactions[0].amount) == 30.82
    assert transactions[0].category == "Retail"
    assert transactions[1].flow_type == "expense"


def test_extract_transactions_parses_generic_cash_management_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "History_for_Account_Z00000001.csv"
    csv_path.write_text(
        (
            "Run Date,Action,Symbol,Description,Type,Price ($),Quantity,Commission ($),"
            "Fees ($),Accrued Interest ($),Amount ($),Cash Balance ($),Settlement Date\n"
            "04/08/2026,\"DIRECT DEBIT DUKEENERGY BILL PAY (Cash)\",,No Description,Cash,,0.000,,,,-142.25,39400.59,\n"
            "04/06/2026,\"Electronic Funds Transfer Received (Cash)\",,No Description,Cash,,0.000,,,,6000,39542.84,\n"
            "03/31/2026,\"REINVESTMENT FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash)\",SPAXX,\"FIDELITY GOVERNMENT MONEY MARKET\",Cash,1,91.96,,,,-91.96,33542.84,\n"
            "03/31/2026,\"DIVIDEND RECEIVED FIDELITY GOVERNMENT MONEY MARKET (SPAXX) (Cash)\",SPAXX,\"FIDELITY GOVERNMENT MONEY MARKET\",Cash,,0.000,,,,91.96,33542.84,\n"
            "03/27/2026,\"DIRECT DEBIT CHASE CREDIT CEPAY (Cash)\",,No Description,Cash,,0.000,,,,-6178.67,33485.87,\n"
        ),
        encoding="utf-8",
    )

    transactions = extract_transactions(
        filename=csv_path.name,
        source_type="brokerage",
        document_type="brokerage_statement",
        extracted_text="brokerage csv preview",
        structured_data={"account_hint": "Cash Management (Joint WROS)"},
        account_label="Cash Management (Joint WROS)",
        review_summary="Brokerage statement with investable assets and account activity.",
        stored_path=csv_path,
    )

    assert len(transactions) == 5
    assert [transaction.flow_type for transaction in transactions] == [
        "expense",
        "transfer_in",
        "investment",
        "income",
        "transfer_out",
    ]
    assert [transaction.category for transaction in transactions] == [
        "Bills",
        "Transfers",
        "Transfers",
        "Income",
        "Transfers",
    ]
    assert transactions[0].account_label == "Cash Management (Joint WROS)"
    assert float(transactions[0].amount) == 142.25
    assert float(transactions[1].amount) == 6000.00
    assert transactions[0].metadata is not None
    assert transactions[0].metadata["source"] == "statement_csv"
    assert transactions[0].metadata["balance_after"] == "39400.59"


def test_extract_transactions_treats_fidelity_trades_as_investment_activity(tmp_path: Path) -> None:
    csv_path = tmp_path / "Accounts_History.csv"
    csv_path.write_text(
        (
            "Run Date,Action,Symbol,Description,Type,Price ($),Quantity,Commission ($),"
            "Fees ($),Accrued Interest ($),Amount ($),Cash Balance ($),Settlement Date\n"
            "05/01/2026,\"YOU BOUGHT VANGUARD WORLD FD INF TECH ETF (VGT) (Cash)\",VGT,"
            "\"VANGUARD WORLD FD INF TECH ETF\",Cash,628.56,20.576,,,,"
            "-12933.20,26151.07,\n"
            "05/08/2026,\"YOU SOLD VANGUARD WORLD FD INF TECH ETF (VGT) (Cash)\",VGT,"
            "\"VANGUARD WORLD FD INF TECH ETF\",Cash,672.52,20.524,,,,"
            "13803.39,39954.46,\n"
        ),
        encoding="utf-8",
    )

    transactions = extract_transactions(
        filename=csv_path.name,
        source_type="brokerage",
        document_type="brokerage_statement",
        extracted_text="Fidelity activity history",
        structured_data={"account_hint": "Fidelity activity history"},
        account_label="Fidelity activity history",
        review_summary="Brokerage activity export.",
        stored_path=csv_path,
    )

    assert [transaction.flow_type for transaction in transactions] == [
        "investment",
        "investment",
    ]
    assert [transaction.category for transaction in transactions] == [
        "Transfers",
        "Transfers",
    ]
    assert all(
        not is_budget_driving_expense(
            flow_type=transaction.flow_type,
            category=transaction.category,
            description=transaction.description,
            merchant=transaction.raw_merchant,
        )
        for transaction in transactions
    )


def test_effective_classification_maps_plaid_taxonomy_to_compact_categories() -> None:
    assert _effective_transaction_classification(
        flow_type="expense",
        raw_merchant="Kekes Breakfast Cafe",
        description="KEKES BREAKFAST CAFE",
        amount=40.07,
        stored_category="Food And Drink Restaurant",
        stored_essentiality="essential",
        merchant_metadata=None,
    ) == ("Dining", "discretionary")
    assert _effective_transaction_classification(
        flow_type="expense",
        raw_merchant="Wayfair",
        description="WF *WAYFAIR4311426181",
        amount=1545.0,
        stored_category="Home Improvement Furniture",
        stored_essentiality="discretionary",
        merchant_metadata=None,
    ) == ("Home", "discretionary")


def test_spend_total_between_uses_collapsed_canonical_rows() -> None:
    service = HouseholdTransactionService.__new__(HouseholdTransactionService)
    service._load_report_rows = lambda: [
        {
            "date": date(2026, 5, 6),
            "merchant": "Walmart (Store #5831)",
            "description": "Walmart receipt",
            "amount": 278.07,
            "category": "Household",
            "essentiality": "mixed",
            "account_label": "Amazon Chase (CC)",
            "document_id": "receipt-doc",
            "document_type": "receipt",
            "source_type": "receipt",
            "source_kind": "transaction",
            "row_hash": "receipt",
        },
        {
            "date": date(2026, 5, 7),
            "merchant": "Walmart (Store #5831)",
            "description": "Walmart",
            "amount": 278.07,
            "category": "Household",
            "essentiality": "mixed",
            "account_label": "Amazon Chase (CC)",
            "document_id": "plaid-doc",
            "document_type": "api_sync",
            "source_type": "plaid",
            "source_kind": "transaction",
            "row_hash": "plaid",
        },
        {
            "date": date(2026, 5, 8),
            "merchant": "Amazon",
            "description": "Amazon",
            "amount": 40.0,
            "category": "Retail",
            "essentiality": "discretionary",
            "account_label": "Amazon Chase (CC)",
            "document_id": "plaid-doc",
            "document_type": "api_sync",
            "source_type": "plaid",
            "source_kind": "transaction",
            "row_hash": "amazon",
        },
    ]

    assert service.spend_total_between(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 31),
    ) == 318.07


def test_merchant_aliases_collapse_walmart_variants() -> None:
    aliases = _merchant_aliases("WM SUPERCENTER #5831 ANYTOWN ST")

    assert "walmart" in aliases
    assert "wm supercenter" in aliases
    assert "wmsupercenter" in aliases


def test_import_document_transactions_holds_future_dated_receipts_for_review() -> None:
    service = HouseholdTransactionService()
    fake_storage = _FakeStorage()
    service.storage = fake_storage
    future_date = date(date.today().year + 1, 9, 3)

    result = service.import_document_transactions(
        document=SimpleNamespace(
            id="doc-1",
            filename="walmart.pdf",
            source_type="receipt",
            document_type="receipt",
            account_label=None,
        ),
        reviewed={
            "source_type": "receipt",
            "document_type": "receipt",
            "summary": "Walmart receipt",
            "extracted_text": f"{future_date:%m/%d/%Y} Order details - Walmart.com",
            "structured_data": {
                "merchant": "Walmart",
                "total_amount": "164.14",
                "account_hint": "Visa Credit ****4635",
            },
        },
    )

    assert result == {"inserted": 0, "updated": 0, "deleted": 0, "deduplicated": 0, "held_for_date_review": 1}
    assert fake_storage.conn.committed is True
    assert not any("INSERT INTO household_transactions" in sql for sql, _ in fake_storage.conn.executed)
    assert any("DELETE FROM household_transactions" in sql for sql, _ in fake_storage.conn.executed)
    metadata_update = fake_storage.conn.executed[-1][1]
    assert metadata_update is not None
    assert '"date_quality_summary"' in metadata_update[0]
    assert '"held_for_date_review": 1' in metadata_update[0]


def test_extract_transactions_uses_structured_multi_receipt_rows() -> None:
    transactions = extract_transactions(
        filename="receipts.jpg",
        source_type="receipt",
        document_type="receipt",
        extracted_text="Ulta 05/04/2026 Target 05/04/2026",
        structured_data={
            "merchant": "Ulta Beauty; Target",
            "account_hint": "Visa ending 9728",
            "transactions": [
                {
                    "date": "2026-05-04",
                    "merchant": "Ulta Beauty",
                    "amount": "34.96",
                    "currency": "USD",
                    "payment_method": "Visa credit",
                    "account_mask": "9728",
                    "line_items": [
                        {"description": "Tarte XL Tubing Mascara Black", "amount": "28.00"},
                    ],
                },
                {
                    "date": "2026-05-04",
                    "merchant": "Target",
                    "amount": "72.89",
                    "currency": "USD",
                    "payment_method": "Visa credit",
                    "account_mask": "9728",
                },
            ],
        },
        account_label=None,
        review_summary="Receipt image contains Ulta and Target purchases.",
        stored_path=None,
    )

    assert [transaction.raw_merchant for transaction in transactions] == [
        "Ulta Beauty",
        "Target",
    ]
    assert [transaction.amount for transaction in transactions] == [
        Decimal("34.96"),
        Decimal("72.89"),
    ]
    assert all(
        transaction.metadata is not None
        and transaction.metadata["source"] == "receipt_transaction"
        for transaction in transactions
    )
    assert transactions[0].metadata is not None
    assert transactions[0].metadata["line_items"] == [
        {"description": "Tarte XL Tubing Mascara Black", "amount": "28.00"},
    ]


def test_import_document_transactions_keeps_transfer_categories_even_with_old_merchant_rule() -> None:
    service = HouseholdTransactionService()
    service.storage = _MerchantOverrideStorage()

    result = service.import_document_transactions(
        document=SimpleNamespace(
            id="doc-merchant-override",
            filename="wells.pdf",
            source_type="bank",
            document_type="statement",
            account_label="Wells Fargo Everyday Checking",
        ),
        reviewed={
            "source_type": "bank",
            "document_type": "statement",
            "summary": "Wells Fargo statement",
            "extracted_text": (
                "February 25, 2026 Page 2 of 5\n"
                "Transaction history\n"
                "2/17   Chase Credit Crd Epay 260215 9126729844 Alex Demo  5,645.34       1,100.00\n"
                "Totals $5,645.34 $1,100.00\n"
            ),
            "structured_data": {},
        },
    )

    assert result == {"inserted": 1, "updated": 0, "deleted": 0, "deduplicated": 0, "held_for_date_review": 0}
    assert service.storage.conn.insert_params is not None
    assert service.storage.conn.insert_params[12] == "transfer_out"
    assert service.storage.conn.insert_params[13] == "Transfers"
    assert service.storage.conn.insert_params[14] == "mixed"


def test_build_reports_excludes_cash_movement_rows_even_when_stored_as_expense() -> None:
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-card-payment",
                    None,
                    datetime(2026, 2, 17, tzinfo=UTC),
                    "Chase Credit Crd Epay 260215 9126729844 Alex Demo",
                    "Chase Credit Crd Epay 260215 9126729844 Alex Demo",
                    Decimal("5645.34"),
                    "Bills",
                    "essential",
                    "expense",
                    "Wells Fargo Everyday Checking",
                    "doc-card-payment",
                    "Chase Credit Crd Epay 260215 9126729844 Alex Demo",
                    "statement",
                    "bank",
                    "payment.csv",
                    "hash-card-payment",
                    {},
                ),
                (
                    "txn-utility",
                    None,
                    datetime(2026, 2, 9, tzinfo=UTC),
                    "Dukeenergy Bill Pay 910066616132 Alex Demo",
                    "Dukeenergy Bill Pay 910066616132 Alex Demo",
                    Decimal("177.51"),
                    "Bills",
                    "essential",
                    "expense",
                    "Wells Fargo Everyday Checking",
                    "doc-utility",
                    "Dukeenergy Bill Pay 910066616132 Alex Demo",
                    "statement",
                    "bank",
                    "utility.csv",
                    "hash-utility",
                    {},
                ),
            ],
            [],
        ]
    )

    reports = service.build_reports()

    assert reports.executive.average_monthly_spend == 177.51
    assert reports.executive.average_monthly_essentials == 177.51
    assert reports.executive.tracked_expense_count == 1
    assert [transaction.merchant for transaction in reports.recent_transactions] == [
        "Dukeenergy Bill Pay 910066616132 Alex Demo"
    ]


def test_build_spending_view_keeps_venmo_payments_visible_as_peer_payments_spend() -> None:
    today = date.today()
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-venmo",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "Venmo Payment 260117 1047668918292 Jordan Demo",
                    "Venmo Payment 260117 1047668918292 Jordan Demo",
                    Decimal("30.00"),
                    "Household",
                    "mixed",
                    "expense",
                    "Wells Fargo Everyday Checking",
                    "doc-venmo",
                    "Venmo Payment 260117 1047668918292 Jordan Demo",
                    "statement",
                    "bank",
                    "venmo.csv",
                    "hash-venmo",
                    {},
                ),
                (
                    "txn-utility",
                    None,
                    datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=UTC),
                    "Dukeenergy Bill Pay 910066616132 Alex Demo",
                    "Dukeenergy Bill Pay 910066616132 Alex Demo",
                    Decimal("177.51"),
                    "Bills",
                    "essential",
                    "expense",
                    "Wells Fargo Everyday Checking",
                    "doc-utility",
                    "Dukeenergy Bill Pay 910066616132 Alex Demo",
                    "statement",
                    "bank",
                    "utility.csv",
                    "hash-utility",
                    {},
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    assert spending.summary.total_spend == 207.51
    assert spending.summary.transaction_count == 2
    categories = {row.description: row.category for row in spending.transactions}
    assert categories["Venmo Payment 260117 1047668918292 Jordan Demo"] == "Peer Payments"
    assert {row.description for row in spending.transactions} == {
        "Dukeenergy Bill Pay 910066616132 Alex Demo",
        "Venmo Payment 260117 1047668918292 Jordan Demo",
    }


def test_effective_classification_normalizes_raw_loan_payment_enum() -> None:
    category, essentiality = _effective_transaction_classification(
        flow_type="expense",
        raw_merchant="Copa Arc",
        description="Copa ARC 2307415340700",
        amount=504.26,
        stored_category="LOAN_PAYMENTS_OTHER_PAYMENT",
        stored_essentiality="essential",
        merchant_metadata=None,
    )
    assert (category, essentiality) == ("Debt Payments", "mixed")


def test_effective_classification_never_echoes_unknown_raw_enum() -> None:
    category, _essentiality = _effective_transaction_classification(
        flow_type="expense",
        raw_merchant="Mystery Vendor",
        description="MYSTERY VENDOR 4471",
        amount=42.0,
        stored_category="SOME_UNKNOWN_ENUM_VALUE",
        stored_essentiality="mixed",
        merchant_metadata=None,
    )
    assert category == "Household"
    assert "_" not in category


def test_build_spending_view_excludes_loan_payments_from_spend() -> None:
    today = date.today()
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-loan",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "Copa ARC 2307415340700",
                    "Copa Arc",
                    Decimal("504.26"),
                    "LOAN_PAYMENTS_OTHER_PAYMENT",
                    "essential",
                    "expense",
                    "Plaid Checking",
                    "doc-loan",
                    "Copa Arc",
                    "statement",
                    "bank",
                    "plaid.csv",
                    "hash-loan",
                    {},
                ),
                (
                    "txn-dining",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "Chipotle 1180 Anytown",
                    "Chipotle 1180 Anytown",
                    Decimal("12.50"),
                    "Dining",
                    "discretionary",
                    "expense",
                    "Chase card",
                    "doc-dining",
                    "Chipotle",
                    "statement",
                    "credit_card",
                    "chase.csv",
                    "hash-dining",
                    {},
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    assert spending.summary.total_spend == 12.50
    assert spending.summary.transaction_count == 1
    surfaced = {row.category for row in spending.transactions}
    assert "LOAN_PAYMENTS_OTHER_PAYMENT" not in surfaced
    assert "Debt Payments" not in surfaced
    assert surfaced == {"Dining"}


def test_build_spending_view_separates_refund_gross_and_income() -> None:
    today = date.today()
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-buy",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "AMAZON MKTPL purchase",
                    "AMAZON MKTPL purchase",
                    Decimal("100.00"),
                    "Retail",
                    "discretionary",
                    "expense",
                    "Chase card",
                    "doc-buy",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "chase.csv",
                    "hash-buy",
                    {},
                ),
                (
                    "txn-return",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "AMAZON RETURN credit",
                    "AMAZON RETURN credit",
                    Decimal("30.00"),
                    "Retail",
                    "discretionary",
                    "refund",
                    "Chase card",
                    "doc-return",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "chase.csv",
                    "hash-return",
                    {},
                ),
            ],
            [],
            [(2000.0,)],
        ]
    )

    spending = service.build_spending_view(window="1m")

    retail = next(c for c in spending.categories if c.category == "Retail")
    # Net spend is refund-reduced, but gross (the cap basis) and the refund stay visible.
    assert retail.average_monthly_spend == 70.0
    assert retail.gross_monthly_spend == 100.0
    assert retail.refund_total == 30.0
    assert spending.summary.total_income == 2000.0
    assert spending.summary.net_cash_flow == 1930.0
    assert spending.summary.savings_rate == 0.965


def test_build_spending_view_uses_selected_timeframe_and_full_filtered_rows() -> None:
    today = date.today()
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-amazon",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "AMAZON MKTPL*B70K66JV1 | Sale",
                    "AMAZON MKTPL*B70K66JV1 | Sale",
                    Decimal("41.81"),
                    "Retail",
                    "discretionary",
                    "expense",
                    "Chase Amazon card",
                    "doc-amazon",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "chase.csv",
                    "hash-amazon",
                    {},
                ),
                (
                    "txn-grocery",
                    None,
                    datetime.combine(today.replace(day=max(today.day - 5, 1)), datetime.min.time(), tzinfo=UTC),
                    "WM SUPERCENTER #5831 | Sale",
                    "WM SUPERCENTER #5831 | Sale",
                    Decimal("155.75"),
                    "Groceries",
                    "essential",
                    "expense",
                    "Chase Amazon card",
                    "doc-grocery",
                    "Walmart (Store #5831)",
                    "statement",
                    "credit_card",
                    "chase.csv",
                    "hash-grocery",
                    {},
                ),
                (
                    "txn-old",
                    None,
                    datetime.combine(today - timedelta(days=75), datetime.min.time(), tzinfo=UTC),
                    "OLD GROCERY",
                    "OLD GROCERY",
                    Decimal("75.00"),
                    "Groceries",
                    "essential",
                    "expense",
                    "Old card",
                    "doc-old",
                    "Old Grocery",
                    "statement",
                    "credit_card",
                    "old.csv",
                    "hash-old",
                    {},
                ),
            ],
            [
                (
                    "import-amazon",
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "Amazon",
                    "AMAZON MKTPL*B70K66JV1 | Sale",
                    Decimal("41.81"),
                    "amazon_order_history",
                    "doc-import",
                    {"account_label": "Visa - 9728"},
                    "order_history.csv",
                    "hash-import",
                ),
            ],
        ]
    )

    spending = service.build_spending_view(window="1m")

    assert spending.summary.timeframe_key == "1m"
    assert spending.summary.transaction_count == 2
    assert round(spending.summary.total_spend, 2) == 197.56
    assert spending.summary.coverage_months == 1
    assert spending.summary.average_monthly_spend == 197.56
    assert [category.category for category in spending.categories] == [
        "Household",
        "Retail",
    ]
    assert len(spending.transactions) == 2
    assert [row.merchant for row in spending.transactions] == [
        "Amazon",
        "Walmart (Store #5831)",
    ]
    assert [row.id for row in spending.transactions] == ["txn-amazon", "txn-grocery"]
    assert all(row.source_kind == "transaction" for row in spending.transactions)
    assert [
        (point.month, point.category, point.total_spend)
        for point in spending.category_monthly_trend
    ] == [
        (today.strftime("%Y-%m"), "Household", 155.75),
        (today.strftime("%Y-%m"), "Retail", 41.81),
    ]


def test_build_spending_view_nets_credit_card_returns_against_spend() -> None:
    today = date.today()
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-sale",
                    "acct-chase",
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "AMAZON MKTPL*B70K66JV1 | Sale",
                    "AMAZON MKTPL*B70K66JV1 | Sale",
                    Decimal("79.98"),
                    "Retail",
                    "discretionary",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-sale",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "activity.csv",
                    "hash-sale",
                    {},
                ),
                (
                    "txn-return",
                    "acct-chase",
                    datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=UTC),
                    "AMAZON MKTPLACE PMTS | Return",
                    "Amazon",
                    Decimal("30.82"),
                    "Transfers",
                    "mixed",
                    "payment",
                    "Amazon Chase (CC)",
                    "doc-return",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "activity.csv",
                    "hash-return",
                    {},
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    assert spending.summary.transaction_count == 2
    assert spending.summary.total_spend == 49.16
    assert len(spending.categories) == 1
    assert spending.categories[0].category == "Retail"
    assert spending.categories[0].total_spend == 49.16
    assert [row.amount for row in spending.transactions] == [79.98, -30.82]


def test_build_spending_view_surfaces_unknown_category_for_review_rows() -> None:
    today = date.today()
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-unknown",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "MYSTERY POS PURCHASE",
                    "MYSTERY POS PURCHASE",
                    Decimal("44.12"),
                    None,
                    None,
                    "expense",
                    "Checking",
                    "doc-unknown",
                    "Mystery merchant",
                    "statement",
                    "bank",
                    "checking.csv",
                    "hash-unknown",
                    {},
                    Decimal("0.42"),
                    {"audit": {"status": "needs_review"}},
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    assert spending.categories[0].category == "Unknown"
    assert spending.categories[0].transaction_count == 1
    assert spending.transactions[0].category == "Unknown"
    assert spending.transactions[0].needs_category_review is True
    assert spending.transactions[0].category_confidence == 0.42


def test_build_spending_view_keeps_statement_and_activity_rows_for_db_dedup() -> None:
    # household_transaction_dedup_service removes true statement/activity
    # duplicates at the DB layer (removed=TRUE never reaches this view), so the
    # view must not merge surviving rows — legitimate same-day same-amount
    # pairs survive the DB dedup on purpose.
    today = date.today()
    household_account_id = "acct-chase"
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-statement",
                    household_account_id,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "Amazon.com*BD3JQ51U1 Amzn.com/bill WA",
                    "AMAZON MKTPL*BD3JQ51U1",
                    Decimal("26.76"),
                    "Retail",
                    "discretionary",
                    "expense",
                    "Chase Amazon card",
                    "doc-statement",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-statement",
                    {},
                ),
                (
                    "txn-export",
                    household_account_id,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "Amazon.com*BD3JQ51U1 | Sale",
                    "Amazon",
                    Decimal("26.76"),
                    "Retail",
                    "discretionary",
                    "expense",
                    "Chase credit card activity export",
                    "doc-export",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "activity.csv",
                    "hash-export",
                    {},
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    assert spending.summary.transaction_count == 2
    assert spending.summary.total_spend == 53.52
    assert len(spending.transactions) == 2


def test_build_spending_view_keeps_phone_and_location_variant_rows_for_db_dedup() -> None:
    today = date.today()
    household_account_id = "acct-chase"
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-statement",
                    household_account_id,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "Spotify USA 877-7781161 NY",
                    "Spotify USA 877-7781161 NY",
                    Decimal("21.58"),
                    "Household",
                    "mixed",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-statement",
                    "Spotify USA 877-7781161 NY",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-statement",
                    {},
                ),
                (
                    "txn-export",
                    household_account_id,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "Spotify USA | Sale",
                    "Spotify USA | Sale",
                    Decimal("21.58"),
                    "Household",
                    "mixed",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-export",
                    "Spotify USA | Sale",
                    "statement",
                    "credit_card",
                    "activity.csv",
                    "hash-export",
                    {},
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    assert spending.summary.transaction_count == 2
    assert spending.summary.total_spend == 43.16
    assert len(spending.transactions) == 2
    assert all(txn.category == "Subscriptions" for txn in spending.transactions)


def test_build_spending_view_reclassifies_obvious_household_miscategorizations() -> None:
    today = date.today()
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-thai",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "THAI BAY & SUSHI RESTAURA | Sale",
                    "THAI BAY & SUSHI RESTAURA | Sale",
                    Decimal("127.96"),
                    "Household",
                    "mixed",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-thai",
                    "THAI BAY & SUSHI RESTAURA | Sale",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-thai",
                    {},
                ),
                (
                    "txn-frontier",
                    None,
                    datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=UTC),
                    "DIRECT DEBIT FRONTIER COMMUBILL PAY (Cash)",
                    "DIRECT DEBIT FRONTIER COMMUBILL PAY (Cash)",
                    Decimal("34.99"),
                    "Household",
                    "mixed",
                    "expense",
                    "Cash Management Account (CMA)",
                    "doc-frontier",
                    "DIRECT DEBIT FRONTIER COMMUBILL PAY (Cash)",
                    "brokerage_statement",
                    "brokerage",
                    "cash.csv",
                    "hash-frontier",
                    {},
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    categories = {tx.description: tx.category for tx in spending.transactions}
    assert categories["THAI BAY & SUSHI RESTAURA | Sale"] == "Dining"
    assert categories["DIRECT DEBIT FRONTIER COMMUBILL PAY (Cash)"] == "Bills"


def test_build_spending_view_treats_mixed_big_box_merchants_conservatively() -> None:
    today = date.today()
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-walmart-store",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "WM SUPERCENTER #5831 | Sale",
                    "WM SUPERCENTER #5831 | Sale",
                    Decimal("155.75"),
                    "Groceries",
                    "essential",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-walmart-store",
                    "WM SUPERCENTER #5831 | Sale",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-walmart-store",
                    {},
                ),
                (
                    "txn-walmart-online",
                    None,
                    datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=UTC),
                    "WALMART.COM 800-925-6278 AR",
                    "WALMART.COM 800-925-6278 AR",
                    Decimal("181.84"),
                    "Groceries",
                    "essential",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-walmart-online",
                    "WALMART.COM 800-925-6278 AR",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-walmart-online",
                    {},
                ),
                (
                    "txn-publix",
                    None,
                    datetime.combine(today - timedelta(days=2), datetime.min.time(), tzinfo=UTC),
                    "PUBLIX #1309 | Sale",
                    "PUBLIX #1309 | Sale",
                    Decimal("45.88"),
                    "Household",
                    "mixed",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-publix",
                    "PUBLIX #1309 | Sale",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-publix",
                    {},
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    categories = {tx.description: tx.category for tx in spending.transactions}
    assert categories["WM SUPERCENTER #5831 | Sale"] == "Household"
    assert categories["WALMART.COM 800-925-6278 AR"] == "Retail"
    assert categories["PUBLIX #1309 | Sale"] == "Groceries"


def test_build_spending_view_reclassifies_auto_and_airport_merchants() -> None:
    today = date.today()
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-jiffy",
                    None,
                    datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    "JIFFY LUBE #886 | Sale",
                    "JIFFY LUBE #886 | Sale",
                    Decimal("32.09"),
                    "Household",
                    "mixed",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-jiffy",
                    "JIFFY LUBE #886 | Sale",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-jiffy",
                    {},
                ),
                (
                    "txn-airport",
                    None,
                    datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=UTC),
                    "International Tampa | Sale",
                    "International Tampa | Sale",
                    Decimal("7.68"),
                    "Subscriptions",
                    "discretionary",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-airport",
                    "International Tampa | Sale",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-airport",
                    {},
                ),
                (
                    "txn-bucees",
                    None,
                    datetime.combine(today - timedelta(days=2), datetime.min.time(), tzinfo=UTC),
                    "BUC-EE'S #0051 FORT VALLEY GA",
                    "BUC-EE'S #0051 FORT VALLEY GA",
                    Decimal("67.18"),
                    "Household",
                    "mixed",
                    "expense",
                    "Amazon Chase (CC)",
                    "doc-bucees",
                    "BUC-EE'S #0051 FORT VALLEY GA",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-bucees",
                    {},
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    categories = {tx.description: tx.category for tx in spending.transactions}
    assert categories["JIFFY LUBE #886 | Sale"] == "Transportation"
    assert categories["International Tampa | Sale"] == "Travel"
    assert categories["BUC-EE'S #0051 FORT VALLEY GA"] == "Gas"


def test_dates_to_cadence_accepts_two_observations_as_provisional_signal() -> None:
    service = HouseholdTransactionService()

    cadence = service._dates_to_cadence(
        [date(2026, 1, 7), date(2026, 2, 9)]
    )

    assert cadence is not None
    assert cadence["label"] == "likely monthly"
    assert cadence["confidence"] == 0.62
