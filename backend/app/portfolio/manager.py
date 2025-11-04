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
from .models import Account, Position

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

    def add_account(
        self,
        name: str,
        account_type: Literal["IRA", "Taxable", "401k", "Roth", "HSA"],
    ) -> Account:
        """Create a new portfolio account.

        Args:
            name: Account name
            account_type: Type of account (IRA, Taxable, 401k, Roth, HSA)

        Returns:
            Created Account instance
        """
        account_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        account = Account(
            id=account_id,
            name=name,
            account_type=account_type,
            created_at=now,
            updated_at=now,
        )

        # Insert into database
        self.storage.insert_dict(
            "portfolio_accounts",
            account.model_dump(),
        )

        logger.info(f"Created account {account_id}: {name} ({account_type})")
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
    ) -> Position:
        """Add a new position to an account.

        Args:
            account_id: ID of the account
            symbol: Stock symbol
            shares: Number of shares
            cost_basis: Cost basis per share
            position_type: 'long' or 'short'

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
            created_at=now,
            updated_at=now,
        )

        # Insert into database
        self.storage.insert_dict(
            "portfolio_positions",
            position.model_dump(),
        )

        logger.info(f"Created position {position_id}: {shares} shares of {symbol} at ${cost_basis}")
        return position

    def update_position(
        self,
        position_id: str,
        shares: float | None = None,
        cost_basis: float | None = None,
    ) -> Position:
        """Update an existing position.

        Args:
            position_id: ID of the position to update
            shares: New number of shares (optional)
            cost_basis: New cost basis (optional)

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

        # Update fields
        if shares is not None:
            position.shares = shares
        if cost_basis is not None:
            position.cost_basis = cost_basis

        position.updated_at = datetime.now(UTC)

        # Update in database using upsert
        df_update = pl.DataFrame([position.model_dump()])
        self.storage.upsert_by_id("portfolio_positions", df_update, "id")

        logger.info(f"Updated position {position_id}")
        return position

    def delete_position(self, position_id: str) -> None:
        """Delete a position.

        Args:
            position_id: ID of the position to delete
        """
        with self.storage.connection() as conn:
            conn.execute(
                "DELETE FROM portfolio_positions WHERE id = ?",
                [position_id],
            )
            conn.commit()  # Commit the deletion

        logger.info(f"Deleted position {position_id}")

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
            positions.append(Position(**row))

        return positions
