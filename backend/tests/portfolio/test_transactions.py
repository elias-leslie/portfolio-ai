"""Unit tests for the TransactionLedger.

The ledger talks to PostgreSQL through ``PortfolioStorage.connection()``.
These tests stub the connection wrapper so the math (idempotency,
window math, FIFO consumption, holding-period bucketing, fallback to
position aggregate) can be exercised without a live database.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from copy import deepcopy
from datetime import UTC, date, datetime
from typing import Any

import pytest

from app.portfolio.transactions import TransactionLedger, TransactionRow


class _Cursor:
    def __init__(self, rows: list[tuple[Any, ...]]):
        self._rows = list(rows)
        self.fetched_one = False

    def fetchall(self) -> list[tuple[Any, ...]]:
        out = list(self._rows)
        self._rows = []
        return out

    def fetchone(self) -> tuple[Any, ...] | None:
        if not self._rows:
            return None
        return self._rows.pop(0)


class _FakeConn:
    def __init__(self, store: _FakeStore) -> None:
        self.store = store
        self._last_cursor: _Cursor | None = None
        self.committed_count = 0
        self._snapshot = (deepcopy(store.transactions), deepcopy(store.tax_lots))

    def execute(
        self,
        query: str,
        params: Iterable[Any] | None = None,
    ) -> _FakeConn:
        params = list(params) if params is not None else []
        normalized = " ".join(query.split())
        self.store.queries.append(normalized)
        rows = self.store.handle(normalized, params)
        self._last_cursor = _Cursor(rows)
        return self

    def fetchall(self) -> list[tuple[Any, ...]]:
        assert self._last_cursor is not None
        return self._last_cursor.fetchall()

    def fetchone(self) -> tuple[Any, ...] | None:
        assert self._last_cursor is not None
        return self._last_cursor.fetchone()

    def commit(self) -> None:
        self.committed_count += 1
        self.store.commit_count += 1
        self._snapshot = (deepcopy(self.store.transactions), deepcopy(self.store.tax_lots))

    def rollback(self) -> None:
        self.store.rollback_count += 1
        transactions, tax_lots = self._snapshot
        self.store.transactions[:] = deepcopy(transactions)
        self.store.tax_lots[:] = deepcopy(tax_lots)


class _FakeStore:
    """Tiny PG-shaped store for transactions+tax_lots+positions."""

    def __init__(self) -> None:
        self.transactions: list[dict[str, Any]] = []
        self.tax_lots: list[dict[str, Any]] = []
        self.positions: list[dict[str, Any]] = []
        self.queries: list[str] = []
        self.connection_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def seed_position(self, account_id: str, symbol: str, cost_basis: float) -> None:
        self.positions.append(
            {"account_id": account_id, "symbol": symbol.upper(), "cost_basis": cost_basis}
        )

    def handle(self, query: str, params: list[Any]) -> list[tuple[Any, ...]]:  # noqa: PLR0911
        q = query.upper()

        if q.startswith("INSERT INTO PORTFOLIO_TRANSACTIONS"):
            keys = [
                "id",
                "account_id",
                "symbol",
                "transaction_type",
                "trade_date",
                "settlement_date",
                "shares",
                "price",
                "fees",
                "source",
                "external_id",
                "metadata",
            ]
            row = dict(zip(keys, params, strict=True))
            external_id = row.get("external_id")
            if external_id is not None and any(
                existing["account_id"] == row["account_id"]
                and existing.get("external_id") == external_id
                for existing in self.transactions
            ):
                return []
            row.setdefault("realized_gain", None)
            row["created_at"] = datetime.now(UTC)
            self.transactions.append(row)
            return [(row["id"],)]

        if q.startswith("UPDATE PORTFOLIO_TRANSACTIONS SET REALIZED_GAIN"):
            realized_gain, txn_id = params
            for row in self.transactions:
                if row["id"] == txn_id:
                    row["realized_gain"] = realized_gain
            return []

        if q.startswith("INSERT INTO PORTFOLIO_TAX_LOTS"):
            keys = [
                "id",
                "account_id",
                "symbol",
                "acquired_date",
                "original_shares",
                "remaining_shares",
                "cost_per_share",
                "cost_basis_total",
                "acquisition_txn_id",
            ]
            row = dict(zip(keys, params, strict=True))
            row["disposed_at"] = None
            self.tax_lots.append(row)
            return []

        if q.startswith("UPDATE PORTFOLIO_TAX_LOTS SET REMAINING_SHARES"):
            new_remaining, disposed_at, lot_id = params
            for row in self.tax_lots:
                if row["id"] == lot_id:
                    row["remaining_shares"] = new_remaining
                    if disposed_at is not None:
                        row["disposed_at"] = disposed_at
            return []

        if q.startswith("SELECT ID FROM PORTFOLIO_TRANSACTIONS WHERE ACCOUNT_ID"):
            account_id, external_id = params
            for row in self.transactions:
                if (
                    row["account_id"] == account_id
                    and row.get("external_id") == external_id
                ):
                    return [(row["id"],)]
            return []

        if q.startswith("SELECT ID, ACCOUNT_ID, SYMBOL, ACQUIRED_DATE"):
            account_id, symbol = params
            matches = [
                row
                for row in self.tax_lots
                if row["account_id"] == account_id
                and row["symbol"] == symbol
                and float(row["remaining_shares"]) > 0
            ]
            matches.sort(key=lambda r: (r["acquired_date"], r["id"]))
            return [
                (
                    row["id"],
                    row["account_id"],
                    row["symbol"],
                    row["acquired_date"],
                    row["original_shares"],
                    row["remaining_shares"],
                    row["cost_per_share"],
                    row["cost_basis_total"],
                    row["acquisition_txn_id"],
                    row["disposed_at"],
                )
                for row in matches
            ]

        if q.startswith("SELECT COST_BASIS FROM PORTFOLIO_POSITIONS"):
            account_id, symbol = params
            for row in self.positions:
                if row["account_id"] == account_id and row["symbol"] == symbol:
                    return [(row["cost_basis"],)]
            return []

        if q.startswith(
            "SELECT ID, ACCOUNT_ID, SYMBOL, TRANSACTION_TYPE, TRADE_DATE,"
        ):
            account_ids, symbol, txn_type, since, until = params
            matches = [
                row
                for row in self.transactions
                if row["account_id"] in account_ids
                and row["symbol"] == symbol
                and row["transaction_type"] == txn_type
                and since <= row["trade_date"] <= until
            ]
            matches.sort(key=lambda r: (r["trade_date"], r["created_at"]))
            return [
                (
                    row["id"],
                    row["account_id"],
                    row["symbol"],
                    row["transaction_type"],
                    row["trade_date"],
                    row.get("settlement_date"),
                    row["shares"],
                    row["price"],
                    row["fees"],
                    row.get("realized_gain"),
                    row["source"],
                    row.get("external_id"),
                    row.get("metadata") or "{}",
                    row["created_at"],
                )
                for row in matches
            ]

        if q.startswith("SELECT ID, TRADE_DATE, REALIZED_GAIN"):
            account_id, start, end = params
            matches = [
                row
                for row in self.transactions
                if row["account_id"] == account_id
                and row["transaction_type"] == "sell"
                and start <= row["trade_date"] <= end
            ]
            return [
                (row["id"], row["trade_date"], row.get("realized_gain"))
                for row in matches
            ]

        raise AssertionError(f"unhandled query: {query[:120]} ; params={params!r}")


class _FakeStorage:
    def __init__(self) -> None:
        self.store = _FakeStore()

    def connection(self) -> Any:
        store = self.store
        store.connection_count += 1

        class _Ctx:
            def __enter__(self_inner) -> _FakeConn:  # noqa: N805
                self_inner.conn = _FakeConn(store)
                return self_inner.conn

            def __exit__(self_inner, *_a: Any) -> None:  # noqa: N805
                pass

        return _Ctx()


def _make_ledger() -> tuple[TransactionLedger, _FakeStore]:
    storage = _FakeStorage()
    return TransactionLedger(storage), storage.store


def test_record_transaction_inserts_row_and_returns_uuid() -> None:
    ledger, store = _make_ledger()

    txn_id = ledger.record_transaction(
        account_id="acct-1",
        symbol="aapl",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
    )

    assert uuid.UUID(txn_id)
    assert len(store.transactions) == 1
    row = store.transactions[0]
    assert row["account_id"] == "acct-1"
    assert row["symbol"] == "AAPL"
    assert row["transaction_type"] == "buy"
    assert row["source"] == "manual"
    # Lot opened automatically for non-legacy buys
    assert len(store.tax_lots) == 1
    assert store.connection_count == 1
    assert store.commit_count == 1


def test_record_transaction_idempotent_on_external_id() -> None:
    ledger, store = _make_ledger()

    first = ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
        external_id="broker-txn-42",
    )
    second = ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
        external_id="broker-txn-42",
    )

    assert first == second
    assert len(store.transactions) == 1
    assert len(store.tax_lots) == 1
    assert store.connection_count == 2
    assert store.commit_count == 1
    assert store.rollback_count == 1


def test_record_transaction_rolls_back_buy_when_lot_creation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ledger, store = _make_ledger()

    def fail_lot_creation(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("injected lot failure")

    monkeypatch.setattr(ledger, "_open_lot_for_buy", fail_lot_creation)

    with pytest.raises(RuntimeError, match="injected lot failure"):
        ledger.record_transaction(
            account_id="acct-1",
            symbol="AAPL",
            transaction_type="buy",
            trade_date=date(2026, 1, 5),
            shares=10.0,
            price=180.0,
            external_id="rollback-buy",
        )

    assert store.transactions == []
    assert store.tax_lots == []
    assert store.commit_count == 0
    assert store.rollback_count == 1


def test_legacy_aggregate_skips_lot_creation() -> None:
    ledger, store = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
        source="legacy_aggregate",
    )
    assert len(store.transactions) == 1
    assert store.transactions[0]["source"] == "legacy_aggregate"
    assert store.tax_lots == []


def test_recent_buys_inclusive_window_math() -> None:
    ledger, _ = _make_ledger()

    for d in (
        date(2026, 1, 1),
        date(2026, 1, 15),
        date(2026, 1, 30),
        date(2026, 2, 1),
    ):
        ledger.record_transaction(
            account_id="acct-1",
            symbol="AAPL",
            transaction_type="buy",
            trade_date=d,
            shares=1.0,
            price=100.0,
        )

    rows = ledger.recent_buys(
        ["acct-1"],
        "AAPL",
        since_date=date(2026, 1, 15),
        until_date=date(2026, 1, 30),
    )

    assert [r.trade_date for r in rows] == [date(2026, 1, 15), date(2026, 1, 30)]
    assert all(isinstance(r, TransactionRow) for r in rows)


def test_recent_buys_scans_multiple_accounts() -> None:
    ledger, _ = _make_ledger()
    for acct in ("acct-1", "acct-spouse"):
        ledger.record_transaction(
            account_id=acct,
            symbol="AAPL",
            transaction_type="buy",
            trade_date=date(2026, 4, 10),
            shares=1.0,
            price=200.0,
        )

    rows = ledger.recent_buys(
        ["acct-1", "acct-spouse"],
        "AAPL",
        since_date=date(2026, 4, 1),
    )
    accounts = {r.account_id for r in rows}
    assert accounts == {"acct-1", "acct-spouse"}


def test_recent_sells_filters_by_type() -> None:
    ledger, _ = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
    )
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2026, 4, 5),
        shares=5.0,
        price=200.0,
    )

    sells = ledger.recent_sells(["acct-1"], "AAPL", since_date=date(2026, 1, 1))
    buys = ledger.recent_buys(["acct-1"], "AAPL", since_date=date(2026, 1, 1))

    assert len(sells) == 1 and sells[0].transaction_type == "sell"
    assert len(buys) == 1 and buys[0].transaction_type == "buy"


def test_realized_gains_ytd_aggregates_sells() -> None:
    ledger, _ = _make_ledger()
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2025, 1, 5),
        shares=10.0,
        price=100.0,
    )
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2026, 3, 1),
        shares=4.0,
        price=150.0,
    )
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2026, 6, 1),
        shares=2.0,
        price=120.0,
    )

    ytd = ledger.realized_gains_ytd("acct-1", 2026)
    # Both sells should contribute realized gains (200 + 40 = 240).
    assert ytd["total"] == 240.0
    # Sells outside the year are excluded.
    ledger.record_transaction(
        account_id="acct-1",
        symbol="AAPL",
        transaction_type="sell",
        trade_date=date(2025, 12, 1),
        shares=1.0,
        price=200.0,
    )
    assert ledger.realized_gains_ytd("acct-1", 2025)["total"] == 100.0


def test_open_lots_returns_empty_when_no_rows() -> None:
    ledger, _ = _make_ledger()
    assert ledger.open_lots("acct-missing", "AAPL") == []
