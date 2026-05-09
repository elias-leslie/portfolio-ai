"""Portfolio management CRUD operations.

This module provides the PortfolioManager class for managing accounts and positions.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

import polars as pl

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from .account_types import AccountType
from .models import Account, Position
from .transactions import TransactionLedger
from .watchlist_sync import ensure_symbols_in_watchlist

logger = get_logger(__name__)


class PortfolioManager:
    """Manages portfolio accounts and positions.

    Provides CRUD operations for accounts and positions with PostgreSQL storage.
    """

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize portfolio manager.

        Args:
            storage: PortfolioStorage instance for database access
        """
        self.storage = storage
        self.ledger = TransactionLedger(storage)

    def add_account(
        self,
        name: str,
        account_type: AccountType,
    ) -> Account:
        """Create a new portfolio account.

        Args:
            name: Account name
            account_type: Type of account (IRA, Taxable, 401k, Roth, HSA, paper)

        Returns:
            Created Account instance
        """
        account_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        starting_cash = 100000.0 if account_type == "paper" else 0.0

        account = Account(
            id=account_id,
            name=name,
            account_type=account_type,
            household_account_id=None,
            cash_balance=starting_cash,
            initial_cash=starting_cash,
            created_at=now,
            updated_at=now,
        )

        # Insert into database
        self.storage.insert_dict(
            "portfolio_accounts",
            account.model_dump(),
        )

        logger.info("account_created", account_id=account_id, name=name, account_type=account_type)
        return account

    def update_account_cash_balance(
        self,
        account_id: str,
        cash_balance: float,
        initial_cash: float | None = None,
    ) -> Account:
        """Update stored cash balances for a portfolio account."""
        df = self.storage.query(
            "SELECT * FROM portfolio_accounts WHERE id = ?",
            [account_id],
        )
        if df.is_empty():
            raise ValueError(f"Account {account_id} not found")

        account = Account(**df.to_dicts()[0])
        account.cash_balance = cash_balance
        if initial_cash is not None:
            account.initial_cash = initial_cash
        account.updated_at = datetime.now(UTC)

        df_update = pl.DataFrame([account.model_dump()])
        self.storage.upsert_by_id("portfolio_accounts", df_update, "id")

        logger.info("cash_balance_updated", account_id=account_id)
        return account

    def get_accounts(self) -> list[Account]:
        """Get all portfolio accounts.

        Returns:
            List of Account instances
        """
        df = self.storage.query("SELECT * FROM portfolio_accounts ORDER BY created_at")

        if df.is_empty():
            return []

        accounts = []
        for row in df.iter_rows(named=True):
            accounts.append(Account(**row))

        return accounts

    def add_position(
        self,
        account_id: str,
        symbol: str,
        shares: float,
        cost_basis: float,
        position_type: Literal["long", "short"] = "long",
        strategy_id: str | None = None,
    ) -> Position:
        """Add a new position to an account.

        Args:
            account_id: ID of the account
            symbol: Stock symbol
            shares: Number of shares
            cost_basis: Cost basis per share
            position_type: 'long' or 'short'
            strategy_id: Optional strategy ID to link this position to

        Returns:
            Created Position instance
        """
        position_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        position = Position(
            id=position_id,
            account_id=account_id,
            symbol=symbol.upper(),
            shares=shares,
            cost_basis=cost_basis,
            position_type=position_type,
            strategy_id=strategy_id,
            created_at=now,
            updated_at=now,
        )

        # Insert into database
        self.storage.insert_dict(
            "portfolio_positions",
            position.model_dump(),
        )
        self.sync_portfolio_to_watchlist([position.symbol])

        self._record_legacy_aggregate(
            account_id=account_id,
            symbol=position.symbol,
            shares_delta=shares,
            cost_basis=cost_basis,
            reason="add_position",
            prior_shares=0.0,
            prior_cost_basis=0.0,
        )

        logger.info("position_created", position_id=position_id, shares=shares, symbol=symbol, cost_basis=cost_basis)
        return position

    def update_position(
        self,
        position_id: str,
        account_id: str | None = None,
        symbol: str | None = None,
        shares: float | None = None,
        cost_basis: float | None = None,
        position_type: Literal["long", "short"] | None = None,
    ) -> Position:
        """Update an existing position.

        Args:
            position_id: ID of the position to update
            account_id: New account ID (optional)
            symbol: New stock symbol (optional)
            shares: New number of shares (optional)
            cost_basis: New cost basis (optional)
            position_type: New position type (optional)

        Returns:
            Updated Position instance

        Raises:
            ValueError: If position not found
        """
        # Get existing position
        df = self.storage.query(
            "SELECT * FROM portfolio_positions WHERE id = ?",
            [position_id],
        )

        if df.is_empty():
            raise ValueError(f"Position {position_id} not found")

        position_data = df.to_dicts()[0]
        position = Position(**position_data)

        prior_shares = position.shares
        prior_cost_basis = position.cost_basis
        prior_account_id = position.account_id
        prior_symbol = position.symbol

        # Update fields
        if account_id is not None:
            position.account_id = account_id
        if symbol is not None:
            position.symbol = symbol.upper()
        if shares is not None:
            position.shares = shares
        if cost_basis is not None:
            position.cost_basis = cost_basis
        if position_type is not None:
            position.position_type = position_type

        position.updated_at = datetime.now(UTC)

        # Update in database using upsert
        df_update = pl.DataFrame([position.model_dump()])
        self.storage.upsert_by_id("portfolio_positions", df_update, "id")
        self.sync_portfolio_to_watchlist([position.symbol])

        shares_changed = position.shares != prior_shares
        cost_changed = position.cost_basis != prior_cost_basis
        identity_changed = (
            position.account_id != prior_account_id
            or position.symbol != prior_symbol
        )
        if shares_changed or cost_changed or identity_changed:
            self._record_legacy_aggregate(
                account_id=position.account_id,
                symbol=position.symbol,
                shares_delta=position.shares - (
                    prior_shares if not identity_changed else 0.0
                ),
                cost_basis=position.cost_basis,
                reason="update_position",
                prior_shares=prior_shares if not identity_changed else 0.0,
                prior_cost_basis=prior_cost_basis if not identity_changed else 0.0,
                prior_account_id=prior_account_id if identity_changed else None,
                prior_symbol=prior_symbol if identity_changed else None,
            )

        logger.info("position_updated", position_id=position_id)
        return position

    def delete_position(self, position_id: str) -> None:
        """Delete a position.

        Args:
            position_id: ID of the position to delete

        Raises:
            ValueError: If position not found
        """
        df = self.storage.query(
            "SELECT id FROM portfolio_positions WHERE id = ?",
            [position_id],
        )
        if df.is_empty():
            raise ValueError(f"Position {position_id} not found")

        with self.storage.connection() as conn:
            conn.execute(
                "DELETE FROM portfolio_positions WHERE id = ?",
                [position_id],
            )
            conn.commit()

        logger.info("position_deleted", position_id=position_id)

    def get_positions(self, account_id: str | None = None) -> list[Position]:
        """Get positions, optionally filtered by account.

        Args:
            account_id: Optional account ID to filter by

        Returns:
            List of Position instances
        """
        if account_id:
            df = self.storage.query(
                "SELECT * FROM portfolio_positions WHERE account_id = ? ORDER BY symbol",
                [account_id],
            )
        else:
            df = self.storage.query("SELECT * FROM portfolio_positions ORDER BY symbol")

        if df.is_empty():
            return []

        positions = []
        for row in df.iter_rows(named=True):
            # Convert UUID to string if present (database returns UUID objects)
            row_dict = dict(row)
            if row_dict.get("strategy_id") is not None:
                row_dict["strategy_id"] = str(row_dict["strategy_id"])
            positions.append(Position(**row_dict))

        return positions

    def _record_legacy_aggregate(
        self,
        *,
        account_id: str,
        symbol: str,
        shares_delta: float,
        cost_basis: float,
        reason: str,
        prior_shares: float,
        prior_cost_basis: float,
        prior_account_id: str | None = None,
        prior_symbol: str | None = None,
    ) -> None:
        """Mirror an aggregate position write into the transaction ledger.

        Lots are intentionally not created from these synthetic rows —
        only real broker/manual transactions populate ``portfolio_tax_lots``.
        Downstream services fall back to ``portfolio_positions.cost_basis``
        when no lots exist for an (account, symbol).
        """
        if shares_delta == 0 and prior_account_id is None and prior_symbol is None:
            return
        txn_type = "buy" if shares_delta >= 0 else "sell"
        metadata: dict[str, object] = {
            "reason": reason,
            "prior_shares": prior_shares,
            "prior_cost_basis": prior_cost_basis,
            "new_cost_basis": cost_basis,
        }
        if prior_account_id is not None:
            metadata["prior_account_id"] = prior_account_id
        if prior_symbol is not None:
            metadata["prior_symbol"] = prior_symbol

        try:
            self.ledger.record_transaction(
                account_id=account_id,
                symbol=symbol,
                transaction_type=txn_type,
                trade_date=datetime.now(UTC).date(),
                shares=abs(shares_delta) if shares_delta != 0 else 0.0,
                price=cost_basis,
                source="legacy_aggregate",
                metadata=metadata,
            )
        except Exception:
            # Aggregate ledger writes are observability — do not fail
            # the user's CRUD on a ledger error.
            logger.exception(
                "legacy_aggregate_ledger_write_failed",
                account_id=account_id,
                symbol=symbol,
                reason=reason,
            )

    def sync_portfolio_to_watchlist(self, symbols: list[str]) -> None:
        """Sync portfolio symbols to watchlist.

        Automatically adds portfolio symbols to watchlist with source='portfolio'.
        This is a one-way, additive sync - it does not remove symbols from the watchlist.

        Args:
            symbols: List of symbols to sync to watchlist

        Note:
            - Uses INSERT...ON CONFLICT DO NOTHING for idempotency
            - Safe to call multiple times with the same symbols
            - Does not modify existing watchlist items
        """
        symbols_to_add = ensure_symbols_in_watchlist(self.storage, symbols, source="portfolio")
        if not symbols_to_add:
            logger.debug("All portfolio symbols already in watchlist")
