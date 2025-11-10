"""Paper trading tracker for agent idea performance.

This module provides functions for creating and updating paper trades
to track the real-world performance of AI agent investment ideas.
"""

from __future__ import annotations

import datetime as dt
from datetime import UTC, datetime
from typing import Any

from app.analytics.trade_calculations import (
    calculate_stop_loss,
    check_exit_conditions,
    extract_target_price_from_thesis,
    extract_ticker_from_title,
)
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def _fetch_idea_details(storage: PortfolioStorage, idea_id: str) -> dict[str, Any] | None:
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


def _fetch_entry_price(storage: PortfolioStorage, ticker: str, idea_id: str) -> float | None:
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


def _build_paper_trade_record(
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


def create_paper_trade(storage: PortfolioStorage, idea_id: str) -> dict[str, Any] | None:
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
        >>> trade = create_paper_trade(storage, "idea-123")
        >>> print(f"Created paper trade for {trade['ticker']} at ${trade['entry_price']}")
    """
    # Fetch idea details
    idea = _fetch_idea_details(storage, idea_id)
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
    entry_price = _fetch_entry_price(storage, ticker, idea_id)
    if entry_price is None:
        return None

    # Calculate stop-loss and target price
    stop_loss_price = calculate_stop_loss(storage, ticker, entry_price)
    target_price = extract_target_price_from_thesis(idea["thesis"], entry_price)

    # Build paper trade record
    insert_data = _build_paper_trade_record(
        idea, ticker, entry_price, stop_loss_price, target_price
    )

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


def _fetch_open_trades(storage: PortfolioStorage) -> list[dict[str, Any]]:
    """Fetch all open paper trades from database.

    Args:
        storage: PortfolioStorage instance

    Returns:
        List of open trade records
    """
    open_trades_query = """
        SELECT
            idea_id,
            ticker,
            idea_type,
            entry_price,
            entry_date,
            target_price,
            stop_loss_price,
            current_price,
            current_return_pct,
            max_favorable_pct,
            max_adverse_pct,
            created_at
        FROM idea_outcomes
        WHERE status = 'open'
    """

    open_trades = storage.query(open_trades_query)

    if open_trades.is_empty():
        return []

    return open_trades.to_dicts()


def _calculate_trade_return(entry_price: float, current_price: float, idea_type: str) -> float:
    """Calculate return percentage for trade.

    Args:
        entry_price: Entry price
        current_price: Current price
        idea_type: 'buy', 'sell', or 'hold'

    Returns:
        Return percentage (positive = profit, negative = loss)
    """
    if idea_type == "sell":
        # Short position: profit when price goes down
        return ((entry_price - current_price) / entry_price) * 100

    # Long position: profit when price goes up
    return ((current_price - entry_price) / entry_price) * 100


def _update_trade_excursions(
    trade: dict[str, Any], current_return_pct: float
) -> tuple[float, float]:
    """Update max favorable and adverse excursions.

    Args:
        trade: Trade record with existing excursions
        current_return_pct: Current return percentage

    Returns:
        Tuple of (max_favorable_pct, max_adverse_pct)
    """
    max_favorable_pct = max(trade["max_favorable_pct"] or 0.0, current_return_pct)
    max_adverse_pct = min(trade["max_adverse_pct"] or 0.0, current_return_pct)
    return max_favorable_pct, max_adverse_pct


def _update_open_trade(
    storage: PortfolioStorage,
    trade: dict[str, Any],
    current_price: float,
    current_return_pct: float,
    max_favorable_pct: float,
    max_adverse_pct: float,
    holding_days: int,
) -> None:
    """Update open trade with current values.

    Args:
        storage: PortfolioStorage instance
        trade: Trade record
        current_price: Current price
        current_return_pct: Current return percentage
        max_favorable_pct: Maximum favorable excursion
        max_adverse_pct: Maximum adverse excursion
        holding_days: Number of days held
    """
    update_query = """
        UPDATE idea_outcomes
        SET current_price = ?,
            current_return_pct = ?,
            max_favorable_pct = ?,
            max_adverse_pct = ?,
            holding_days = ?,
            updated_at = ?
        WHERE idea_id = ?
    """

    storage.query(
        update_query,
        [
            current_price,
            current_return_pct,
            max_favorable_pct,
            max_adverse_pct,
            holding_days,
            datetime.now(UTC),
            trade["idea_id"],
        ],
    )


def _close_trade(
    storage: PortfolioStorage,
    trade: dict[str, Any],
    current_price: float,
    current_return_pct: float,
    max_favorable_pct: float,
    max_adverse_pct: float,
    holding_days: int,
    exit_reason: str | None,
    status: str,
) -> None:
    """Close trade with exit details.

    Args:
        storage: PortfolioStorage instance
        trade: Trade record
        current_price: Exit price
        current_return_pct: Final return percentage
        max_favorable_pct: Maximum favorable excursion
        max_adverse_pct: Maximum adverse excursion
        holding_days: Number of days held
        exit_reason: Reason for exit (target/stop/time_limit), None if unknown
        status: Exit status (target_hit/stop_hit/expired)
    """
    update_query = """
        UPDATE idea_outcomes
        SET current_price = ?,
            current_return_pct = ?,
            max_favorable_pct = ?,
            max_adverse_pct = ?,
            holding_days = ?,
            status = ?,
            exit_price = ?,
            exit_date = ?,
            exit_reason = ?,
            realized_return_pct = ?,
            updated_at = ?
        WHERE idea_id = ?
    """

    storage.query(
        update_query,
        [
            current_price,
            current_return_pct,
            max_favorable_pct,
            max_adverse_pct,
            holding_days,
            status,
            current_price,  # exit_price
            dt.date.today(),  # exit_date
            exit_reason,
            current_return_pct,  # realized_return_pct
            datetime.now(UTC),
            trade["idea_id"],
        ],
    )

    logger.info(
        "paper_trade_closed",
        idea_id=trade["idea_id"],
        ticker=trade["ticker"],
        entry_price=trade["entry_price"],
        exit_price=current_price,
        realized_return_pct=round(current_return_pct, 2),
        holding_days=holding_days,
        exit_reason=exit_reason,
    )


def _process_single_trade(
    storage: PortfolioStorage,
    trade: dict[str, Any],
    price_data: dict[str, Any],
    today: dt.date,
    max_holding_days: int,
    stats: dict[str, Any],
) -> None:
    """Process a single trade update.

    Args:
        storage: PortfolioStorage instance
        trade: Trade record
        price_data: Dict of ticker -> price data
        today: Current date
        max_holding_days: Maximum holding period
        stats: Statistics dict to update (modified in-place)
    """
    ticker = trade["ticker"]

    # Skip if price fetch failed
    if ticker not in price_data:
        logger.warning(
            "paper_trade_update_skipped",
            idea_id=trade["idea_id"],
            ticker=ticker,
            reason="price_fetch_failed",
        )
        return

    # Calculate returns and metrics
    current_price = price_data[ticker].price
    current_return_pct = _calculate_trade_return(
        trade["entry_price"], current_price, trade["idea_type"]
    )
    max_favorable_pct, max_adverse_pct = _update_trade_excursions(trade, current_return_pct)
    holding_days = (today - trade["entry_date"]).days

    # Check if trade should close
    should_close, exit_reason, status = check_exit_conditions(
        trade, current_price, holding_days, max_holding_days
    )

    # Update or close trade
    if should_close:
        _close_trade(
            storage,
            trade,
            current_price,
            current_return_pct,
            max_favorable_pct,
            max_adverse_pct,
            holding_days,
            exit_reason,
            status,
        )
        stats["trades_closed"] += 1

        # Update exit reason stats
        if exit_reason == "target":
            stats["target_hits"] += 1
        elif exit_reason == "stop":
            stats["stop_hits"] += 1
        elif exit_reason == "time_limit":
            stats["expired"] += 1
    else:
        _update_open_trade(
            storage,
            trade,
            current_price,
            current_return_pct,
            max_favorable_pct,
            max_adverse_pct,
            holding_days,
        )

    stats["trades_updated"] += 1


def update_paper_trades(storage: PortfolioStorage, max_holding_days: int = 60) -> dict[str, Any]:
    """Update all open paper trades with current prices and check for exits.

    Fetches current prices for all open trades, updates returns, and closes
    trades that hit target/stop or exceed max holding period.

    Args:
        storage: PortfolioStorage instance for database access
        max_holding_days: Maximum days to hold before auto-closing (default: 60)

    Returns:
        Dict with update statistics:
        - trades_updated: Number of trades updated
        - trades_closed: Number of trades closed
        - target_hits: Number of target price hits
        - stop_hits: Number of stop loss hits
        - expired: Number of trades closed due to time limit

    Example:
        >>> storage = get_storage()
        >>> stats = update_paper_trades(storage, max_holding_days=60)
        >>> print(f"Updated {stats['trades_updated']} trades, closed {stats['trades_closed']}")
    """
    # Fetch all open trades
    trades_list = _fetch_open_trades(storage)

    if not trades_list:
        logger.info("paper_trade_update", trades_updated=0, trades_closed=0)
        return {
            "trades_updated": 0,
            "trades_closed": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "expired": 0,
        }

    # Fetch current prices for all tickers
    tickers = list({trade["ticker"] for trade in trades_list})
    price_fetcher = PriceDataFetcher(storage)
    price_data = price_fetcher.fetch_price_data(tickers)

    # Initialize statistics
    stats = {
        "trades_updated": 0,
        "trades_closed": 0,
        "target_hits": 0,
        "stop_hits": 0,
        "expired": 0,
    }

    today = dt.date.today()

    # Process each trade
    for trade in trades_list:
        _process_single_trade(storage, trade, price_data, today, max_holding_days, stats)

    logger.info(
        "paper_trade_update_complete",
        trades_updated=stats["trades_updated"],
        trades_closed=stats["trades_closed"],
        target_hits=stats["target_hits"],
        stop_hits=stats["stop_hits"],
        expired=stats["expired"],
    )

    return stats
