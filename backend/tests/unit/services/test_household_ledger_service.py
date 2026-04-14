"""Unit tests for household ledger accounting direction and exclusions."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from app.services.household_ledger_service import HouseholdLedgerService


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


def test_ledger_uses_flow_direction_for_debits_and_credits() -> None:
    today = date.today()
    service = HouseholdLedgerService()
    fake_service = SimpleNamespace(
        storage=_SequenceStorage(
            [
                [
                    (
                        "txn-income",
                        "income",
                        "acct-checking",
                        "Checking",
                        datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                        None,
                        "Payroll",
                        "Payroll deposit",
                        Decimal("2840.59"),
                        "USD",
                        "Income",
                        "essential",
                        "hash-income",
                        {},
                        "doc-income",
                        "statement.pdf",
                        "bank",
                        "statement",
                        datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                        {},
                    ),
                    (
                        "txn-expense",
                        "expense",
                        "acct-card",
                        "Amazon Chase (CC)",
                        datetime.combine(today - timedelta(days=1), datetime.min.time(), tzinfo=UTC),
                        None,
                        "Publix",
                        "PUBLIX #1309 | Sale",
                        Decimal("45.88"),
                        "USD",
                        "Groceries",
                        "essential",
                        "hash-expense",
                        {},
                        "doc-expense",
                        "card.csv",
                        "credit_card",
                        "statement",
                        datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                        {},
                    ),
                ],
                [],
            ]
        )
    )

    ledger = service.get_ledger(fake_service, window="1m", kind="transactions")

    assert ledger.debit_total == 45.88
    assert ledger.credit_total == 2840.59
    by_id = {entry.id: entry for entry in ledger.entries}
    assert by_id["txn-income"].included_in_spend is False
    assert by_id["txn-income"].exclusion_reason == "non_expense_flow"
    assert by_id["txn-expense"].included_in_spend is True


def test_ledger_treats_return_rows_as_refunds_not_payments() -> None:
    today = date.today()
    service = HouseholdLedgerService()
    fake_service = SimpleNamespace(
        storage=_SequenceStorage(
            [
                [
                    (
                        "txn-return",
                        "payment",
                        "acct-card",
                        "Amazon Chase (CC)",
                        datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                        None,
                        "Amazon",
                        "AMAZON MKTPLACE PMTS | Return",
                        Decimal("30.82"),
                        "USD",
                        "Transfers",
                        "mixed",
                        "hash-return",
                        {},
                        "doc-return",
                        "activity.csv",
                        "credit_card",
                        "statement",
                        datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                        {},
                    ),
                ],
                [],
            ]
        )
    )

    ledger = service.get_ledger(fake_service, window="1m", kind="transactions")

    assert ledger.debit_total == 0.0
    assert ledger.credit_total == 30.82
    assert len(ledger.entries) == 1
    entry = ledger.entries[0]
    assert entry.flow_type == "refund"
    assert entry.category == "Retail"
    assert entry.included_in_spend is True
    assert entry.exclusion_reason is None
