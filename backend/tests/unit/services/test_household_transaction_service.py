"""Unit tests for household transaction extraction and normalization."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
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


def test_parse_chase_statement_extracts_walmart_activity_lines() -> None:
    service = HouseholdTransactionService()

    transactions = service._parse_chase_statement(
        (
            "ELIAS B LESLIE Page 2 of 4 Statement Date: 01/11/26\n"
            "Date of Transaction Merchant Name or Transaction Description $ Amount\n"
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
    assert transactions[0].metadata["fitid"] == "abc123"
    assert transactions[1].flow_type == "payment"
    assert float(transactions[1].amount) == 1200.00


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
