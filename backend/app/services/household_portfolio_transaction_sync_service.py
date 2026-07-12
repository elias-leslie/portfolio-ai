"""Sync portfolio transactions from broker activity-history exports.

Counterpart to :class:`HouseholdPortfolioPositionSyncService`: where
that service mirrors a *positions snapshot* into ``portfolio_positions``,
this service mirrors a *trade history* into ``portfolio_transactions``
through the canonical :class:`TransactionLedger`.

The ledger handles tax-lot bookkeeping for us:
- ``buy`` rows automatically open a matching ``portfolio_tax_lots`` row.
- ``sell`` rows FIFO-consume open lots, stamp realized gain on the
  transaction, and split LT vs ST holding-period gain.

Idempotency: each row gets a deterministic ``external_id`` derived from
``(account_number, run_date, action, symbol, shares, amount)`` so re-
running the sync (or re-uploading the same CSV next month) does not
create duplicate transactions. The ledger short-circuits when an
existing row matches.

Wired into :mod:`app.services.household_document_pipeline` next to the
position sync; both run on every reviewed document so a single CSV that
carries both snapshots and history fans out correctly.
"""

from __future__ import annotations

import hashlib
from datetime import date
from typing import Any, cast

from app.models.household_finance import HouseholdDocument
from app.portfolio.transactions import TransactionLedger


def _string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    text = _string(value)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _trade_date_sort_key(raw_txn: object) -> tuple[bool, date]:
    """Sort valid trades oldest-first and leave invalid rows stably at the end."""
    if not isinstance(raw_txn, dict):
        return (True, date.max)
    trade_date = _to_date(raw_txn.get("trade_date"))
    return (trade_date is None, trade_date or date.max)


def _txn_external_id(*, account_number: str, txn: dict[str, Any]) -> str:
    """Deterministic dedupe key for one Fidelity activity row.

    Fidelity does not include a stable transaction id in the activity
    export, so we synthesize one from the columns that uniquely
    identify the trade. The hash is short — 16 hex chars — to fit the
    128-char ``external_id`` column comfortably.
    """
    digest = hashlib.sha256()
    digest.update(account_number.encode("utf-8"))
    digest.update(b"|")
    digest.update(str(txn.get("trade_date", "")).encode("utf-8"))
    digest.update(b"|")
    digest.update(str(txn.get("transaction_type", "")).encode("utf-8"))
    digest.update(b"|")
    digest.update(str(txn.get("symbol", "")).encode("utf-8"))
    digest.update(b"|")
    digest.update(str(txn.get("shares", "")).encode("utf-8"))
    digest.update(b"|")
    digest.update(str(txn.get("amount", "")).encode("utf-8"))
    digest.update(b"|")
    digest.update(str(txn.get("raw_action", "")).encode("utf-8"))
    return f"fidelity:{digest.hexdigest()[:32]}"


