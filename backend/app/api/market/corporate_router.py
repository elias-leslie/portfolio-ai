"""Corporate actions endpoints (buybacks, dividends, splits)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.logging_config import get_logger
from app.repositories.market_repository import MarketRepository
from app.storage import get_storage
from app.utils.formatters import format_db_date

router = APIRouter()
logger = get_logger(__name__)

_state: dict[str, MarketRepository] = {}


def _get_market_repo() -> MarketRepository:
    """Lazy singleton to avoid DB connection at import time."""
    if "repo" not in _state:
        _state["repo"] = MarketRepository(get_storage())
    return _state["repo"]


# API endpoints
@router.get("/corporate-actions")
async def get_corporate_actions(
    symbol: str | None = Query(None, description="Filter by symbol"),
    action_type: str = Query("buyback", description="Action type: buyback, dividend, split"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """
    Get corporate actions (buybacks, dividends, splits).

    Returns:
        List of corporate actions with amounts and dates.
    """
    # Use repository for data access
    rows = _get_market_repo().get_corporate_actions(action_type, symbol, limit)

    actions = []
    for row in rows:
        actions.append(
            {
                "symbol": row[0],
                "action_type": row[1],
                "action_date": format_db_date(row[2]),
                "repurchase_amount": float(row[3]) if row[3] else None,
                "shares_repurchased": row[4],
                "dividend_amount": float(row[5]) if row[5] else None,
                "source": row[6],
                "updated_at": format_db_date(row[7]),
            }
        )

    return {
        "actions": actions,
        "total": len(actions),
        "action_type": action_type,
    }


@router.get("/corporate-actions/summary")
async def get_corporate_actions_summary(
    symbol: str | None = Query(None, description="Filter by symbol"),
) -> dict[str, Any]:
    """
    Get summary of corporate actions by symbol.

    Returns:
        Aggregated buyback totals and counts.
    """
    # Use repository for data access
    rows = _get_market_repo().get_corporate_actions_summary(symbol)

    summaries = []
    for row in rows:
        summaries.append(
            {
                "symbol": row[0],
                "buyback_count": row[1] or 0,
                "total_buybacks": float(row[2]) if row[2] else 0,
                "latest_buyback": format_db_date(row[3]),
            }
        )

    return {
        "summaries": summaries,
        "total_symbols": len(summaries),
    }
