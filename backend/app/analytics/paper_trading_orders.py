"""Paper trading order creation and management.

This module handles the creation of new paper trades from agent ideas,
including fetching idea details, current prices, and building trade records.
"""

from __future__ import annotations

import datetime as dt
from datetime import UTC, datetime
from typing import Any

from app.analytics.trade_calculations import (
    calculate_stop_loss,
    extract_target_price_from_thesis,
    extract_ticker_from_title,
)
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def fetch_idea_details(storage: PortfolioStorage, idea_id: str) -> dict[str, Any] | None:
    """Fetch agent idea details from database.

    Args:
        storage: PortfolioStorage instance
        idea_id: ID of the agent idea

    Returns:
        Dict with idea details if found, None otherwise
    """
    idea_query = """
        SELECT
            id,
            agent_run_id,
            idea_type,
            title,
            thesis,
            action,
            created_at
        FROM agent_ideas
        WHERE id = ?
    """

    idea_result = storage.query(idea_query, [idea_id])

    if idea_result.is_empty():
        logger.warning("paper_trade_create_failed", reason="idea_not_found", idea_id=idea_id)
        return None

    return idea_result.to_dicts()[0]


def fetch_entry_price(storage: PortfolioStorage, ticker: str, idea_id: str) -> float | None:
    """Fetch current market price for ticker.

    Args:
        storage: PortfolioStorage instance
        ticker: Stock ticker symbol
        idea_id: ID of the idea (for logging)

    Returns:
        Current price if available, None otherwise
    """
    price_fetcher = PriceDataFetcher(storage)
    price_data = price_fetcher.fetch_price_data([ticker])

    if ticker not in price_data:
        logger.warning(
            "paper_trade_create_failed", reason="price_fetch_failed", idea_id=idea_id, ticker=ticker
        )
        return None

    return price_data[ticker].price


def build_paper_trade_record(
    idea: dict[str, Any],
    ticker: str,
    entry_price: float,
    stop_loss_price: float | None,
    target_price: float | None,
) -> dict[str, Any]:
    """Build complete paper trade record for insertion.

    Args:
        idea: Agent idea data
        ticker: Stock ticker symbol
        entry_price: Entry price
        stop_loss_price: Stop loss price (optional)
        target_price: Target price (optional)

    Returns:
        Dict with complete paper trade record
    """
    idea_type = idea["action"].lower() if idea["action"] else "buy"
    if idea_type not in ["buy", "sell", "hold"]:
        idea_type = "buy"

    entry_date = dt.date.today()
    now = datetime.now(UTC)

    return {
        "idea_id": idea["id"],
        "agent_run_id": idea["agent_run_id"],
        "ticker": ticker,
        "idea_type": idea_type,
        "entry_price": entry_price,
        "entry_date": entry_date,
        "target_price": target_price,
        "stop_loss_price": stop_loss_price,
        "current_price": entry_price,
        "current_return_pct": 0.0,
        "status": "open",
        "exit_price": None,
        "exit_date": None,
        "exit_reason": None,
        "realized_return_pct": None,
        "holding_days": 0,
        "max_favorable_pct": 0.0,
        "max_adverse_pct": 0.0,
        "created_at": now,
        "updated_at": now,
    }


def create_paper_trade_from_idea(storage: PortfolioStorage, idea_id: str) -> dict[str, Any] | None:
    """Create a paper trade entry for an agent idea.

    Extracts idea details from agent_ideas table, fetches current price,
    calculates stop-loss based on ATR, and creates idea_outcomes record.

    Args:
        storage: PortfolioStorage instance for database access
        idea_id: ID of the agent idea to track

    Returns:
        Dict with paper trade details if successful, None if failed
        - ticker: Stock ticker symbol
        - entry_price: Current market price
        - stop_loss_price: Calculated stop loss (entry - 2xATR)
        - target_price: From agent idea (if available)
        - status: 'open'

    Example:
        >>> storage = get_storage()
        >>> trade = create_paper_trade_from_idea(storage, "idea-123")
        >>> print(f"Created paper trade for {trade['ticker']} at ${trade['entry_price']}")
    """
    # Fetch idea details
    idea = fetch_idea_details(storage, idea_id)
    if not idea:
        return None

    # Extract ticker from title
    ticker = extract_ticker_from_title(idea["title"])
    if not ticker:
        logger.warning(
            "paper_trade_create_failed",
            reason="ticker_not_extracted",
            idea_id=idea_id,
            title=idea["title"],
        )
        return None

    # Fetch current price
    entry_price = fetch_entry_price(storage, ticker, idea_id)
    if entry_price is None:
        return None

    # Calculate stop-loss and target price
    stop_loss_price = calculate_stop_loss(storage, ticker, entry_price)
    target_price = extract_target_price_from_thesis(idea["thesis"], entry_price)

    # Build paper trade record
    insert_data = build_paper_trade_record(idea, ticker, entry_price, stop_loss_price, target_price)

    # Insert into database
    try:
        storage.insert_dict("idea_outcomes", insert_data)
        logger.info(
            "paper_trade_created",
            idea_id=idea_id,
            ticker=ticker,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            target_price=target_price,
        )
        return insert_data
    except Exception as e:
        logger.error(
            "paper_trade_create_error",
            idea_id=idea_id,
            ticker=ticker,
            error=str(e),
        )
        return None
