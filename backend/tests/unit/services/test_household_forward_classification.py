"""Forward classification of imported household transactions."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services._household_merchants import (
    _classify_merchant,
    _classify_wells_flow,
    _effective_transaction_classification,
)
from app.services._household_transaction_parsers import (
    _classify_statement_csv_flow,
    parse_chase_statement,
    parse_ofx_transactions,
)
from app.services.household_ledger_service import _entry_direction


@pytest.mark.parametrize("amount", [12.00, 950.00])
def test_unknown_merchant_is_not_classified_by_amount_alone(amount: float) -> None:
    assert _classify_merchant(
        raw_merchant="Unidentified Shop",
        description="Unidentified Shop",
        amount=amount,
    ) == ("Household", "mixed")


def test_known_merchant_evidence_still_classifies_without_amount_shortcuts() -> None:
    assert _classify_merchant(
        raw_merchant="Depop", description="Depop", amount=10.00
    ) == ("Retail", "discretionary")
    assert _classify_merchant(
        raw_merchant="Spotify", description="Spotify", amount=12.00
    ) == ("Subscriptions", "discretionary")
    assert _classify_merchant(
        raw_merchant="Duke Energy", description="Duke Energy", amount=950.00
    ) == ("Bills", "essential")
    assert _classify_merchant(
        raw_merchant="Costco Gas", description="Costco Gas", amount=45.00
    ) == ("Gas", "essential")
    assert _classify_merchant(
        raw_merchant="Sephora", description="Sephora", amount=45.00
    ) == ("Personal Care", "discretionary")
    assert _classify_merchant(
        raw_merchant="SEAWORLD-FOOD SVC", description="SEAWORLD-FOOD SVC", amount=45.00
    ) == ("Dining", "discretionary")
    assert _classify_merchant(
        raw_merchant="Nanonoble", description="Nanonoble", amount=45.00
    ) == ("Subscriptions", "discretionary")
    assert _classify_merchant(
        raw_merchant="NIC FL SUNBIZ", description="NIC FL SUNBIZ", amount=25.00
    ) == ("Bills", "essential")


@pytest.mark.parametrize(
    ("description", "expected_flow", "expected_category"),
    [
        ("Payment Thank You-Mobile", "payment", "Transfers"),
        ("Depop", "refund", "Retail"),
        ("AIRBNB", "refund", "Travel"),
        ("Card Credit", "credit", "Unknown"),
    ],
)
def test_positive_card_csv_credit_distinguishes_payment_from_merchant_credit(
    description: str, expected_flow: str, expected_category: str
) -> None:
    merchant_category, merchant_essentiality = _classify_merchant(
        raw_merchant=description, description=description, amount=25.00
    )
    flow, category, _ = _classify_statement_csv_flow(
        description=description,
        source_type="credit_card",
        signed_amount=Decimal("25.00"),
        category=merchant_category,
        essentiality=merchant_essentiality,
    )
    assert (flow, category) == (expected_flow, expected_category)


def test_positive_card_ofx_merchant_credit_is_refund() -> None:
    transactions = parse_ofx_transactions(
        (
            "<STMTTRN><DTPOSTED>20260301</DTPOSTED><TRNAMT>25.00</TRNAMT>"
            "<NAME>Depop</NAME></STMTTRN>"
        ),
        "Primary card",
        "credit_card",
    )

    assert len(transactions) == 1
    assert (transactions[0].flow_type, transactions[0].category) == ("refund", "Retail")


def test_positive_card_ofx_ambiguous_credit_stays_out_of_income_and_spend() -> None:
    transactions = parse_ofx_transactions(
        "<STMTTRN><DTPOSTED>20260301</DTPOSTED><TRNAMT>25.00</TRNAMT><NAME>Card Credit</NAME></STMTTRN>",
        "Primary card",
        "credit_card",
    )

    assert [(row.flow_type, row.category) for row in transactions] == [
        ("credit", "Unknown")
    ]


def test_chase_statement_negative_merchant_credit_is_refund() -> None:
    transactions = parse_chase_statement(
        (
            "ALEX DEMO Page 2 of 4 Statement Date: 01/11/26\n"
            "Date of\n"
            "Transaction Merchant Name or Transaction Description $ Amount\n"
            "12/11 & Depop -25.00\n"
            "12/23 & Payment Thank You-Mobile -100.00\n"
        ),
        "Chase card",
    )

    assert [(row.flow_type, row.category) for row in transactions] == [
        ("refund", "Retail"),
        ("payment", "Transfers"),
    ]


def test_unresolved_credit_is_visible_as_unknown_credit_in_ledger() -> None:
    assert _entry_direction("credit", 25.00) == "credit"
    assert _effective_transaction_classification(
        flow_type="credit",
        raw_merchant="Card Credit",
        description="Card Credit",
        amount=25.00,
        stored_category="Unknown",
        stored_essentiality="mixed",
        merchant_metadata=None,
        categorization_source="plaid",
    ) == ("Unknown", "mixed")


def test_confirmed_property_zelle_receipt_is_income_only_with_source_and_memo() -> None:
    description = "ZELLE FROM MICHAEL WILEY MORTGAGE PAYMENT ON THE PROPERTY AT 8"
    assert _classify_wells_flow(description) == "income"
    assert _classify_statement_csv_flow(
        description=description,
        source_type="bank",
        signed_amount=Decimal("506.31"),
        category="Transfers",
        essentiality="mixed",
    ) == ("income", "Income", "essential")
    assert _classify_wells_flow("Zelle From Brother Mortgage Payment") == "transfer_in"
    assert _classify_wells_flow("Zelle From Michael Wiley") == "transfer_in"
