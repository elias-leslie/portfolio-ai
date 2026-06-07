"""Tests for the Fidelity Activity History CSV parser.

Drives the parser against a representative slice of the actual export
format the user uploaded (multi-account, signed quantities, both buys
and sells, settlement_date column).
"""

from __future__ import annotations

from app.services._household_document_baseline import (
    _classify_fidelity_action,
    _extract_fidelity_activity_history_accounts,
)

_SAMPLE_CSV = (
    '\n\n'
    'Run Date,Account,Account Number,Action,Symbol,Description,Type,'
    'Price ($),Quantity,Commission ($),Fees ($),Accrued Interest ($),'
    'Amount ($),Settlement Date\n'
    '05/08/2026,"Individual - TOD","Z00000002",'
    '"YOU SOLD TESLA INC COM (TSLA) (Cash)",TSLA,"TESLA INC COM",Cash,'
    '426.2,-11,,0.1,,4688.1,05/11/2026\n'
    '05/01/2026,"Traditional IRA","000000001",'
    '"YOU BOUGHT VANGUARD WORLD FD INF TECH ETF (VGT) (Cash)",VGT,'
    '"VANGUARD WORLD FD INF TECH ETF",Cash,104.3,124,,,,-12933.2,05/04/2026\n'
)


def test_parser_returns_brokerage_classification_with_two_accounts() -> None:
    result = _extract_fidelity_activity_history_accounts(extracted_text=_SAMPLE_CSV)
    assert result is not None
    source_type, document_type, confidence, summary, structured = result
    assert source_type == "brokerage"
    assert document_type == "brokerage_statement"
    assert 0.85 < confidence < 1.0
    assert "2 accounts" in summary
    assert "2 transactions" in summary
    accounts: list[dict] = structured["financial_accounts"]  # type: ignore[assignment]
    assert len(accounts) == 2
    masks = {a["account_mask"] for a in accounts}
    assert masks == {"Z00000002", "000000001"}


def test_parser_signs_quantity_and_assigns_transaction_type() -> None:
    result = _extract_fidelity_activity_history_accounts(extracted_text=_SAMPLE_CSV)
    assert result is not None
    structured = result[4]
    accounts: list[dict] = structured["financial_accounts"]  # type: ignore[assignment]
    by_mask = {a["account_mask"]: a for a in accounts}
    sells = by_mask["Z00000002"]["transactions"]
    buys = by_mask["000000001"]["transactions"]
    assert len(sells) == 1
    assert sells[0]["transaction_type"] == "sell"
    assert sells[0]["shares"] == 11.0  # absolute value
    assert sells[0]["symbol"] == "TSLA"
    assert sells[0]["fees"] == 0.1
    assert len(buys) == 1
    assert buys[0]["transaction_type"] == "buy"
    assert buys[0]["shares"] == 124.0
    assert buys[0]["symbol"] == "VGT"


def test_parser_marks_ira_account_type() -> None:
    result = _extract_fidelity_activity_history_accounts(extracted_text=_SAMPLE_CSV)
    assert result is not None
    structured = result[4]
    accounts: list[dict] = structured["financial_accounts"]  # type: ignore[assignment]
    by_mask = {a["account_mask"]: a for a in accounts}
    assert by_mask["Z00000002"]["account_type"] == "brokerage"
    assert by_mask["Z00000002"]["source_type"] == "brokerage"
    assert by_mask["000000001"]["account_type"] == "ira"
    assert by_mask["000000001"]["source_type"] == "retirement"


def test_parser_returns_none_for_non_activity_csv() -> None:
    other_csv = "Date,Description,Amount\n05/08/2026,Coffee,-4.50\n"
    assert _extract_fidelity_activity_history_accounts(extracted_text=other_csv) is None


def test_parser_returns_none_for_empty_input() -> None:
    assert _extract_fidelity_activity_history_accounts(extracted_text=None) is None
    assert _extract_fidelity_activity_history_accounts(extracted_text="") is None


def test_classify_fidelity_action_handles_common_strings() -> None:
    assert _classify_fidelity_action("YOU BOUGHT FOOBAR") == "buy"
    assert _classify_fidelity_action("YOU SOLD FOOBAR") == "sell"
    assert _classify_fidelity_action("REINVESTMENT FOOBAR") == "buy"
    assert _classify_fidelity_action("YOU REDEEMED FOOBAR") == "sell"
    assert _classify_fidelity_action("DIVIDEND RECEIVED") == "dividend"
    assert _classify_fidelity_action("DIVIDEND REINVEST") is None  # buy via REINVESTMENT branch only
    assert _classify_fidelity_action("STOCK SPLIT") == "split"
    assert _classify_fidelity_action("STOCK SPINOFF") == "split"
    assert _classify_fidelity_action("CASH TRANSFER") is None
    assert _classify_fidelity_action("FEE DEBIT") is None
