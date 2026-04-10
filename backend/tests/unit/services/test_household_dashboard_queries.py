"""Unit tests for household dashboard query helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Any

from app.services import _household_dashboard_queries as queries


class _FakeResult:
    def __init__(self, row: tuple[Any, ...]) -> None:
        self._row = row

    def fetchone(self) -> tuple[Any, ...]:
        return self._row


class _FakeConnection:
    def __init__(self, storage: _FakeStorage) -> None:
        self._storage = storage

    def execute(self, sql: str, _params: list[Any] | None = None) -> _FakeResult:
        self._storage.sql.append(sql)
        return _FakeResult(self._storage.rows.pop(0))


class _FakeStorage:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.sql: list[str] = []

    @contextmanager
    def connection(self) -> Iterator[_FakeConnection]:
        yield _FakeConnection(self)


def test_statement_freshness_excludes_future_rows_and_surfaces_date_quality() -> None:
    today = date.today()
    storage = _FakeStorage(
        [
            (2, today + timedelta(days=30), today + timedelta(days=120)),
            (today - timedelta(days=5), 2, today - timedelta(days=35)),
        ]
    )

    freshness = queries.check_statement_freshness(storage)

    assert freshness["most_recent_date"] == (today - timedelta(days=5)).isoformat()
    assert freshness["days_since_latest"] == 5
    assert freshness["coverage_months"] == 2
    assert freshness["future_transaction_count"] == 2
    assert freshness["latest_future_date"] == (today + timedelta(days=120)).isoformat()
    assert "transaction_date > CURRENT_DATE" in storage.sql[0]
    assert "transaction_date <= CURRENT_DATE" in storage.sql[1]


def test_current_fact_queries_share_current_date_guard() -> None:
    guarded_queries = [
        queries._CATEGORIZATION_SQL,
        queries._RECURRING_SQL,
        queries._RETIREMENT_CONTRIBUTION_SQL,
        queries._MONTH_SPEND_SQL,
        queries._UNKNOWN_ACCOUNT_SQL,
        queries._STATEMENT_FRESHNESS_SQL,
        queries._INCOME_MONTHLY_AVG_SQL,
    ]

    assert all("transaction_date <= CURRENT_DATE" in sql for sql in guarded_queries)
