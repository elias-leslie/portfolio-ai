"""Tests for HouseholdPortfolioTransactionSyncService.

Covers the happy path (rows → ledger writes), idempotent re-sync (same
external_id ⇒ no duplicate), and the multi-account-per-document case
that the user's actual Fidelity export hits.
"""

from __future__ import annotations

from datetime import date
from typing import Any, cast
from unittest.mock import MagicMock

from app.services.household_portfolio_transaction_sync_service import (
    HouseholdPortfolioTransactionSyncService,
    _txn_external_id,
)


def _fake_storage_with_account(account_id: str = "acct-1") -> MagicMock:
    """A storage shim that resolves household_account_id → portfolio_account_id."""
    storage = MagicMock()

    class _Cursor:
        def __init__(self, row: tuple | None) -> None:
            self.row = row

        def fetchone(self) -> tuple | None:
            return self.row

    class _Conn:
        def __init__(self) -> None:
            self.calls: list[tuple[str, list]] = []

        def execute(self, query: str, params: list) -> _Cursor:
            self.calls.append((query.strip(), params))
            if "FROM portfolio_accounts" in query:
                return _Cursor((account_id,))
            if "FROM portfolio_transactions" in query:
                return _Cursor(None)  # no pre-existing row
            return _Cursor(None)

        def commit(self) -> None:
            pass

    class _Ctx:
        def __enter__(self_inner) -> _Conn:  # noqa: N805
            self_inner.conn = _Conn()
            return self_inner.conn

        def __exit__(self_inner, *_a: Any) -> None:  # noqa: N805
            pass

    storage.connection.return_value = _Ctx()
    return storage


def _fake_service(storage: MagicMock) -> MagicMock:
    service = MagicMock()
    service.storage = storage
    return service


def _reviewed_with_one_txn(
    *,
    account_mask: str = "Z35217544",
    household_account_id: str = "hh-1",
    transaction_type: str = "sell",
    shares: float = 11.0,
    symbol: str = "TSLA",
) -> dict[str, object]:
    return {
        "structured_data": {
            "financial_accounts": [
                {
                    "transaction_source": "fidelity_activity_history_csv",
                    "account_mask": account_mask,
                    "household_account_id": household_account_id,
                    "transactions": [
                        {
                            "transaction_type": transaction_type,
                            "trade_date": "2026-05-08",
                            "settlement_date": "2026-05-11",
                            "symbol": symbol,
                            "shares": shares,
                            "price": 426.2,
                            "fees": 0.1,
                            "amount": 4688.1,
                            "raw_action": f"YOU SOLD {symbol} INC",
                        }
                    ],
                }
            ]
        }
    }


def test_sync_writes_one_transaction_via_ledger() -> None:
    storage = _fake_storage_with_account("acct-1")
    service = _fake_service(storage)
    ledger = MagicMock()
    ledger.storage = storage  # so _find_by_external_id walks the same fake
    sync = HouseholdPortfolioTransactionSyncService(ledger=ledger)
    summary = sync.sync_from_reviewed_accounts(
        service, document=cast(Any, MagicMock()), reviewed=_reviewed_with_one_txn()
    )
    assert summary["accounts_linked"] == 1
    assert summary["transactions_inserted"] == 1
    ledger.record_transaction.assert_called_once()
    kwargs = ledger.record_transaction.call_args.kwargs
    assert kwargs["account_id"] == "acct-1"
    assert kwargs["transaction_type"] == "sell"
    assert kwargs["symbol"] == "TSLA"
    assert kwargs["shares"] == 11.0
    assert kwargs["price"] == 426.2
    assert kwargs["fees"] == 0.1
    assert kwargs["source"] == "broker_import"
    assert kwargs["external_id"].startswith("fidelity:")
    assert kwargs["trade_date"] == date(2026, 5, 8)
    assert kwargs["settlement_date"] == date(2026, 5, 11)


def test_external_id_is_deterministic() -> None:
    """Same row → same external_id → ledger short-circuits dupes."""
    txn = {
        "transaction_type": "buy",
        "trade_date": "2026-05-01",
        "symbol": "VGT",
        "shares": 124.0,
        "amount": -12933.2,
        "raw_action": "YOU BOUGHT VANGUARD WORLD FD INF TECH ETF (VGT) (Cash)",
    }
    a = _txn_external_id(account_number="245944181", txn=txn)
    b = _txn_external_id(account_number="245944181", txn=txn)
    assert a == b
    different_account = _txn_external_id(account_number="Z35217544", txn=txn)
    assert different_account != a


