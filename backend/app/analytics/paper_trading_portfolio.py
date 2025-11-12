"""Paper trading portfolio calculations and updates.

This module handles updating existing paper trades with current prices,
calculating returns, tracking excursions, and closing trades.
"""

from __future__ import annotations

import datetime as dt
from datetime import UTC, datetime
from typing import Any

from app.analytics.trade_calculations import check_exit_conditions
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def fetch_open_trades(storage: PortfolioStorage) -> list[dict[str, Any]]:
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


def calculate_trade_return(entry_price: float, current_price: float, idea_type: str) -> float:
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


def update_trade_excursions(
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


def update_open_trade(
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


def close_trade(
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


def process_single_trade(
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
    current_return_pct = calculate_trade_return(
        trade["entry_price"], current_price, trade["idea_type"]
    )
    max_favorable_pct, max_adverse_pct = update_trade_excursions(trade, current_return_pct)
    holding_days = (today - trade["entry_date"]).days

    # Check if trade should close
    should_close, exit_reason, status = check_exit_conditions(
        trade, current_price, holding_days, max_holding_days
    )

    # Update or close trade
    if should_close:
        close_trade(
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
        update_open_trade(
            storage,
            trade,
            current_price,
            current_return_pct,
            max_favorable_pct,
            max_adverse_pct,
            holding_days,
        )

    stats["trades_updated"] += 1


def update_all_paper_trades(
    storage: PortfolioStorage, max_holding_days: int = 60
) -> dict[str, Any]:
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
        >>> stats = update_all_paper_trades(storage, max_holding_days=60)
        >>> print(f"Updated {stats['trades_updated']} trades, closed {stats['trades_closed']}")
    """
    # Fetch all open trades
    trades_list = fetch_open_trades(storage)

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
        process_single_trade(storage, trade, price_data, today, max_holding_days, stats)

    logger.info(
        "paper_trade_update_complete",
        trades_updated=stats["trades_updated"],
        trades_closed=stats["trades_closed"],
        target_hits=stats["target_hits"],
        stop_hits=stats["stop_hits"],
        expired=stats["expired"],
    )

    return stats
