"""Unit tests for household transaction extraction and normalization."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.services.household_transaction_service import (
    HouseholdTransactionService,
    _merchant_aliases,
)


class _FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any] | None]] = []
        self.committed = False

    def execute(self, sql: str, params: list[Any] | None = None) -> _FakeConnection:
        self.executed.append((sql, params))
        return self

    def fetchone(self) -> tuple[bool]:
        return (True,)

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
        rows = self._responses.pop(0)
        return SimpleNamespace(fetchall=lambda: rows)


class _SequenceStorage:
    def __init__(self, responses: list[list[tuple[Any, ...]]]) -> None:
        self.conn = _SequenceConnection(responses)

    @contextmanager
    def connection(self):
        yield self.conn


def test_parse_chase_statement_extracts_walmart_activity_lines() -> None:
    service = HouseholdTransactionService()

    transactions = service._parse_chase_statement(
        (
            "ELIAS B LESLIE Page 2 of 4 Statement Date: 01/11/26\n"
            "Date of\n"
            "Transaction Merchant  Name or Transaction Description $ Amount\n"
            "12/11 & WAL-MART #5831 LARGO FL 149.21\n"
            "12/12 & WM SUPERCENTER #5831 LARGO FL 30.00\n"
            "12/23 & Payment Thank You-Mobile -5757.53\n"
        ),
        "Chase Amazon card",
    )

    assert len(transactions) == 3
    assert transactions[0].raw_merchant == "WAL-MART #5831 LARGO FL"
    assert float(transactions[0].amount) == 149.21
    assert transactions[0].flow_type == "expense"
    assert transactions[2].flow_type == "payment"


def test_parse_wells_fargo_statement_extracts_payroll_and_spotify() -> None:
    service = HouseholdTransactionService()

    transactions = service._parse_wells_fargo_statement(
        (
            "February 25, 2026 Page 2 of 5\n"
            "Transaction history\n"
            "2/4   Recurring Payment authorized on 02/03 Spotify P3Efef4F77\n"
            "NEW York NY S346034529890991 Card 2873\n"
            "19.31    8,200.63\n"
            "2/6   Pinellas County Payroll 260206 8859 Leslie Mariana  2,900.41       11,101.04\n"
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
    service = HouseholdTransactionService()

    transactions = service._parse_wells_fargo_statement(
        (
            "February 25, 2026 Page 2 of 5\n"
            "Transaction history\n"
            "2/17   Chase Credit Crd Epay 260215 9126729844 Elias Leslie  5,645.34       1,100.00\n"
            "2/18   Paypal Inst Xfer 260218 Tbl.Leslie Elias Leslie  3,520.25       1,200.00\n"
            "2/18   Zelle From Michael Wiley on 02/18 Ref # Wfct0Ztbcn6L  506.31       1,706.31\n"
            "2/18   FL Deo Ui Benefit 260214 xxxxx5852 Elias B Leslie  247.00       1,953.31\n"
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


def test_parse_ofx_transactions_extracts_credit_card_expenses_and_payments() -> None:
    service = HouseholdTransactionService()

    transactions = service._parse_ofx_transactions(
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


def test_extract_transactions_parses_generic_cash_management_csv(tmp_path: Path) -> None:
    service = HouseholdTransactionService()
    csv_path = tmp_path / "History_for_Account_Z38367298.csv"
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

    transactions = service._extract_transactions(
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


def test_merchant_aliases_collapse_walmart_variants() -> None:
    aliases = _merchant_aliases("WM SUPERCENTER #5831 LARGO FL")

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

    assert result == {"inserted": 0, "updated": 0, "held_for_date_review": 1}
    assert fake_storage.conn.committed is True
    assert not any("INSERT INTO household_transactions" in sql for sql, _ in fake_storage.conn.executed)
    metadata_update = fake_storage.conn.executed[-1][1]
    assert metadata_update is not None
    assert '"date_quality_summary"' in metadata_update[0]
    assert '"held_for_date_review": 1' in metadata_update[0]


def test_build_reports_excludes_cash_movement_rows_even_when_stored_as_expense() -> None:
    service = HouseholdTransactionService()
    service.storage = _SequenceStorage(
        [
            [
                (
                    "txn-card-payment",
                    None,
                    datetime(2026, 2, 17, tzinfo=UTC),
                    "Chase Credit Crd Epay 260215 9126729844 Elias Leslie",
                    "Chase Credit Crd Epay 260215 9126729844 Elias Leslie",
                    Decimal("5645.34"),
                    "Bills",
                    "essential",
                    "Wells Fargo Everyday Checking",
                    "doc-card-payment",
                    "Chase Credit Crd Epay 260215 9126729844 Elias Leslie",
                    "statement",
                    "bank",
                    "payment.csv",
                    "hash-card-payment",
                ),
                (
                    "txn-utility",
                    None,
                    datetime(2026, 2, 9, tzinfo=UTC),
                    "Dukeenergy Bill Pay 910066616132 Elias B Leslie",
                    "Dukeenergy Bill Pay 910066616132 Elias B Leslie",
                    Decimal("177.51"),
                    "Bills",
                    "essential",
                    "Wells Fargo Everyday Checking",
                    "doc-utility",
                    "Dukeenergy Bill Pay 910066616132 Elias B Leslie",
                    "statement",
                    "bank",
                    "utility.csv",
                    "hash-utility",
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
        "Dukeenergy Bill Pay 910066616132 Elias B Leslie"
    ]


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
                    "Chase Amazon card",
                    "doc-amazon",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "chase.csv",
                    "hash-amazon",
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
                    "Chase Amazon card",
                    "doc-grocery",
                    "Walmart (Store #5831)",
                    "statement",
                    "credit_card",
                    "chase.csv",
                    "hash-grocery",
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
                    "Old card",
                    "doc-old",
                    "Old Grocery",
                    "statement",
                    "credit_card",
                    "old.csv",
                    "hash-old",
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
        "Groceries",
        "Retail",
    ]
    assert len(spending.transactions) == 2
    assert [row.merchant for row in spending.transactions] == [
        "Amazon",
        "Walmart (Store #5831)",
    ]
    assert all(row.source_kind == "transaction" for row in spending.transactions)


def test_build_spending_view_dedupes_same_account_statement_and_activity_rows() -> None:
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
                    "Chase Amazon card",
                    "doc-statement",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "statement.pdf",
                    "hash-statement",
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
                    "Chase credit card activity export",
                    "doc-export",
                    "Amazon",
                    "statement",
                    "credit_card",
                    "activity.csv",
                    "hash-export",
                ),
            ],
            [],
        ]
    )

    spending = service.build_spending_view(window="1m")

    assert spending.summary.transaction_count == 1
    assert spending.summary.total_spend == 26.76
    assert len(spending.transactions) == 1


def test_dates_to_cadence_accepts_two_observations_as_provisional_signal() -> None:
    service = HouseholdTransactionService()

    cadence = service._dates_to_cadence(
        [date(2026, 1, 7), date(2026, 2, 9)]
    )

    assert cadence is not None
    assert cadence["label"] == "likely monthly"
    assert cadence["confidence"] == 0.62
