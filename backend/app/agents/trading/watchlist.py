"""Watchlist management executors."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.logging_config import get_logger
from app.utils.db_helpers import ensure_symbol_exists

logger = get_logger(__name__)


def execute_add_symbol(
    storage: PortfolioStorage,
    agent_run_id: str,
    symbol: str,
    reason: str,
    expected_return_pct: float,
    time_horizon_days: int,
) -> dict[str, object]:
    """Execute add_symbol tool to autonomously add symbols to watchlist.

    Args:
        storage: PortfolioStorage instance
        agent_run_id: ID of the agent run (for ownership tracking)
        symbol: Stock symbol
        reason: Why adding this symbol
        expected_return_pct: Expected return percentage
        time_horizon_days: Time horizon in days

    Returns:
        Result dictionary with status and details
    """
    symbol = symbol.upper()

    # Check if symbol already exists
    existing = storage.query("SELECT id, added_by FROM watchlist_items WHERE symbol = $1", [symbol])

    if not existing.is_empty():
        added_by = existing.get_column("added_by")[0]
        return {
            "status": "exists",
            "symbol": symbol,
            "added_by": added_by,
            "message": f"{symbol} already in watchlist (added by {added_by})",
        }

    # Create watchlist item with ownership tracking
    item_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    metadata = {
        "reason": reason,
        "expected_return_pct": expected_return_pct,
        "time_horizon_days": time_horizon_days,
        "added_by_agent": agent_run_id,
    }

    try:
        ensure_symbol_exists(storage, symbol)

        storage.insert_dict(
            "watchlist_items",
            {
                "id": item_id,
                "symbol": symbol,
                "metadata": str(metadata),
                "added_by": agent_run_id,
                "added_at": now.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        )

        logger.info("watchlist_symbol_added", agent_run_id=agent_run_id, symbol=symbol, reason=reason)

        return {
            "status": "added",
            "symbol": symbol,
            "item_id": item_id,
            "message": f"Added {symbol} to watchlist (expected {expected_return_pct}% in {time_horizon_days} days)",
        }

    except Exception as e:
        logger.error("watchlist_add_failed", symbol=symbol, error=str(e), exc_info=True)
        return {
            "status": "error",
            "symbol": symbol,
            "error": str(e),
        }


def execute_remove_symbol(
    storage: PortfolioStorage, agent_run_id: str, symbol: str, reason: str
) -> dict[str, object]:
    """Execute remove_symbol tool with ownership validation.

    Agents can ONLY remove symbols they added. This prevents agents from
    removing user-added symbols or symbols added by other agents.

    Args:
        storage: PortfolioStorage instance
        agent_run_id: ID of the agent run
        symbol: Stock symbol to remove
        reason: Why removing this symbol

    Returns:
        Result dictionary with status and details
    """
    symbol = symbol.upper()

    # Check if symbol exists and get ownership
    existing = storage.query(
        "SELECT id, added_by, added_at FROM watchlist_items WHERE symbol = $1", [symbol]
    )

    if existing.is_empty():
        return {
            "status": "not_found",
            "symbol": symbol,
            "message": f"{symbol} not in watchlist",
        }

    item_id = existing.get_column("id")[0]
    added_by = existing.get_column("added_by")[0]
    added_at = existing.get_column("added_at")[0]

    # Ownership validation
    if added_by != agent_run_id:
        if added_by == "user":
            return {
                "status": "forbidden",
                "symbol": symbol,
                "added_by": added_by,
                "message": f"Cannot remove {symbol} - user-added symbols can only be removed by users",
            }
        return {
            "status": "forbidden",
            "symbol": symbol,
            "added_by": added_by,
            "message": f"Cannot remove {symbol} - added by different agent ({added_by})",
        }

    # Time threshold check (30 days minimum)
    days_since_added = (datetime.now(UTC) - added_at).days
    if days_since_added < 30:
        return {
            "status": "too_soon",
            "symbol": symbol,
            "days_since_added": days_since_added,
            "message": f"Cannot remove {symbol} - only {days_since_added} days since added (need 30+)",
        }

    # Remove symbol
    try:
        with storage.connection() as conn:
            conn.execute("DELETE FROM watchlist_items WHERE id = $1", [item_id])

        logger.info(
            f"Agent {agent_run_id} removed {symbol} from watchlist after {days_since_added} days: {reason}"
        )

        return {
            "status": "removed",
            "symbol": symbol,
            "days_held": days_since_added,
            "message": f"Removed {symbol} from watchlist (held {days_since_added} days): {reason}",
        }

    except Exception as e:
        logger.error("watchlist_remove_failed", symbol=symbol, error=str(e), exc_info=True)
        return {
            "status": "error",
            "symbol": symbol,
            "error": str(e),
        }


__all__ = ["execute_add_symbol", "execute_remove_symbol"]
