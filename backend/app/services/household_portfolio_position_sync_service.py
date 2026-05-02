"""Sync portfolio positions from account evidence snapshots."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from app.models.household_finance import HouseholdDocument
from app.services._household_document_pipeline_utils import parse_decimal_value

_CASH_SYMBOLS = frozenset({"SPAXX", "FCASH", "FDRXX"})
_SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")


def _dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _decimal(value: object) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int | float):
        try:
            return Decimal(str(value))
        except InvalidOperation:
            return None
    return parse_decimal_value(str(value)) if value is not None else None


def _float(value: object) -> float | None:
    parsed = _decimal(value)
    return float(parsed) if parsed is not None else None


def _symbol(value: object) -> str | None:
    raw = _string(value)
    if raw is None:
        return None
    normalized = raw.replace("*", "").strip().upper()
    if normalized in _CASH_SYMBOLS:
        return None
    if not _SYMBOL_PATTERN.fullmatch(normalized):
        return None
    return normalized


def _cash_like(holding: dict[str, object]) -> bool:
    if bool(holding.get("cash_like")):
        return True
    raw_symbol = (_string(holding.get("symbol")) or "").replace("*", "").upper()
    description = (_string(holding.get("description")) or "").lower()
    return (
        raw_symbol in _CASH_SYMBOLS
        or raw_symbol in {"PENDING ACTIVITY", "PENDING"}
        or "money market" in description
    )


def _is_full_snapshot(
    *,
    document: HouseholdDocument,
    structured_data: dict[str, object],
    account: dict[str, object],
) -> bool:
    if account.get("position_snapshot") is True:
        return True
    if _string(account.get("position_source")) == "fidelity_positions_csv":
        return True
    filename = document.filename.lower()
    account_hint = (_string(structured_data.get("account_hint")) or "").lower()
    return "portfolio_positions" in filename or "fidelity positions export" in account_hint


def _position_from_holding(holding: dict[str, object]) -> dict[str, object] | None:
    if _cash_like(holding):
        return None
    symbol = _symbol(holding.get("symbol"))
    quantity = _decimal(holding.get("quantity"))
    if symbol is None or quantity is None or quantity <= 0:
        return None

    average_cost_basis = _decimal(holding.get("average_cost_basis"))
    cost_basis_total = _decimal(holding.get("cost_basis_total"))
    market_value = _decimal(holding.get("market_value"))
    if average_cost_basis is not None and average_cost_basis >= 0:
        cost_basis = average_cost_basis
    elif cost_basis_total is not None and cost_basis_total >= 0:
        cost_basis = cost_basis_total / quantity
    elif market_value is not None and market_value >= 0:
        cost_basis = market_value / quantity
    else:
        cost_basis = Decimal("0")

    return {
        "symbol": symbol,
        "shares": float(quantity),
        "cost_basis": float(cost_basis),
    }


class HouseholdPortfolioPositionSyncService:
    """Apply full holdings snapshots to linked portfolio accounts."""

    def sync_from_reviewed_accounts(
        self,
        service: Any,
        *,
        document: HouseholdDocument,
        reviewed: dict[str, object],
    ) -> dict[str, int]:
        structured_data = _dict(reviewed.get("structured_data"))
        raw_accounts = structured_data.get("financial_accounts")
        if not isinstance(raw_accounts, list):
            return self._empty_summary()

        now = datetime.now(UTC)
        summary = self._empty_summary()
        symbols_to_sync: set[str] = set()

        with service.storage.connection() as conn:
            for raw_account in raw_accounts:
                account = _dict(raw_account)
                holdings = account.get("holdings")
                if not isinstance(holdings, list):
                    continue
                summary["accounts_scanned"] += 1
                household_account_id = _string(account.get("household_account_id"))
                if household_account_id is None:
                    summary["accounts_skipped"] += 1
                    continue

                portfolio_row = conn.execute(
                    """
                    SELECT id, cash_balance
                    FROM portfolio_accounts
                    WHERE household_account_id::text = %s
                    LIMIT 1
                    """,
                    [household_account_id],
                ).fetchone()
                if portfolio_row is None:
                    summary["accounts_skipped"] += 1
                    continue

                portfolio_account_id = str(portfolio_row[0])
                summary["accounts_linked"] += 1

                cash_balance = _float(account.get("cash_balance"))
                if cash_balance is not None:
                    conn.execute(
                        """
                        UPDATE portfolio_accounts
                        SET cash_balance = %s,
                            updated_at = %s
                        WHERE id = %s
                        """,
                        [cash_balance, now, portfolio_account_id],
                    )
                    summary["cash_updated"] += 1

                positions = [
                    position
                    for holding in holdings
                    if isinstance(holding, dict)
                    for position in [_position_from_holding(holding)]
                    if position is not None
                ]
                summary["positions_seen"] += len(positions)
                if not positions:
                    continue

                existing_rows = conn.execute(
                    """
                    SELECT id, symbol, shares, cost_basis
                    FROM portfolio_positions
                    WHERE account_id = %s
                    ORDER BY updated_at DESC NULLS LAST, id
                    """,
                    [portfolio_account_id],
                ).fetchall()
                existing_by_symbol: dict[str, tuple[str, float, float]] = {}
                duplicate_ids: list[str] = []
                for row in existing_rows:
                    symbol = str(row[1]).upper()
                    if symbol in existing_by_symbol:
                        duplicate_ids.append(str(row[0]))
                        continue
                    existing_by_symbol[symbol] = (
                        str(row[0]),
                        float(row[2] or 0.0),
                        float(row[3] or 0.0),
                    )

                if duplicate_ids:
                    conn.execute(
                        "DELETE FROM portfolio_positions WHERE id = ANY(%s)",
                        [duplicate_ids],
                    )
                    summary["positions_deleted"] += len(duplicate_ids)

                desired_symbols = {str(position["symbol"]) for position in positions}
                if _is_full_snapshot(
                    document=document,
                    structured_data=structured_data,
                    account=account,
                ):
                    stale_ids = [
                        row_id
                        for symbol, (row_id, _, _) in existing_by_symbol.items()
                        if symbol not in desired_symbols
                    ]
                    if stale_ids:
                        conn.execute(
                            "DELETE FROM portfolio_positions WHERE id = ANY(%s)",
                            [stale_ids],
                        )
                        summary["positions_deleted"] += len(stale_ids)

                for position in positions:
                    symbol = str(position["symbol"])
                    shares = float(position["shares"])
                    cost_basis = float(position["cost_basis"])
                    existing = existing_by_symbol.get(symbol)
                    if existing is None:
                        conn.execute(
                            """
                            INSERT INTO portfolio_positions (
                                id, account_id, symbol, shares, cost_basis,
                                position_type, created_at, updated_at
                            ) VALUES (%s, %s, %s, %s, %s, 'long', %s, %s)
                            """,
                            [
                                str(uuid.uuid4()),
                                portfolio_account_id,
                                symbol,
                                shares,
                                cost_basis,
                                now,
                                now,
                            ],
                        )
                        summary["positions_inserted"] += 1
                    elif existing[1] != shares or existing[2] != cost_basis:
                        conn.execute(
                            """
                            UPDATE portfolio_positions
                            SET shares = %s,
                                cost_basis = %s,
                                position_type = 'long',
                                updated_at = %s
                            WHERE id = %s
                            """,
                            [shares, cost_basis, now, existing[0]],
                        )
                        summary["positions_updated"] += 1
                    else:
                        summary["positions_unchanged"] += 1
                    symbols_to_sync.add(symbol)
            conn.commit()

        if symbols_to_sync and hasattr(service, "portfolio_mgr"):
            service.portfolio_mgr.sync_portfolio_to_watchlist(sorted(symbols_to_sync))

        return summary

    @staticmethod
    def _empty_summary() -> dict[str, int]:
        return {
            "accounts_scanned": 0,
            "accounts_linked": 0,
            "accounts_skipped": 0,
            "cash_updated": 0,
            "positions_seen": 0,
            "positions_inserted": 0,
            "positions_updated": 0,
            "positions_unchanged": 0,
            "positions_deleted": 0,
        }