class HouseholdPortfolioTransactionSyncService:
    """Apply broker activity-history exports to ``portfolio_transactions``."""

    def __init__(self, ledger: TransactionLedger | None = None) -> None:
        # ``ledger`` is injected for tests; production callers leave
        # it ``None`` and the service binds to the canonical singleton
        # via the storage facade at sync time.
        self._injected_ledger = ledger

    def sync_from_reviewed_accounts(
        self,
        service: Any,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
    ) -> dict[str, int]:
        """Walk reviewed.financial_accounts and write trades to the ledger."""
        del document
        structured_data = reviewed.get("structured_data")
        if not isinstance(structured_data, dict):
            return self._empty_summary()
        raw_accounts = structured_data.get("financial_accounts")
        if not isinstance(raw_accounts, list):
            return self._empty_summary()

        ledger = self._injected_ledger or TransactionLedger(service.storage)
        summary = self._empty_summary()

        for raw_account in raw_accounts:
            if not isinstance(raw_account, dict):
                continue
            transactions = raw_account.get("transactions")
            if not isinstance(transactions, list):
                continue
            if raw_account.get("transaction_source") != "fidelity_activity_history_csv":
                # Other CSV kinds (positions, statements) flow through
                # their own sync services; ignore them here.
                continue
            account_mask = _string(raw_account.get("account_mask"))
            if account_mask is None:
                summary["accounts_skipped"] += 1
                continue
            household_account_id = _string(raw_account.get("household_account_id"))

            portfolio_account_id = self._resolve_portfolio_account_id(
                service.storage,
                account_mask=account_mask,
                household_account_id=household_account_id,
            )
            if portfolio_account_id is None:
                summary["accounts_skipped"] += 1
                continue

            summary["accounts_linked"] += 1
            # Broker exports commonly arrive newest-first. The ledger updates
            # FIFO tax lots as each row is recorded, so trades must be applied
            # chronologically within an account. ``sorted`` is stable: rows
            # with the same date, and malformed rows placed at the end, retain
            # their original relative order for deterministic review counts.
            for raw_txn in sorted(transactions, key=_trade_date_sort_key):
                if not isinstance(raw_txn, dict):
                    summary["transactions_skipped"] += 1
                    continue
                txn = cast(dict[str, Any], raw_txn)
                transaction_type = _string(txn.get("transaction_type"))
                trade_date = _to_date(txn.get("trade_date"))
                symbol = _string(txn.get("symbol"))
                shares = txn.get("shares")
                price = txn.get("price")
                if (
                    transaction_type is None
                    or trade_date is None
                    or symbol is None
                    or not isinstance(shares, int | float)
                    or not isinstance(price, int | float)
                ):
                    summary["transactions_skipped"] += 1
                    continue

                external_id = _txn_external_id(
                    account_number=account_mask, txn=txn
                )
                # Idempotency: if a row already exists with this
                # external_id the ledger returns the existing UUID and
                # we record it as 'unchanged'. The lookup happens
                # inside ``record_transaction`` so the call is safe to
                # repeat.
                pre_existing_id = self._find_by_external_id(
                    ledger, account_id=portfolio_account_id, external_id=external_id
                )
                fees_value = txn.get("fees")
                fees = float(fees_value) if isinstance(fees_value, int | float) else 0.0
                ledger.record_transaction(
                    account_id=portfolio_account_id,
                    symbol=symbol,
                    transaction_type=cast(Any, transaction_type),
                    trade_date=trade_date,
                    shares=float(shares),
                    price=float(price),
                    fees=fees,
                    settlement_date=_to_date(txn.get("settlement_date")),
                    source="broker_import",
                    external_id=external_id,
                    metadata={
                        "raw_action": _string(txn.get("raw_action")),
                        "amount": txn.get("amount"),
                        "import_origin": "fidelity_activity_history_csv",
                    },
                )
                if pre_existing_id is None:
                    summary["transactions_inserted"] += 1
                else:
                    summary["transactions_unchanged"] += 1

        return summary

    @staticmethod
    def _empty_summary() -> dict[str, int]:
        return {
            "accounts_linked": 0,
            "accounts_skipped": 0,
            "transactions_inserted": 0,
            "transactions_unchanged": 0,
            "transactions_skipped": 0,
        }

    @staticmethod
    def _resolve_portfolio_account_id(
        storage: Any,
        *,
        account_mask: str,
        household_account_id: str | None,
    ) -> str | None:
        """Resolve a ``portfolio_accounts.id`` for one row.

        Strategy: prefer the explicit ``household_account_id`` link
        when the document review wrote one (matches the positions sync
        behavior). Fall back to ``portfolio_accounts.account_mask`` —
        not a column today, so this is a string-match against the
        account *name* which Fidelity exports identically to the mask
        field on related statements (e.g. ``Z00000002``).
        """
        with storage.connection() as conn:
            if household_account_id is not None:
                row = conn.execute(
                    """
                    SELECT id FROM portfolio_accounts
                    WHERE household_account_id::text = %s
                    LIMIT 1
                    """,
                    [household_account_id],
                ).fetchone()
                if row is not None:
                    return str(row[0])
            # Fallback: name match. Fidelity puts the masked account
            # number in the row's Account Number column; portfolio
            # accounts' ``name`` is the friendly label and may not
            # match. This branch returns None when nothing matches —
            # the caller increments ``accounts_skipped`` and the user
            # can re-link from the household-document review screen.
            row = conn.execute(
                """
                SELECT id FROM portfolio_accounts
                WHERE name = %s OR name ILIKE %s
                LIMIT 1
                """,
                [account_mask, f"%{account_mask}%"],
            ).fetchone()
            if row is not None:
                return str(row[0])
        return None

    @staticmethod
    def _find_by_external_id(
        ledger: TransactionLedger, *, account_id: str, external_id: str
    ) -> str | None:
        with ledger.storage.connection() as conn:
            row = conn.execute(
                """
                SELECT id FROM portfolio_transactions
                WHERE account_id = %s AND external_id = %s
                LIMIT 1
                """,
                [account_id, external_id],
            ).fetchone()
        return str(row[0]) if row else None
