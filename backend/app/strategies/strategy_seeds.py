"""Strategy seed storage operations.

This module handles storage and retrieval of strategy seeds - investment theses
that can be converted into full trading strategies.
"""

from __future__ import annotations

import logging
from typing import Any

from app.storage.connection import get_connection_manager

logger = logging.getLogger(__name__)


class SeedStorage:
    """Database operations for strategy seed management."""

    def __init__(self) -> None:
        """Initialize seed storage."""
        self.conn = get_connection_manager()

    def get_strategy_seed(self, seed_id: str) -> tuple[str, float] | None:
        """Get strategy seed details.

        Args:
            seed_id: Seed UUID

        Returns:
            Tuple of (thesis, confidence) or None if not found
        """
        with self.conn.connection() as conn:
            row = conn.execute(
                "SELECT thesis, confidence FROM strategy_seeds WHERE id = %s",
                [seed_id],
            ).fetchone()

            if not row:
                return None

            thesis = str(row[0]) if row[0] else ""
            confidence = float(row[1]) if row[1] is not None else 0.0
            return (thesis, confidence)

    def get_seed_by_strategy_id(self, strategy_id: str) -> dict[str, Any] | None:
        """Get seed info for a strategy.

        Args:
            strategy_id: Strategy UUID

        Returns:
            Dict with seed info or None if no seed exists
        """
        with self.conn.connection() as conn:
            row = conn.execute(
                "SELECT id, thesis, confidence, created_at FROM strategy_seeds WHERE strategy_id = %s",
                [strategy_id],
            ).fetchone()

            if not row:
                return None

            return {
                "id": str(row[0]),
                "thesis": str(row[1]),
                "confidence": float(row[2]) if row[2] is not None else 0.0,
                "created_at": row[3],
            }

    def get_seed_by_id(self, seed_id: str) -> tuple[Any, ...] | None:
        """Get a specific strategy seed by ID.

        Args:
            seed_id: Seed UUID

        Returns:
            Tuple of (id, symbol, thesis, confidence, status, strategy_id, created_at, processed_at)
            or None if not found
        """
        with self.conn.connection() as conn:
            row = conn.execute(
                """
                SELECT id, symbol, thesis, confidence, status, strategy_id,
                       created_at, processed_at
                FROM strategy_seeds
                WHERE id = %s
                """,
                [seed_id],
            ).fetchone()

            return row if row else None

    def link_strategy_to_seed(
        self,
        strategy_id: str,
        seed_id: str,
        seed_thesis: str,
        seed_confidence: float,
    ) -> None:
        """Link a generated strategy back to its seed.

        Updates strategy_definitions with seed info and marks seed as converted.

        Args:
            strategy_id: Strategy UUID
            seed_id: Seed UUID
            seed_thesis: Seed thesis text
            seed_confidence: Seed confidence score
        """
        with self.conn.connection() as conn:
            # Update strategy with seed info
            conn.execute(
                """
                UPDATE strategy_definitions
                SET seed_id = %s, seed_thesis = %s, seed_confidence = %s
                WHERE id = %s
                """,
                [seed_id, seed_thesis, seed_confidence, strategy_id],
            )

            # Mark seed as converted
            conn.execute(
                """
                UPDATE strategy_seeds
                SET status = 'converted', strategy_id = %s, processed_at = NOW()
                WHERE id = %s
                """,
                [strategy_id, seed_id],
            )
            conn.commit()

    def reject_seed(self, seed_id: str) -> None:
        """Mark a seed as rejected.

        Args:
            seed_id: Seed UUID
        """
        with self.conn.connection() as conn:
            conn.execute(
                """
                UPDATE strategy_seeds
                SET status = 'rejected', processed_at = NOW()
                WHERE id = %s
                """,
                [seed_id],
            )
            conn.commit()

    def list_seeds(
        self,
        status: str | None = None,
        symbol: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[Any, ...]], int]:
        """List strategy seeds with optional filtering.

        Args:
            status: Filter by status (optional)
            symbol: Filter by symbol (optional)
            limit: Maximum results (default 50)
            offset: Number of results to skip (default 0)

        Returns:
            Tuple of (rows, total_count) where rows are tuples of:
            (id, symbol, thesis, confidence, status, strategy_id, created_at, processed_at)
        """
        conditions = []
        params: list[Any] = []

        if status:
            conditions.append("status = %s")
            params.append(status)
        if symbol:
            conditions.append("symbol = %s")
            params.append(symbol.upper())

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        with self.conn.connection() as conn:
            # Get total count
            count_query = f"SELECT COUNT(*) FROM strategy_seeds {where_clause}"
            count_row = conn.execute(count_query, params).fetchone()
            total = int(count_row[0]) if count_row and count_row[0] is not None else 0

            # Get seeds with pagination
            query = f"""
                SELECT id, symbol, thesis, confidence, status, strategy_id,
                       created_at, processed_at
                FROM strategy_seeds
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """
            params.extend([limit, offset])
            rows = conn.execute(query, params).fetchall()

            return (rows, total)


# Singleton instance
_seed_storage_instance: SeedStorage | None = None


def get_seed_storage() -> SeedStorage:
    """Get singleton instance of seed storage."""
    global _seed_storage_instance  # noqa: PLW0603
    if _seed_storage_instance is None:
        _seed_storage_instance = SeedStorage()
    return _seed_storage_instance