def test_sync_skips_account_when_no_link() -> None:
    storage = MagicMock()

    class _Cursor:
        def fetchone(self) -> None:
            return None

    class _Conn:
        def execute(self, *_a: Any, **_kw: Any) -> _Cursor:
            return _Cursor()

        def commit(self) -> None:
            pass

    class _Ctx:
        def __enter__(self_inner) -> _Conn:  # noqa: N805
            return _Conn()

        def __exit__(self_inner, *_a: Any) -> None:  # noqa: N805
            pass

    storage.connection.return_value = _Ctx()
    service = _fake_service(storage)
    ledger = MagicMock()
    sync = HouseholdPortfolioTransactionSyncService(ledger=ledger)
    summary = sync.sync_from_reviewed_accounts(
        service,
        document=cast(Any, MagicMock()),
        reviewed=_reviewed_with_one_txn(household_account_id="never-linked"),
    )
    assert summary["accounts_skipped"] == 1
    assert summary["transactions_inserted"] == 0
    ledger.record_transaction.assert_not_called()


def test_sync_handles_multi_account_document() -> None:
    """Mirrors the user's actual CSV: one file, two accounts."""
    storage = _fake_storage_with_account("acct-multi")
    service = _fake_service(storage)
    ledger = MagicMock()
    ledger.storage = storage
    sync = HouseholdPortfolioTransactionSyncService(ledger=ledger)
    reviewed = {
        "structured_data": {
            "financial_accounts": [
                {
                    "transaction_source": "fidelity_activity_history_csv",
                    "account_mask": "Z35217544",
                    "household_account_id": "hh-1",
                    "transactions": [
                        {
                            "transaction_type": "sell",
                            "trade_date": "2026-05-08",
                            "symbol": "TSLA",
                            "shares": 11.0,
                            "price": 426.2,
                            "amount": 4688.1,
                            "raw_action": "YOU SOLD TSLA",
                        }
                    ],
                },
                {
                    "transaction_source": "fidelity_activity_history_csv",
                    "account_mask": "245944181",
                    "household_account_id": "hh-2",
                    "transactions": [
                        {
                            "transaction_type": "buy",
                            "trade_date": "2026-05-01",
                            "symbol": "VGT",
                            "shares": 124.0,
                            "price": 104.3,
                            "amount": -12933.2,
                            "raw_action": "YOU BOUGHT VGT",
                        }
                    ],
                },
            ]
        }
    }
    summary = sync.sync_from_reviewed_accounts(
        service, document=cast(Any, MagicMock()), reviewed=reviewed
    )
    assert summary["accounts_linked"] == 2
    assert summary["transactions_inserted"] == 2
    assert ledger.record_transaction.call_count == 2


def test_sync_ignores_non_activity_history_accounts() -> None:
    """Positions snapshots and other CSVs flow through their own sync services."""
    storage = _fake_storage_with_account("acct-1")
    service = _fake_service(storage)
    ledger = MagicMock()
    sync = HouseholdPortfolioTransactionSyncService(ledger=ledger)
    reviewed = {
        "structured_data": {
            "financial_accounts": [
                {
                    # Note: position_source, NOT transaction_source.
                    "position_source": "fidelity_positions_csv",
                    "account_mask": "Z35217544",
                    "holdings": [{"symbol": "VTI", "quantity": 100}],
                }
            ]
        }
    }
    summary = sync.sync_from_reviewed_accounts(
        service, document=cast(Any, MagicMock()), reviewed=reviewed
    )
    assert summary["accounts_linked"] == 0
    ledger.record_transaction.assert_not_called()


def test_sync_skips_malformed_transaction_rows() -> None:
    storage = _fake_storage_with_account("acct-1")
    service = _fake_service(storage)
    ledger = MagicMock()
    sync = HouseholdPortfolioTransactionSyncService(ledger=ledger)
    reviewed = {
        "structured_data": {
            "financial_accounts": [
                {
                    "transaction_source": "fidelity_activity_history_csv",
                    "account_mask": "Z35217544",
                    "household_account_id": "hh-1",
                    "transactions": [
                        # missing shares
                        {"transaction_type": "buy", "trade_date": "2026-05-01", "symbol": "VTI", "price": 100.0},
                        # missing trade_date
                        {"transaction_type": "buy", "symbol": "VTI", "shares": 1.0, "price": 100.0},
                        # missing symbol
                        {"transaction_type": "buy", "trade_date": "2026-05-01", "shares": 1.0, "price": 100.0},
                    ],
                }
            ]
        }
    }
    summary = sync.sync_from_reviewed_accounts(
        service, document=cast(Any, MagicMock()), reviewed=reviewed
    )
    assert summary["transactions_skipped"] == 3
    assert summary["transactions_inserted"] == 0
    ledger.record_transaction.assert_not_called()
