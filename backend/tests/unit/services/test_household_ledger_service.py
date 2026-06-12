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


def test_ledger_returns_category_options_from_transactions_only() -> None:
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
                # Purchase-items query runs between transactions and imports.
                [],
                [
                    (
                        "import-1",
                        "statement_csv",
                        "row-1",
                        datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                        "Walmart",
                        "WALMART STORE",
                        Decimal("12.34"),
                        "USD",
                        "hash-import",
                        {},
                        "doc-import",
                        "import.csv",
                        "bank",
                        "import",
                        datetime.combine(today, datetime.min.time(), tzinfo=UTC),
                    ),
                ],
            ]
        )
    )

    ledger = service.get_ledger(fake_service, window="1m", kind="all")

    # Import rows carry a synthetic display category; only real transaction
    # categories feed the inline category editor's options.
    assert ledger.category_options == ["Groceries", "Income"]


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


def _txn_row(
    *,
    row_id: str,
    account_label: str,
    merchant: str,
    description: str,
    amount: str,
    day_offset: int,
) -> tuple[Any, ...]:
    moment = datetime.combine(
        date.today() - timedelta(days=day_offset), datetime.min.time(), tzinfo=UTC
    )
    return (
        row_id,
        "expense",
        f"acct-{account_label}",
        account_label,
        moment,
        None,
        merchant,
        description,
        Decimal(amount),
        "USD",
        "Groceries",
        "essential",
        f"hash-{row_id}",
        {},
        f"doc-{row_id}",
        "statement.pdf",
        "bank",
        "statement",
        moment,
        {},
    )


def _ledger_with_rows() -> SimpleNamespace:
    return SimpleNamespace(
        storage=_SequenceStorage(
            [
                [
                    _txn_row(
                        row_id="a",
                        account_label="Checking",
                        merchant="Publix",
                        description="PUBLIX #1",
                        amount="10.00",
                        day_offset=0,
                    ),
                    _txn_row(
                        row_id="b",
                        account_label="Card",
                        merchant="Amazon",
                        description="AMZN MKTPL",
                        amount="20.00",
                        day_offset=1,
                    ),
                    _txn_row(
                        row_id="c",
                        account_label="Checking",
                        merchant="Shell",
                        description="SHELL GAS",
                        amount="30.00",
                        day_offset=2,
                    ),
                ],
                [],
            ]
        )
    )


def test_ledger_paginates_and_reports_filtered_counts() -> None:
    service = HouseholdLedgerService()

    page = service.get_ledger(
        _ledger_with_rows(), window="all", kind="transactions", limit=2, offset=0
    )
    assert page.filtered_count == 3
    assert page.returned_count == 2
    assert page.limit == 2
    assert page.offset == 0
    # Default sort is newest-first by effective date.
    assert [entry.id for entry in page.entries] == ["a", "b"]
    assert page.account_options == ["Card", "Checking"]

    page_two = service.get_ledger(
        _ledger_with_rows(), window="all", kind="transactions", limit=2, offset=2
    )
    assert [entry.id for entry in page_two.entries] == ["c"]


def test_ledger_filters_by_account_and_search() -> None:
    service = HouseholdLedgerService()

    by_account = service.get_ledger(
        _ledger_with_rows(), window="all", kind="transactions", account="Checking"
    )
    assert by_account.filtered_count == 2
    assert {entry.id for entry in by_account.entries} == {"a", "c"}

    by_search = service.get_ledger(
        _ledger_with_rows(), window="all", kind="transactions", search="amazon"
    )
    assert by_search.filtered_count == 1
    assert by_search.entries[0].id == "b"


def test_ledger_attaches_purchase_item_counts_and_categories() -> None:
    service = HouseholdLedgerService()
    fake_service = SimpleNamespace(
        storage=_SequenceStorage(
            [
                [
                    _txn_row(
                        row_id="itemized",
                        account_label="Card",
                        merchant="Walmart",
                        description="WALMART #5831",
                        amount="99.00",
                        day_offset=0,
                    ),
                    _txn_row(
                        row_id="plain",
                        account_label="Card",
                        merchant="Shell",
                        description="SHELL GAS",
                        amount="30.00",
                        day_offset=1,
                    ),
                ],
                # Purchase-items aggregate: (transaction_id, count, categories).
                [("itemized", 17, ["Groceries", "Household"])],
            ]
        )
    )

    ledger = service.get_ledger(fake_service, window="all", kind="transactions")

    by_id = {entry.id: entry for entry in ledger.entries}
    assert by_id["itemized"].item_count == 17
    assert by_id["itemized"].item_categories == ["Groceries", "Household"]
    assert by_id["plain"].item_count == 0
    assert by_id["plain"].item_categories == []


def test_ledger_sorts_by_amount_ascending() -> None:
    service = HouseholdLedgerService()

    ascending = service.get_ledger(
        _ledger_with_rows(),
        window="all",
        kind="transactions",
        sort="amount",
        sort_dir="asc",
    )
    assert [entry.id for entry in ascending.entries] == ["a", "b", "c"]
