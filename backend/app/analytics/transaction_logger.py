"""Transaction logging for paper trading audit trail.

This module handles logging all cash transactions (trade entries and exits)
to the paper_trade_transactions table for complete audit trail.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from app.analytics.types import TransactionDict
from app.logging_config import get_logger

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


class TransactionLogger:
    """Logs all paper trade transactions for audit trail."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize transaction logger.

        Args:
            storage: PortfolioStorage instance for database operations
        """
        self.storage = storage

    def log_entry(
        self,
        trade_id: str,
        symbol: str,
        shares: int,
        price: float,
        cash_before: float,
        cash_after: float,
        notes: str | None = None,
        agent_run_id: str | None = None,
        expected_price: float | None = None,
        slippage_amount: float | None = None,
        slippage_bps: float | None = None,
        adv: float | None = None,
        slippage_model: str | None = None,
    ) -> bool:
        """Log a trade entry transaction with slippage tracking.

        Args:
            trade_id: ID of the trade (idea_id from idea_outcomes)
            symbol: Stock symbol
            shares: Number of shares purchased
            price: Actual fill price per share
            cash_before: Cash balance before transaction
            cash_after: Cash balance after transaction
            notes: Optional transaction notes
            agent_run_id: Optional ID linking to agent workflow (P3 audit trail)
            expected_price: Price at order time before slippage applied
            slippage_amount: Total slippage cost in dollars (actual - expected) * shares
            slippage_bps: Slippage in basis points
            adv: Average Daily Volume at trade time
            slippage_model: Slippage model used (NONE, FIXED_PCT, DYNAMIC)

        Returns:
            True if logged successfully, False otherwise
        """
        amount = shares * price

        insert_query = """
            INSERT INTO paper_trade_transactions (
                trade_id,
                transaction_type,
                symbol,
                shares,
                price,
                amount,
                cash_before,
                cash_after,
                notes,
                agent_run_id,
                expected_price,
                slippage_amount,
                slippage_bps,
                adv,
                slippage_model
            )
            VALUES ($1, 'ENTRY', $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """

        try:
            with self.storage.connection() as conn:
                # Ensure symbol exists in symbols table (FK constraint)
                conn.execute(
                    """
                    INSERT INTO symbols (symbol, security_type, created_at)
                    VALUES ($1, 'equity', NOW())
                    ON CONFLICT (symbol) DO NOTHING
                    """,
                    [symbol],
                )
                conn.execute(
                    insert_query,
                    [
                        trade_id,
                        symbol,
                        shares,
                        price,
                        amount,
                        cash_before,
                        cash_after,
                        notes or f"Entry: {symbol} {shares} shares @ ${price:.2f}",
                        agent_run_id,
                        expected_price,
                        slippage_amount,
                        slippage_bps,
                        adv,
                        slippage_model,
                    ],
                )
                conn.commit()  # Commit INSERT to database

            slippage_info = ""
            if slippage_bps is not None:
                slippage_info = f" [slippage: {slippage_bps:.1f}bps, ${slippage_amount:.2f}]"

            logger.info(
                f"Logged ENTRY transaction: {trade_id} - {symbol} "
                f"{shares} shares @ ${price:.2f} (${amount:.2f}){slippage_info}"
                + (f" [agent: {agent_run_id[:8]}...]" if agent_run_id else "")
            )
            return True

        except Exception as e:
            logger.error(f"Failed to log entry transaction for {trade_id}: {e}")
            return False

    def log_exit(
        self,
        trade_id: str,
        symbol: str,
        shares: int,
        price: float,
        cash_before: float,
        cash_after: float,
        pnl: float,
        notes: str | None = None,
        agent_run_id: str | None = None,
        expected_price: float | None = None,
        slippage_amount: float | None = None,
        slippage_bps: float | None = None,
        adv: float | None = None,
        slippage_model: str | None = None,
    ) -> bool:
        """Log a trade exit transaction with slippage tracking.

        Args:
            trade_id: ID of the trade (idea_id from idea_outcomes)
            symbol: Stock symbol
            shares: Number of shares sold
            price: Actual fill price per share
            cash_before: Cash balance before transaction
            cash_after: Cash balance after transaction
            pnl: Realized profit/loss
            notes: Optional transaction notes (usually exit reason)
            agent_run_id: Optional ID linking to agent workflow (P3 audit trail)
            expected_price: Price at order time before slippage applied
            slippage_amount: Total slippage cost in dollars (expected - actual) * shares
            slippage_bps: Slippage in basis points
            adv: Average Daily Volume at trade time
            slippage_model: Slippage model used (NONE, FIXED_PCT, DYNAMIC)

        Returns:
            True if logged successfully, False otherwise
        """
        amount = shares * price

        # Include P&L in default notes if not provided
        if not notes:
            pnl_sign = "+" if pnl >= 0 else ""
            notes = f"Exit: {symbol} {shares} shares @ ${price:.2f} (P&L: {pnl_sign}${pnl:.2f})"

        insert_query = """
            INSERT INTO paper_trade_transactions (
                trade_id,
                transaction_type,
                symbol,
                shares,
                price,
                amount,
                cash_before,
                cash_after,
                notes,
                agent_run_id,
                expected_price,
                slippage_amount,
                slippage_bps,
                adv,
                slippage_model
            )
            VALUES ($1, 'EXIT', $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """

        try:
            with self.storage.connection() as conn:
                # Ensure symbol exists in symbols table (FK constraint)
                conn.execute(
                    """
                    INSERT INTO symbols (symbol, security_type, created_at)
                    VALUES ($1, 'equity', NOW())
                    ON CONFLICT (symbol) DO NOTHING
                    """,
                    [symbol],
                )
                conn.execute(
                    insert_query,
                    [
                        trade_id,
                        symbol,
                        shares,
                        price,
                        amount,
                        cash_before,
                        cash_after,
                        notes,
                        agent_run_id,
                        expected_price,
                        slippage_amount,
                        slippage_bps,
                        adv,
                        slippage_model,
                    ],
                )
                conn.commit()  # Commit INSERT to database

            slippage_info = ""
            if slippage_bps is not None:
                slippage_info = f" [slippage: {slippage_bps:.1f}bps, ${slippage_amount:.2f}]"

            logger.info(
                f"Logged EXIT transaction: {trade_id} - {symbol} "
                f"{shares} shares @ ${price:.2f} (${amount:.2f}, P&L: ${pnl:.2f}){slippage_info}"
                + (f" [agent: {agent_run_id[:8]}...]" if agent_run_id else "")
            )
            return True

        except Exception as e:
            logger.error(f"Failed to log exit transaction for {trade_id}: {e}")
            return False

    def get_transactions(
        self,
        account_id: str | None = None,
        trade_id: str | None = None,
        limit: int = 100,
    ) -> list[TransactionDict]:
        """Get recent transactions.

        Args:
            account_id: Optional filter by account (not directly stored, joins through trades)
            trade_id: Optional filter by specific trade
            limit: Maximum number of transactions to return

        Returns:
            List of transaction records ordered by timestamp (newest first)
        """
        if trade_id:
            # Filter by specific trade
            query = """
                SELECT
                    t.id,
                    t.trade_id,
                    t.transaction_type,
                    t.symbol,
                    t.shares,
                    t.price,
                    t.amount,
                    t.cash_before,
                    t.cash_after,
                    t.timestamp,
                    t.notes,
                    t.expected_price,
                    t.slippage_amount,
                    t.slippage_bps,
                    t.adv,
                    t.slippage_model
                FROM paper_trade_transactions t
                WHERE t.trade_id = $1
                ORDER BY t.timestamp DESC
                LIMIT $2
            """
            result = self.storage.query(query, [trade_id, limit])

        else:
            # Get all transactions (optionally filtered by account via join)
            # Note: This requires joining through idea_outcomes to find account
            # For MVP, just return all transactions
            query = """
                SELECT
                    id,
                    trade_id,
                    transaction_type,
                    symbol,
                    shares,
                    price,
                    amount,
                    cash_before,
                    cash_after,
                    timestamp,
                    notes,
                    expected_price,
                    slippage_amount,
                    slippage_bps,
                    adv,
                    slippage_model
                FROM paper_trade_transactions
                ORDER BY timestamp DESC
                LIMIT $1
            """
            result = self.storage.query(query, [limit])

        if result.is_empty():
            return []

        # Convert to list of dicts
        transactions: list[TransactionDict] = []
        for row in result.iter_rows(named=True):
            transactions.append(cast(TransactionDict, dict(row)))

        return transactions

    def get_transactions_by_symbol(self, symbol: str, limit: int = 50) -> list[TransactionDict]:
        """Get recent transactions for a specific symbol.

        Args:
            symbol: Stock symbol
            limit: Maximum number of transactions to return

        Returns:
            List of transaction records for the symbol
        """
        query = """
            SELECT
                id,
                trade_id,
                transaction_type,
                symbol,
                shares,
                price,
                amount,
                cash_before,
                cash_after,
                timestamp,
                notes,
                expected_price,
                slippage_amount,
                slippage_bps,
                adv,
                slippage_model
            FROM paper_trade_transactions
            WHERE symbol = $1
            ORDER BY timestamp DESC
            LIMIT $2
        """

        result = self.storage.query(query, [symbol, limit])

        if result.is_empty():
            return []

        transactions: list[TransactionDict] = []
        for row in result.iter_rows(named=True):
            transactions.append(cast(TransactionDict, dict(row)))

        return transactions
