"""The Ledger must count exactly the rows the analytics totals count.

Spend is decided over transaction rows alone. An imported receipt line is
evidence that a purchase happened, not a second purchase and not grounds to
drop the charge it describes -- when the Ledger collapsed the two together it
reported $71.03 of real July spending as excluded while every other surface
counted it, which is P0-1 one surface down.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from app.services.household_ledger_service import HouseholdLedgerService

_DAY = date.today() - timedelta(days=3)
_MOMENT = datetime.combine(_DAY, datetime.min.time(), tzinfo=UTC)


class _SequenceConnection:
    def __init__(self, responses: list[list[tuple[Any, ...]]]) -> None:
        self._responses = responses

    def execute(self, sql: str, params: list[Any] | None = None) -> SimpleNamespace:
        del sql, params
        rows = self._responses.pop(0)
        return SimpleNamespace(fetchall=lambda: rows)


class _SequenceStorage:
    def __init__(self, responses: list[list[tuple[Any, ...]]]) -> None:
        self.conn = _SequenceConnection(responses)

    @contextmanager
    def connection(self):
        yield self.conn


def _transaction_row() -> tuple[Any, ...]:
    return (
        "txn-amazon",
        "expense",
        "acct-card",
        "Card",
        _MOMENT,
        None,
        "Amazon",
        "AMZN Mktp US",
        Decimal("71.03"),
        "USD",
        "Retail",
        "discretionary",
        "hash-txn-amazon",
        {},
        "doc-statement",
        "statement.pdf",
        "bank",
        "statement",
        _MOMENT,
        {},
    )


def _import_row() -> tuple[Any, ...]:
    return (
        "import-amazon",
        "import",
        None,
        _MOMENT,
        "Amazon",
        "AMZN Mktp US",
        Decimal("71.03"),
        None,
        "hash-import-amazon",
        {},
        "doc-order-history",
        "orders.csv",
        "import",
        "order_history",
        _MOMENT,
    )


def _ledger_entries(import_rows: list[tuple[Any, ...]]):
    service = HouseholdLedgerService()
    ledger = service.get_ledger(
        SimpleNamespace(storage=_SequenceStorage([[_transaction_row()], [], import_rows])),
        window="all",
        kind="all",
        limit=50,
        offset=0,
    )
    return {entry.id: entry for entry in ledger.entries}


def test_an_imported_receipt_line_does_not_uncount_the_charge_it_describes() -> None:
    entries = _ledger_entries([_import_row()])

    charge = entries["txn-amazon"]
    assert charge.included_in_spend is True
    assert charge.exclusion_reason is None


def test_the_charge_still_says_a_receipt_line_describes_the_same_purchase() -> None:
    entries = _ledger_entries([_import_row()])

    assert entries["txn-amazon"].duplicate_note is not None


def test_the_imported_line_itself_never_counts_toward_spend() -> None:
    entries = _ledger_entries([_import_row()])

    assert entries["import-amazon"].included_in_spend is False


def test_spend_inclusion_is_the_same_with_and_without_the_import() -> None:
    with_import = _ledger_entries([_import_row()])
    without_import = _ledger_entries([])

    assert with_import["txn-amazon"].included_in_spend is (
        without_import["txn-amazon"].included_in_spend
    )
    assert without_import["txn-amazon"].duplicate_note is None
