"""Manual holdings entry for household accounts.

Accounts that arrive through documents or balance-only feeds (403(b), FRS,
457(b), 529s) have a value but no positions, so retirement projections fall
back to portfolio-level allocation assumptions. This service lets the user
enter the account's funds by symbol — either as share counts or as percent of
the account value — stored as regular ``portfolio_positions`` on a
``portfolio_accounts`` row linked via ``household_account_id``, which is the
same path SnapTrade/document syncs use. The household balance stays the
authoritative account value; positions inform allocation and coverage.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from importlib import import_module
from typing import Any

from pydantic import BaseModel, Field, model_validator

_PORTFOLIO_ACCOUNT_TYPE_BY_HOUSEHOLD_TYPE = {
    "roth_ira": "Roth",
    "roth_403b": "Roth",
    "roth_401k": "Roth",
    "ira": "IRA",
    "401k": "IRA",
    "403b": "IRA",
    "457b": "IRA",
    "retirement": "IRA",
}


class ManualHoldingEntry(BaseModel):
    """One symbol entered by the user, sized by shares or percent of value."""

    symbol: str = Field(..., min_length=1, max_length=15)
    shares: float | None = Field(None, gt=0.0)
    percent: float | None = Field(None, gt=0.0, le=100.0)

    @model_validator(mode="after")
    def _shares_xor_percent(self) -> ManualHoldingEntry:
        if (self.shares is None) == (self.percent is None):
            raise ValueError("Provide exactly one of shares or percent per holding.")
        return self


class ManualHoldingsReplaceRequest(BaseModel):
    entries: list[ManualHoldingEntry] = Field(..., max_length=50)
    # Required when any entry uses percent; the dialog passes the account's
    # current value so percent rows can be converted to share counts.
    account_value: float | None = Field(None, gt=0.0)


class ManualHoldingsService:
    """Read and replace manual holdings for one household account."""

    def __init__(self, storage: Any | None = None) -> None:
        self.storage = storage or import_module("app.storage").get_storage()

    # -- reads ---------------------------------------------------------------

    def get_holdings(self, household_account_id: str) -> dict[str, Any]:
        label, account_type = self._household_account(household_account_id)
        with self.storage.connection() as conn:
            row = conn.execute(
                "SELECT id FROM portfolio_accounts"
                " WHERE household_account_id::text = %s LIMIT 1",
                [household_account_id],
            ).fetchone()
            positions: list[dict[str, Any]] = []
            if row is not None:
                positions = self._positions(conn, str(row[0]))
        self._price_positions(positions)
        return {
            "household_account_id": household_account_id,
            "label": label,
            "account_type": account_type,
            "positions": positions,
            "priced_value": round(
                sum(p["value"] for p in positions if p["value"] is not None), 2
            ),
        }

    # -- writes --------------------------------------------------------------

    def replace_holdings(
        self,
        household_account_id: str,
        payload: ManualHoldingsReplaceRequest,
    ) -> dict[str, Any]:
        label, account_type = self._household_account(household_account_id)
        entries = payload.entries
        if any(entry.percent is not None for entry in entries) and (
            payload.account_value is None
        ):
            raise ValueError(
                "account_value is required when sizing holdings by percent."
            )
        total_percent = sum(entry.percent or 0.0 for entry in entries)
        if total_percent > 100.0001:
            raise ValueError(
                f"Percent entries add up to {total_percent:.1f}%; they cannot exceed 100%."
            )

        symbols = sorted({entry.symbol.strip().upper() for entry in entries})
        prices = self._fetch_prices(symbols)
        unpriced = [
            symbol
            for symbol in symbols
            if symbol not in prices
            or getattr(prices[symbol], "error", None)
            or float(getattr(prices[symbol], "price", 0.0) or 0.0) <= 0
        ]
        if unpriced:
            raise ValueError(
                "No market price found for: "
                + ", ".join(unpriced)
                + ". For institutional funds without a ticker, enter the closest"
                " public proxy (e.g. VTI for a US total-market index fund)."
            )

        now = datetime.now(UTC)
        with self.storage.connection() as conn:
            account_id = self._find_or_create_portfolio_account(
                conn,
                household_account_id,
                label=label,
                household_account_type=account_type,
                now=now,
            )
            conn.execute(
                "DELETE FROM portfolio_positions WHERE account_id = %s",
                [account_id],
            )
            for entry in entries:
                symbol = entry.symbol.strip().upper()
                price = float(prices[symbol].price)
                shares = (
                    entry.shares
                    if entry.shares is not None
                    else (entry.percent or 0.0) / 100.0 * float(payload.account_value or 0.0) / price
                )
                conn.execute(
                    """
                    INSERT INTO portfolio_positions (
                        id, account_id, symbol, shares, cost_basis,
                        position_type, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, 'long', %s, %s)
                    """,
                    [str(uuid.uuid4()), account_id, symbol, shares, price, now, now],
                )
            conn.commit()
        return self.get_holdings(household_account_id)

    # -- internals -----------------------------------------------------------

    def _household_account(self, household_account_id: str) -> tuple[str, str]:
        with self.storage.connection() as conn:
            row = conn.execute(
                "SELECT canonical_label, account_type FROM household_accounts"
                " WHERE id::text = %s",
                [household_account_id],
            ).fetchone()
        if row is None:
            raise LookupError(f"Household account not found: {household_account_id}")
        return str(row[0] or "Account"), str(row[1] or "other")

    def _find_or_create_portfolio_account(
        self,
        conn: Any,
        household_account_id: str,
        *,
        label: str,
        household_account_type: str,
        now: datetime,
    ) -> str:
        row = conn.execute(
            "SELECT id FROM portfolio_accounts"
            " WHERE household_account_id::text = %s LIMIT 1",
            [household_account_id],
        ).fetchone()
        if row is not None:
            account_id = str(row[0])
            if account_id.startswith("snaptrade:"):
                raise ValueError(
                    "This account's holdings are synced live from SnapTrade and"
                    " cannot be edited manually."
                )
            return account_id
        account_id = str(uuid.uuid4())
        account_type = _PORTFOLIO_ACCOUNT_TYPE_BY_HOUSEHOLD_TYPE.get(
            household_account_type.lower(), "Taxable"
        )
        conn.execute(
            """
            INSERT INTO portfolio_accounts (
                id, name, account_type, cash_balance, initial_cash,
                household_account_id, created_at, updated_at
            ) VALUES (%s, %s, %s, 0, 0, %s, %s, %s)
            """,
            [account_id, label, account_type, household_account_id, now, now],
        )
        return account_id

    def _positions(self, conn: Any, account_id: str) -> list[dict[str, Any]]:
        rows = conn.execute(
            """
            SELECT symbol, shares FROM portfolio_positions
            WHERE account_id = %s AND position_type = 'long' AND shares > 0
            ORDER BY symbol
            """,
            [account_id],
        ).fetchall()
        return [
            {"symbol": str(row[0]).upper(), "shares": float(row[1] or 0.0)}
            for row in rows
        ]

    def _price_positions(self, positions: list[dict[str, Any]]) -> None:
        symbols = sorted({p["symbol"] for p in positions})
        prices = self._fetch_prices(symbols) if symbols else {}
        for position in positions:
            info = prices.get(position["symbol"])
            price = float(getattr(info, "price", 0.0) or 0.0) if info is not None else 0.0
            if price > 0 and not getattr(info, "error", None):
                position["price"] = price
                position["value"] = round(price * position["shares"], 2)
            else:
                position["price"] = None
                position["value"] = None

    def _fetch_prices(self, symbols: list[str]) -> dict[str, Any]:
        if not symbols:
            return {}
        # Manually entered funds (e.g. 529 mutual funds) may not be in any
        # ingestion universe; register them so price_cache FK inserts succeed.
        helpers = import_module("app.utils.db_helpers")
        with self.storage.connection() as conn:
            helpers.ensure_symbols_exist(conn, symbols)
            conn.commit()
        price_mod = import_module("app.portfolio.price_fetcher")
        return price_mod.PriceDataFetcher(self.storage).fetch_price_data(symbols)
