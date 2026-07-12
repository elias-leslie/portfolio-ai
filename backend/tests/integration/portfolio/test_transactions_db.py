"""Postgres-backed integration tests for the ledger schema.

Exercises:
- round-trip insert and read of ``portfolio_transactions``
- cascade delete on parent account removal
- partial-unique constraint on ``(account_id, external_id)``
- ``portfolio_accounts.is_spouse`` flag round-trip
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from typing import Any

import pytest
from psycopg.errors import CheckViolation

from app.portfolio.account_types import AccountType
from app.portfolio.manager import PortfolioManager
from app.portfolio.transactions import TransactionLedger
from app.storage import PortfolioStorage, get_storage


@pytest.fixture
def storage() -> PortfolioStorage:
    return get_storage()


@pytest.fixture
def manager(storage: PortfolioStorage) -> PortfolioManager:
    return PortfolioManager(storage)


@pytest.fixture
def ledger(storage: PortfolioStorage) -> TransactionLedger:
    return TransactionLedger(storage)


def _make_account(manager: PortfolioManager, account_type: AccountType = "Taxable"):
    return manager.add_account("Test", account_type)


def test_record_transaction_round_trip(
    manager: PortfolioManager, ledger: TransactionLedger
) -> None:
    account = _make_account(manager)

    txn_id = ledger.record_transaction(
        account_id=account.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
        fees=1.0,
        external_id="broker-42",
        metadata={"note": "first buy"},
    )

    rows = ledger.recent_buys([account.id], "AAPL", since_date=date(2026, 1, 1))
    assert len(rows) == 1
    assert rows[0].id == txn_id
    assert rows[0].external_id == "broker-42"
    assert rows[0].metadata == {"note": "first buy"}

    open_lots = ledger.open_lots(account.id, "AAPL")
    assert len(open_lots) == 1
    # Fees pro-rated: (180 + 1/10) per share.
    assert open_lots[0].cost_per_share == pytest.approx(180.1)


def test_external_id_is_idempotent_per_account(
    manager: PortfolioManager, ledger: TransactionLedger
) -> None:
    account = _make_account(manager)

    a = ledger.record_transaction(
        account_id=account.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
        external_id="dup",
    )
    b = ledger.record_transaction(
        account_id=account.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
        external_id="dup",
    )

    assert a == b
    rows = ledger.recent_buys([account.id], "AAPL", since_date=date(2026, 1, 1))
    assert len(rows) == 1


def test_external_id_is_conflict_safe_under_concurrent_imports(
    manager: PortfolioManager, ledger: TransactionLedger
) -> None:
    account = _make_account(manager)
    start = Barrier(2)

    def import_once() -> str:
        start.wait()
        return ledger.record_transaction(
            account_id=account.id,
            symbol="AAPL",
            transaction_type="buy",
            trade_date=date(2026, 1, 5),
            shares=10.0,
            price=180.0,
            external_id="concurrent-dup",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(import_once) for _index in range(2)]
        ids = [future.result() for future in futures]

    assert ids[0] == ids[1]
    rows = ledger.recent_buys([account.id], "AAPL", since_date=date(2026, 1, 1))
    assert len(rows) == 1
    assert len(ledger.open_lots(account.id, "AAPL")) == 1


def test_buy_lot_failure_rolls_back_transaction_row(
    manager: PortfolioManager,
    ledger: TransactionLedger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _make_account(manager)

    def fail_lot_creation(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("injected buy lot failure")

    monkeypatch.setattr(ledger, "_open_lot_for_buy", fail_lot_creation)

    with pytest.raises(RuntimeError, match="injected buy lot failure"):
        ledger.record_transaction(
            account_id=account.id,
            symbol="AAPL",
            transaction_type="buy",
            trade_date=date(2026, 1, 5),
            shares=10.0,
            price=180.0,
            external_id="rollback-buy",
        )

    assert ledger.recent_buys([account.id], "AAPL", since_date=date.min) == []
    assert ledger.open_lots(account.id, "AAPL") == []


def test_sell_gain_failure_rolls_back_transaction_and_lot_consumption(
    manager: PortfolioManager,
    ledger: TransactionLedger,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    account = _make_account(manager)
    ledger.record_transaction(
        account_id=account.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2025, 1, 5),
        shares=10.0,
        price=100.0,
        external_id="rollback-seed-buy",
    )

    def fail_gain_stamp(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("injected gain stamp failure")

    monkeypatch.setattr(ledger, "_stamp_realized_gain", fail_gain_stamp)

    with pytest.raises(RuntimeError, match="injected gain stamp failure"):
        ledger.record_transaction(
            account_id=account.id,
            symbol="AAPL",
            transaction_type="sell",
            trade_date=date(2026, 1, 5),
            shares=7.0,
            price=150.0,
            external_id="rollback-sell",
        )

    assert ledger.recent_sells([account.id], "AAPL", since_date=date.min) == []
    open_lots = ledger.open_lots(account.id, "AAPL")
    assert len(open_lots) == 1
    assert open_lots[0].remaining_shares == pytest.approx(10.0)


def test_concurrent_sells_lock_lots_before_consumption(
    manager: PortfolioManager, ledger: TransactionLedger
) -> None:
    account = _make_account(manager)
    manager.add_position(account.id, "AAPL", shares=10.0, cost_basis=100.0)
    ledger.record_transaction(
        account_id=account.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2025, 1, 5),
        shares=10.0,
        price=100.0,
        external_id="concurrent-seed-buy",
    )
    start = Barrier(2)

    def sell_once(index: int) -> str:
        start.wait()
        return ledger.record_transaction(
            account_id=account.id,
            symbol="AAPL",
            transaction_type="sell",
            trade_date=date(2026, 1, 5),
            shares=7.0,
            price=150.0,
            external_id=f"concurrent-sell-{index}",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        sell_ids = list(executor.map(sell_once, range(2)))

    assert len(set(sell_ids)) == 2
    assert ledger.open_lots(account.id, "AAPL") == []
    sells = ledger.recent_sells([account.id], "AAPL", since_date=date.min)
    assert len(sells) == 2
    assert sorted(float(row.realized_gain or 0.0) for row in sells) == [350.0, 350.0]


def test_tax_lot_remaining_shares_constraint_rejects_negative_values(
    storage: PortfolioStorage,
    manager: PortfolioManager,
    ledger: TransactionLedger,
) -> None:
    account = _make_account(manager)
    ledger.record_transaction(
        account_id=account.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
    )

    with storage.connection() as conn:
        with pytest.raises(CheckViolation):
            conn.execute(
                """
                UPDATE portfolio_tax_lots
                SET remaining_shares = -1
                WHERE account_id = %s AND symbol = %s
                """,
                [account.id, "AAPL"],
            )
        conn.rollback()

    open_lots = ledger.open_lots(account.id, "AAPL")
    assert len(open_lots) == 1
    assert open_lots[0].remaining_shares == pytest.approx(10.0)


def test_external_id_independent_across_accounts(
    manager: PortfolioManager, ledger: TransactionLedger
) -> None:
    a1 = _make_account(manager)
    a2 = _make_account(manager)

    ledger.record_transaction(
        account_id=a1.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
        external_id="shared-id",
    )
    # Same external_id under a different account is allowed by the
    # partial-unique constraint.
    ledger.record_transaction(
        account_id=a2.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
        external_id="shared-id",
    )
    # Both accounts should have one row each.
    assert len(ledger.recent_buys([a1.id], "AAPL", since_date=date(2026, 1, 1))) == 1
    assert len(ledger.recent_buys([a2.id], "AAPL", since_date=date(2026, 1, 1))) == 1


def test_account_delete_cascades_transactions_and_lots(
    storage: PortfolioStorage,
    manager: PortfolioManager,
    ledger: TransactionLedger,
) -> None:
    account = _make_account(manager)
    ledger.record_transaction(
        account_id=account.id,
        symbol="AAPL",
        transaction_type="buy",
        trade_date=date(2026, 1, 5),
        shares=10.0,
        price=180.0,
    )

    # Direct delete of the parent account.
    with storage.connection() as conn:
        conn.execute("DELETE FROM portfolio_accounts WHERE id = %s", [account.id])
        conn.commit()

    txn_count = storage.query(
        "SELECT COUNT(*) AS c FROM portfolio_transactions WHERE account_id = %s",
        [account.id],
    ).to_dicts()[0]["c"]
    lot_count = storage.query(
        "SELECT COUNT(*) AS c FROM portfolio_tax_lots WHERE account_id = %s",
        [account.id],
    ).to_dicts()[0]["c"]
    assert txn_count == 0
    assert lot_count == 0


def test_is_spouse_flag_round_trips(
    storage: PortfolioStorage, manager: PortfolioManager
) -> None:
    account = _make_account(manager)
    with storage.connection() as conn:
        conn.execute(
            "UPDATE portfolio_accounts SET is_spouse = TRUE WHERE id = %s",
            [account.id],
        )
        conn.commit()

    accounts = manager.get_accounts()
    matched = [a for a in accounts if a.id == account.id]
    assert matched and matched[0].is_spouse is True


def test_legacy_aggregate_writes_synthetic_txn_on_add_position(
    manager: PortfolioManager, ledger: TransactionLedger
) -> None:
    account = _make_account(manager)
    manager.add_position(account.id, "AAPL", shares=5.0, cost_basis=100.0)

    rows = ledger.recent_buys([account.id], "AAPL", since_date=date.min)
    assert len(rows) == 1
    assert rows[0].source == "legacy_aggregate"
    # Lots remain empty for legacy-aggregate writes.
    assert ledger.open_lots(account.id, "AAPL") == []


def test_legacy_aggregate_writes_synthetic_txn_on_update_position(
    manager: PortfolioManager, ledger: TransactionLedger
) -> None:
    account = _make_account(manager)
    position = manager.add_position(account.id, "AAPL", shares=5.0, cost_basis=100.0)
    manager.update_position(position.id, shares=10.0)

    rows = ledger.recent_buys([account.id], "AAPL", since_date=date.min)
    # Two entries: the original add, plus a delta-buy of +5 shares.
    assert len(rows) == 2
    assert all(r.source == "legacy_aggregate" for r in rows)
