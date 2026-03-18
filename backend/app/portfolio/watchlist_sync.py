"""Shared helpers for ensuring symbols exist in the watchlist."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from ..logging_config import get_logger
from ..storage import PortfolioStorage
from ..utils.db_helpers import ensure_symbol_exists

logger = get_logger(__name__)


def ensure_symbols_in_watchlist(
    storage: PortfolioStorage,
    symbols: list[str],
    *,
    source: str = "portfolio",
) -> list[str]:
    """Ensure symbols exist in watchlist_items and symbols tables.

    Returns the list of newly inserted symbols.
    """
    if not symbols:
        return []

    unique_symbols = list({symbol.upper() for symbol in symbols if symbol})
    if not unique_symbols:
        return []

    df = storage.query("SELECT symbol FROM watchlist_items")
    existing_symbols = set()
    if not df.is_empty():
        existing_symbols = {row["symbol"] for row in df.iter_rows(named=True)}

    symbols_to_add = [symbol for symbol in unique_symbols if symbol not in existing_symbols]
    if not symbols_to_add:
        return []

    now = datetime.now(UTC)
    with storage.connection() as conn:
        for symbol in symbols_to_add:
            ensure_symbol_exists(conn, symbol)
            conn.execute(
                """
                INSERT INTO watchlist_items (id, symbol, source, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO NOTHING
                """,
                [str(uuid.uuid4()), symbol, source, now, now],
            )
        conn.commit()

    logger.info(
        "symbols_synced_to_watchlist",
        source=source,
        count=len(symbols_to_add),
        symbols=symbols_to_add,
    )
    return symbols_to_add
