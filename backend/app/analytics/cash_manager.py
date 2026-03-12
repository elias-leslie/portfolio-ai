"""Cash management for paper trading accounts.

This module handles cash balance tracking, validation, and updates for paper
trading portfolios. All cash operations are logged to the transaction table
for complete audit trail.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


class CashManager:
    """Manages cash balances for paper trading accounts."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize cash manager.

        Args:
            storage: PortfolioStorage instance for database operations
        """
        self.storage = storage

    def get_cash_balance(self, account_id: str) -> float:
        """Fetch current cash balance for an account.

        Args:
            account_id: Portfolio account ID

        Returns:
            Current cash balance

        Raises:
            ValueError: If account not found
        """
        query = """
            SELECT cash_balance
            FROM portfolio_accounts
            WHERE id = $1
        """

        result = self.storage.query(query, [account_id])

        if result.is_empty():
            error_msg = f"Account not found: {account_id}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        return float(result.get_column("cash_balance")[0])

    def check_sufficient_cash(self, account_id: str, amount: float) -> bool:
        """Check if account has sufficient cash for a transaction.

        Args:
            account_id: Portfolio account ID
            amount: Amount to check

        Returns:
            True if sufficient cash available, False otherwise
        """
        try:
            current_balance = self.get_cash_balance(account_id)
            return current_balance >= amount
        except ValueError:
            logger.error("account_not_found_during_cash_check", account_id=account_id)
            return False

    def deduct_cash(self, account_id: str, amount: float, reason: str) -> bool:
        """Deduct cash from account (for trade entry).

        Args:
            account_id: Portfolio account ID
            amount: Amount to deduct (must be positive)
            reason: Description of transaction

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If amount is negative or zero
        """
        if amount <= 0:
            raise ValueError(f"Deduction amount must be positive, got: {amount}")

        # Check sufficient funds
        if not self.check_sufficient_cash(account_id, amount):
            current_balance = self.get_cash_balance(account_id)
            logger.warning(
                "insufficient_cash",
                account_id=account_id,
                needed=amount,
                available=current_balance,
                reason=reason,
            )
            return False

        # Get current balance before update
        cash_before = self.get_cash_balance(account_id)

        # Update balance
        update_query = """
            UPDATE portfolio_accounts
            SET cash_balance = cash_balance - $1,
                updated_at = NOW()
            WHERE id = $2
        """

        try:
            with self.storage.connection() as conn:
                conn.execute(update_query, [amount, account_id])
                conn.commit()  # Commit UPDATE to database
            cash_after = self.get_cash_balance(account_id)

            logger.info(
                "cash_deducted",
                account_id=account_id,
                amount=amount,
                cash_before=cash_before,
                cash_after=cash_after,
                reason=reason,
            )
            return True

        except Exception as e:
            logger.error("cash_deduction_failed", account_id=account_id, error=str(e), exc_info=True)
            return False

    def add_cash(self, account_id: str, amount: float, reason: str) -> bool:
        """Add cash to account (for trade exit).

        Args:
            account_id: Portfolio account ID
            amount: Amount to add (must be positive)
            reason: Description of transaction

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If amount is negative or zero
        """
        if amount <= 0:
            raise ValueError(f"Addition amount must be positive, got: {amount}")

        # Get current balance before update
        try:
            cash_before = self.get_cash_balance(account_id)
        except ValueError:
            logger.error("cash_add_account_not_found", account_id=account_id)
            return False

        # Update balance
        update_query = """
            UPDATE portfolio_accounts
            SET cash_balance = cash_balance + $1,
                updated_at = NOW()
            WHERE id = $2
        """

        try:
            with self.storage.connection() as conn:
                conn.execute(update_query, [amount, account_id])
                conn.commit()  # Commit UPDATE to database
            cash_after = self.get_cash_balance(account_id)

            logger.info(
                "cash_added",
                account_id=account_id,
                amount=amount,
                cash_before=cash_before,
                cash_after=cash_after,
                reason=reason,
            )
            return True

        except Exception as e:
            logger.error("cash_addition_failed", account_id=account_id, error=str(e), exc_info=True)
            return False

    def reset_cash_balance(self, account_id: str) -> bool:
        """Reset account cash balance to initial_cash value.

        Useful for resetting paper trading accounts.

        Args:
            account_id: Portfolio account ID

        Returns:
            True if successful, False otherwise
        """
        reset_query = """
            UPDATE portfolio_accounts
            SET cash_balance = initial_cash,
                updated_at = NOW()
            WHERE id = $1
        """

        try:
            with self.storage.connection() as conn:
                conn.execute(reset_query, [account_id])
                conn.commit()  # Commit UPDATE to database

            balance = self.get_cash_balance(account_id)
            logger.info("cash_balance_reset", account_id=account_id, balance=balance)
            return True

        except Exception as e:
            logger.error("cash_balance_reset_failed", account_id=account_id, error=str(e), exc_info=True)
            return False
