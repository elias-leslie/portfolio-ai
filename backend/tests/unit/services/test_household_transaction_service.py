"""Unit tests for household transaction extraction and normalization."""

from __future__ import annotations

from app.services.household_transaction_service import (
    HouseholdTransactionService,
    _merchant_aliases,
)


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


def test_merchant_aliases_collapse_walmart_variants() -> None:
    aliases = _merchant_aliases("WM SUPERCENTER #5831 LARGO FL")

    assert "walmart" in aliases
    assert "wm supercenter" in aliases
    assert "wmsupercenter" in aliases
