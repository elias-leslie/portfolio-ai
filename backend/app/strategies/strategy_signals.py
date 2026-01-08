"""Strategy signal storage operations.

This module handles storage and retrieval of strategy trading signals.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from app.storage.connection import get_connection_manager
from app.utils.db_helpers import rows_to_dicts

logger = logging.getLogger(__name__)


class SignalStorage:
    """Database operations for strategy signal management."""

    def __init__(self) -> None:
        """Initialize signal storage."""
        self.conn = get_connection_manager()

    def get_strategy_signals(self, strategy_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent signals for a strategy.

        Args:
            strategy_id: Strategy UUID
            limit: Maximum number of signals to return

        Returns:
            List of signal dicts
        """
        with self.conn.connection() as conn:
            result = conn.execute(
                """
                SELECT id, signal_type, signal_strength, signal_date, reasons, market_data, created_at
                FROM strategy_signals
                WHERE strategy_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                [strategy_id, limit],
            )
            rows = result.fetchall()
            signals_raw = rows_to_dicts(rows, conn)

        signals = []
        for row in signals_raw:
            signals.append(
                {
                    "id": str(row["id"]),
                    "signal_type": str(row["signal_type"]),
                    "signal_strength": int(row["signal_strength"])
                    if row["signal_strength"]
                    else None,
                    "signal_date": row["signal_date"],
                    "reasons": row["reasons"] if row["reasons"] else [],
                    "market_data": row["market_data"] if row["market_data"] else {},
                    "created_at": row["created_at"],
                }
            )
        return signals

    def store_signal(self, signal_data: dict[str, Any]) -> str | None:
        """Store a generated signal in the database.

        Args:
            signal_data: Signal data containing strategy_id, symbol, signal_type, etc.

        Returns:
            Signal ID (UUID string) or None if storage failed
        """
        if "error" in signal_data:
            return None

        try:
            with self.conn.connection() as conn:
                # Ensure symbol exists in symbols table (FK constraint)
                conn.execute(
                    """
                    INSERT INTO symbols (symbol, security_type, created_at)
                    VALUES (%s, 'equity', NOW())
                    ON CONFLICT (symbol) DO NOTHING
                    """,
                    (signal_data["symbol"],),
                )
                result = conn.execute(
                    """
                    INSERT INTO strategy_signals (
                        strategy_id, symbol, signal_date, signal_type,
                        signal_strength, reasons, market_data
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (strategy_id, signal_date) DO UPDATE SET
                        signal_type = EXCLUDED.signal_type,
                        signal_strength = EXCLUDED.signal_strength,
                        reasons = EXCLUDED.reasons,
                        market_data = EXCLUDED.market_data,
                        created_at = NOW()
                    RETURNING id
                    """,
                    (
                        signal_data["strategy_id"],
                        signal_data["symbol"],
                        str(date.today()),
                        signal_data["signal_type"],
                        signal_data["signal_strength"],
                        signal_data["reasons"],
                        json.dumps(signal_data["market_data"]),
                    ),
                ).fetchone()
                conn.commit()
                return str(result[0]) if result else None
        except Exception:
            logger.exception("Failed to store signal")
            return None


# Singleton instance
_signal_storage_instance: SignalStorage | None = None


def get_signal_storage() -> SignalStorage:
    """Get singleton instance of signal storage."""
    global _signal_storage_instance  # noqa: PLW0603
    if _signal_storage_instance is None:
        _signal_storage_instance = SignalStorage()
    return _signal_storage_instance
