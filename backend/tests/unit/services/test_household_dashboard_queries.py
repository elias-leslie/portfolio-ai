"""Unit tests for household dashboard query helpers."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

from app.services._household_dashboard_profile_inference import (
    _income_metrics,
    _stale_transaction_inference_fields,
    build_inferences,
)
from app.services._household_dashboard_query_sql import (
    CATEGORIZATION_SQL,
    MONTH_SPEND_SQL,
    RECURRING_SQL,
    RETIREMENT_CONTRIBUTION_SQL,
    STATEMENT_FRESHNESS_SQL,
)
from app.services._household_dashboard_unknown_accounts import _UNKNOWN_ACCOUNT_SQL

queries = importlib.import_module("app.services._household_dashboard_queries")


class _FakeResult:
    def __init__(self, result: tuple[Any, ...] | list[tuple[Any, ...]]) -> None:
        self._result = result

    def fetchone(self) -> tuple[Any, ...]:
        if isinstance(self._result, list):
            return self._result[0] if self._result else ()
        return self._result

    def fetchall(self) -> list[tuple[Any, ...]]:
        if isinstance(self._result, list):
            return self._result
        return [self._result]


class _FakeConnection:
    def __init__(self, storage: _FakeStorage) -> None:
        self._storage = storage

    def execute(self, sql: str, _params: list[Any] | None = None) -> _FakeResult:
        self._storage.sql.append(sql)
        return _FakeResult(self._storage.rows.pop(0))


class _FakeStorage:
    def __init__(self, rows: list[tuple[Any, ...] | list[tuple[Any, ...]]]) -> None:
        self.rows = rows
        self.sql: list[str] = []

    @contextmanager
    def connection(self) -> Iterator[_FakeConnection]:
        yield _FakeConnection(self)


def test_statement_freshness_excludes_future_rows_and_surfaces_date_quality() -> None:
    today = datetime.now(UTC).date()
    storage = _FakeStorage(
        [
            (2, today + timedelta(days=30), today + timedelta(days=120)),
            (0, None, None),
            (today - timedelta(days=5), 2, today - timedelta(days=35)),
            [], [],
        ]
    )

    freshness = queries.check_statement_freshness(storage)

    assert freshness["most_recent_date"] == (today - timedelta(days=5)).isoformat()
    assert freshness["days_since_latest"] == 5
    assert freshness["coverage_months"] == 2
    assert freshness["future_transaction_count"] == 2
    assert freshness["latest_future_date"] == (today + timedelta(days=120)).isoformat()
    assert "transaction_date > CURRENT_DATE" in storage.sql[0]
    assert "transaction_date <= CURRENT_DATE" in storage.sql[2]
    assert "ROW_NUMBER() OVER (ORDER BY month_start DESC)" in STATEMENT_FRESHNESS_SQL
    assert "recency_rank <= 6" in STATEMENT_FRESHNESS_SQL


def test_transaction_date_issues_include_transaction_and_held_document_rows() -> None:
    today = datetime.now(UTC).date()
    storage = _FakeStorage(
        [
            [
                (
                    "txn-1",
                    "doc-1",
                    "walmart.pdf",
                    "receipt",
                    "receipt",
                    today + timedelta(days=30),
                    today - timedelta(days=2),
                    "Walmart",
                    "Walmart receipt",
                    164.14,
                    "Visa Credit ****4635",
                    0.9,
                    "09/03/2026 Order details - Walmart.com",
                )
            ],
            [
                (
                    "doc-2",
                    "target.pdf",
                    "receipt",
                    "receipt",
                    today - timedelta(days=1),
                    [
                        {
                            "transaction_date": (today + timedelta(days=60)).isoformat(),
                            "merchant": "Target",
                            "description": "Target receipt",
                            "amount": "42.50",
                            "account_label": "Visa",
                            "confidence": 0.8,
                        }
                    ],
                    "Target receipt text",
                )
            ],
        ]
    )

    issues = queries.fetch_transaction_date_issues(storage)

    assert len(issues) == 2
    assert issues[0].transaction_id == "txn-1"
    assert issues[0].transaction_date == (today + timedelta(days=30)).isoformat()
    assert issues[0].source_excerpt == "09/03/2026 Order details - Walmart.com"
    assert issues[1].transaction_id is None
    assert issues[1].merchant == "Target"
    assert issues[1].amount == 42.5


def test_current_fact_queries_share_current_date_guard() -> None:
    guarded_queries = [
        CATEGORIZATION_SQL,
        RECURRING_SQL,
        RETIREMENT_CONTRIBUTION_SQL,
        MONTH_SPEND_SQL,
        _UNKNOWN_ACCOUNT_SQL,
        STATEMENT_FRESHNESS_SQL,
    ]

    assert all("transaction_date <= CURRENT_DATE" in sql for sql in guarded_queries)


def test_current_month_spend_excludes_brokerage_trades() -> None:
    assert "you bought" in MONTH_SPEND_SQL.lower()
    assert "you sold" in MONTH_SPEND_SQL.lower()


def test_profile_income_metrics_use_canonical_money_income_totals() -> None:
    # The caller's Money totals already exclude removed rows and reversals.
    # A second raw SQL sum can reintroduce those rows into inferred budgets.
    assert _income_metrics({"2026-01": 7622.17, "2026-02": 6541.84}) == (2, 7082.005)


def test_overspending_does_not_become_a_monthly_discretionary_target() -> None:
    inferences = build_inferences(6000, 6, 0.85, 4000, 3500, 0, 6, 0.85)
    fields = {name for name, *_ in inferences}
    assert "monthly_discretionary_target" not in fields
    assert "monthly_savings_target" not in fields
    assert "monthly_net_income_target" in fields
    no_income_fields = {name for name, *_ in build_inferences(0, 0, 0, 0, 3500, 0, 6, 0.85)}
    assert "monthly_discretionary_target" not in no_income_fields


def test_stale_savings_and_unaffordable_target_inferences_are_retired() -> None:
    profile = SimpleNamespace(monthly_discretionary_target=None, monthly_savings_target=0)
    existing = {
        "monthly_discretionary_target": {"source": "transaction_inference", "status": "inferred"},
        "monthly_savings_target": {"source": "transaction_inference", "status": "inferred"},
        "monthly_net_income_target": {"source": "transaction_inference", "status": "confirmed"},
    }
    assert _stale_transaction_inference_fields(existing, profile, set()) == [
        "monthly_discretionary_target", "monthly_savings_target"
    ]


def test_superseded_inference_is_not_presented_as_a_budget_value(monkeypatch) -> None:
    from app.services import household_finance_service as finance_module

    class EmptyProfile:
        def __getattr__(self, _name: str) -> None:
            return None

    monkeypatch.setattr(finance_module, "fetch_inferred_value_rows", lambda _storage: {
        "monthly_discretionary_target": {
            "value": "6639.41", "confidence": 0.85, "status": "superseded",
            "rationale": "old transaction estimate",
        }
    })
    service = SimpleNamespace(storage=object())
    resolved = finance_module.HouseholdFinanceService.get_resolved_values(
        service, profile=EmptyProfile(), questions=[]
    )
    discretionary = next(
        value for value in resolved if value.field_name == "monthly_discretionary_target"
    )
    assert discretionary.value is None
    assert discretionary.status == "missing"


def test_detect_unknown_accounts_skips_institution_when_known_account_exists_for_same_source_type() -> None:
    storage = _FakeStorage(
        [
            [
                ("DIRECT DEBIT CHASE CREDIT CEPAY (Cash)", "transfer_out", 1),
            ],
            # Detection now also reads the registry's masks and the transaction
            # labels that resolved to no account; neither has anything to add here.
            [],
            [],
        ]
    )
    documents = [
        SimpleNamespace(
            account_label="Chase Amazon card",
            source_type="credit_card",
            metadata={"structured_data": {"account_hint": "Chase Amazon card"}},
        )
    ]

    detected = queries.detect_unknown_accounts(storage, documents)

    assert detected == []


def test_quiet_synced_accounts_do_not_generate_missing_transaction_months(monkeypatch) -> None:
    today = datetime.now(UTC).date()
    monkeypatch.setattr(queries, "review_coverage", lambda *_args, **_kwargs: {
        "coverage_status": "current", "coverage_through": today.isoformat()})
    storage = _FakeStorage([(0, None, None), (0, None, None), (today-timedelta(days=40), 1, today-timedelta(days=100))])
    freshness = queries.check_statement_freshness(storage)
    assert freshness["days_since_latest"] == 0
    assert freshness["gap_months"] == []
    assert freshness["sync_coverage_current"] is True
    assert freshness["most_recent_date"] == (today-timedelta(days=40)).isoformat()
