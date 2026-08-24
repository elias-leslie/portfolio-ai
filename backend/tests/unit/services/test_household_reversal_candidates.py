"""The pairing pass has to be shown both legs of a reversal.

`find_reversal_pairs` matched the July Pinellas deposit against its clawback
from the day it was written, and never once fired on live data: the candidate
rows came from the spend rows, and an outflow filed under income is dropped
from spend by category before pairing ever sees it. The deposit therefore
stayed in income for good -- $1,102.23 of a July paycheque that was taken back
the next day.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from app.services.household_transaction_service import HouseholdTransactionService

_DEPOSIT = "DIRECT DEPOSIT PINELLAS COUPAYROLL (Cash)"
_CLAWBACK = "DIRECT DEBIT PINELLAS COUNTREVERSAL (Cash)"


class _Connection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def execute(self, sql: str, params: list[Any] | None = None) -> SimpleNamespace:
        del sql, params
        return SimpleNamespace(fetchall=lambda: self._rows)


class _Storage:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    @contextmanager
    def connection(self):
        yield _Connection(self._rows)


def _moment(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=UTC)


class _StubService(HouseholdTransactionService):
    """The real pairing code over stubbed row sources."""

    def __init__(
        self,
        *,
        clawback_rows: list[tuple[Any, ...]],
        report_rows: list[dict[str, Any]] | None = None,
        income_rows: list[dict[str, Any]] | None = None,
    ) -> None:
        self.storage = _Storage(clawback_rows)
        self._reversal_pairs = None
        self._report_rows = report_rows or []
        self._stub_income_rows = income_rows or []

    def _load_report_rows(self, *, include_reversals: bool = False) -> list[dict[str, Any]]:
        del include_reversals
        return self._report_rows

    def _income_rows(self) -> list[dict[str, Any]]:
        return self._stub_income_rows


def _clawback_row(flow_type: str = "expense") -> tuple[Any, ...]:
    return (
        "txn-clawback",
        _moment(10),
        Decimal("1102.23"),
        "Pinellas Cty Sch Payables",
        _CLAWBACK,
        flow_type,
    )


def _deposit_candidate() -> dict[str, Any]:
    return {
        "id": "txn-deposit",
        "date": date(2026, 7, 9),
        "amount": 1102.23,
        "flow_type": "income",
        "merchant": "Pinellas Cty Sch Payables",
        "description": _DEPOSIT,
    }


def test_an_outflow_filed_under_income_is_read_as_a_clawback() -> None:
    rows = _StubService(clawback_rows=[_clawback_row()])._income_clawback_rows()

    assert [row["id"] for row in rows] == ["txn-clawback"]
    assert rows[0]["flow_type"] == "expense"
    assert rows[0]["date"] == date(2026, 7, 10)
    assert rows[0]["amount"] == 1102.23


def test_the_reversed_july_paycheque_finally_pairs() -> None:
    service = _StubService(
        clawback_rows=[_clawback_row()],
        income_rows=[_deposit_candidate()],
    )

    pairs = service.reversal_pairs()

    assert len(pairs) == 1
    assert pairs[0].inflow_id == "txn-deposit"
    assert pairs[0].outflow_id == "txn-clawback"
    assert pairs[0].amount == 1102.23
    assert set(service.reversal_reasons()) == {"txn-deposit", "txn-clawback"}


def test_a_row_counted_as_spend_is_not_offered_to_the_pairing_pass_twice() -> None:
    service = _StubService(
        clawback_rows=[_clawback_row()],
        report_rows=[
            {
                "id": "txn-clawback",
                "date": date(2026, 7, 10),
                "amount": 1102.23,
                "flow_type": "expense",
                "merchant": "Pinellas Cty Sch Payables",
                "description": _CLAWBACK,
                "source_kind": "transaction",
            }
        ],
    )

    candidates = service._reversal_candidate_rows()

    assert [row["id"] for row in candidates] == ["txn-clawback"]


def test_household_transfers_are_still_left_out_of_the_candidate_set() -> None:
    service = _StubService(clawback_rows=[])

    assert service._reversal_candidate_rows() == []
