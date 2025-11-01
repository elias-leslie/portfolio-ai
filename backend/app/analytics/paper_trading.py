"""Paper trading tracker for agent idea performance.

This module provides functions for creating and updating paper trades
to track the real-world performance of AI agent investment ideas.
"""

from __future__ import annotations

import datetime as dt
import re
from datetime import UTC, datetime
from typing import Any

from app.analytics.indicators import calculate_indicators
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import DuckDBStorage

logger = get_logger(__name__)


def create_paper_trade(storage: DuckDBStorage, idea_id: str) -> dict[str, Any] | None:
    """Create a paper trade entry for an agent idea.

    Extracts idea details from agent_ideas table, fetches current price,
    calculates stop-loss based on ATR, and creates idea_outcomes record.

    Args:
        storage: DuckDBStorage instance for database access
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
    # Fetch idea details from agent_ideas table
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

    idea = idea_result.to_dicts()[0]

    # Extract ticker from title (assumes format like "Buy AAPL" or "AAPL: Strong Buy")
    ticker = _extract_ticker_from_title(idea["title"])

    if not ticker:
        logger.warning(
            "paper_trade_create_failed",
            reason="ticker_not_extracted",
            idea_id=idea_id,
            title=idea["title"],
        )
        return None

    # Fetch current price
    price_fetcher = PriceDataFetcher(storage)
    price_data = price_fetcher.fetch_price_data([ticker])

    if ticker not in price_data:
        logger.warning(
            "paper_trade_create_failed", reason="price_fetch_failed", idea_id=idea_id, ticker=ticker
        )
        return None

    entry_price = price_data[ticker].price

    # Calculate stop-loss using ATR (2x ATR below entry)
    stop_loss_price = _calculate_stop_loss(storage, ticker, entry_price)

    # Extract target price from thesis if available (simple heuristic)
    target_price = _extract_target_price_from_thesis(idea["thesis"], entry_price)

    # Determine idea_type from action field
    idea_type = idea["action"].lower() if idea["action"] else "buy"
    if idea_type not in ["buy", "sell", "hold"]:
        idea_type = "buy"  # Default to buy

    # Insert into idea_outcomes table
    entry_date = dt.date.today()
    now = datetime.now(UTC)

    insert_data = {
        "idea_id": idea_id,
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


def update_paper_trades(storage: DuckDBStorage, max_holding_days: int = 60) -> dict[str, Any]:
    """Update all open paper trades with current prices and check for exits.

    Fetches current prices for all open trades, updates returns, and closes
    trades that hit target/stop or exceed max holding period.

    Args:
        storage: DuckDBStorage instance for database access
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
    # Fetch all open paper trades
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
        logger.info("paper_trade_update", trades_updated=0, trades_closed=0)
        return {
            "trades_updated": 0,
            "trades_closed": 0,
            "target_hits": 0,
            "stop_hits": 0,
            "expired": 0,
        }

    trades_list = open_trades.to_dicts()

    # Fetch current prices for all tickers
    tickers = list({trade["ticker"] for trade in trades_list})
    price_fetcher = PriceDataFetcher(storage)
    price_data = price_fetcher.fetch_price_data(tickers)

    # Update statistics
    stats = {
        "trades_updated": 0,
        "trades_closed": 0,
        "target_hits": 0,
        "stop_hits": 0,
        "expired": 0,
    }

    now = datetime.now(UTC)
    today = dt.date.today()

    for trade in trades_list:
        ticker = trade["ticker"]

        # Skip if price fetch failed
        if ticker not in price_data:
            logger.warning(
                "paper_trade_update_skipped",
                idea_id=trade["idea_id"],
                ticker=ticker,
                reason="price_fetch_failed",
            )
            continue

        current_price = price_data[ticker].price
        entry_price = trade["entry_price"]

        # Calculate returns (handle both long and short positions)
        if trade["idea_type"] == "sell":
            # For short positions: profit when price goes down
            current_return_pct = ((entry_price - current_price) / entry_price) * 100
        else:
            # For long positions (buy/hold): profit when price goes up
            current_return_pct = ((current_price - entry_price) / entry_price) * 100

        # Track max favorable and adverse excursions
        max_favorable_pct = max(trade["max_favorable_pct"] or 0.0, current_return_pct)
        max_adverse_pct = min(trade["max_adverse_pct"] or 0.0, current_return_pct)

        # Calculate holding days
        holding_days = (today - trade["entry_date"]).days

        # Check exit conditions
        should_close = False
        exit_reason = None
        status = "open"

        # Check if target price hit
        if trade["target_price"] is not None:
            if trade["idea_type"] == "sell":
                # For shorts, target is below entry
                if current_price <= trade["target_price"]:
                    should_close = True
                    exit_reason = "target"
                    status = "target_hit"
                    stats["target_hits"] += 1
            elif current_price >= trade["target_price"]:
                should_close = True
                exit_reason = "target"
                status = "target_hit"
                stats["target_hits"] += 1

        # Check if stop loss hit
        if not should_close and trade["stop_loss_price"] is not None:
            if trade["idea_type"] == "sell":
                # For shorts, stop is above entry
                if current_price >= trade["stop_loss_price"]:
                    should_close = True
                    exit_reason = "stop"
                    status = "stop_hit"
                    stats["stop_hits"] += 1
            elif current_price <= trade["stop_loss_price"]:
                should_close = True
                exit_reason = "stop"
                status = "stop_hit"
                stats["stop_hits"] += 1

        # Check if max holding period exceeded
        if not should_close and holding_days >= max_holding_days:
            should_close = True
            exit_reason = "time_limit"
            status = "expired"
            stats["expired"] += 1

        # Update trade record
        if should_close:
            # Close the trade
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
                    today,  # exit_date
                    exit_reason,
                    current_return_pct,  # realized_return_pct
                    now,
                    trade["idea_id"],
                ],
            )

            stats["trades_closed"] += 1
            logger.info(
                "paper_trade_closed",
                idea_id=trade["idea_id"],
                ticker=ticker,
                entry_price=entry_price,
                exit_price=current_price,
                realized_return_pct=round(current_return_pct, 2),
                holding_days=holding_days,
                exit_reason=exit_reason,
            )
        else:
            # Update current values only
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
                    now,
                    trade["idea_id"],
                ],
            )

        stats["trades_updated"] += 1

    logger.info(
        "paper_trade_update_complete",
        trades_updated=stats["trades_updated"],
        trades_closed=stats["trades_closed"],
        target_hits=stats["target_hits"],
        stop_hits=stats["stop_hits"],
        expired=stats["expired"],
    )

    return stats


def _extract_ticker_from_title(title: str) -> str | None:
    """Extract ticker symbol from idea title.

    Handles common formats:
    - "Buy AAPL"
    - "AAPL: Strong Buy"
    - "Long NVDA position"
    - "Short TSLA"

    Args:
        title: Idea title string

    Returns:
        Ticker symbol in uppercase, or None if not found
    """
    # Look for 1-5 uppercase letter sequences (typical ticker format)
    # Match standalone tickers or tickers followed by colon/space
    pattern = r"\b([A-Z]{1,5})\b"
    matches = re.findall(pattern, title)

    if matches:
        # Filter out common words that match the pattern
        common_words = {"BUY", "SELL", "LONG", "SHORT", "HOLD", "THE", "AND", "OR", "A", "I"}
        tickers = [m for m in matches if m not in common_words]

        if tickers:
            ticker_str: str = tickers[0]  # Return first ticker found
            return ticker_str

    return None


def _calculate_stop_loss(storage: DuckDBStorage, ticker: str, entry_price: float) -> float | None:
    """Calculate stop-loss price using 2x ATR method.

    Args:
        storage: DuckDBStorage instance
        ticker: Stock ticker symbol
        entry_price: Entry price for the trade

    Returns:
        Stop loss price (entry - 2xATR), or None if ATR unavailable
    """
    try:
        # Try to get ATR from technical_indicators table
        atr_query = """
            SELECT atr_14
            FROM technical_indicators
            WHERE ticker = ?
            ORDER BY date DESC
            LIMIT 1
        """

        atr_result = storage.query(atr_query, [ticker])

        if not atr_result.is_empty():
            atr_value = atr_result.to_dicts()[0]["atr_14"]
            if atr_value is not None:
                atr: float = float(atr_value)
                stop_loss = entry_price - (2 * atr)
                return max(stop_loss, 0.0)  # Ensure non-negative

        # Fallback: calculate ATR on the fly
        indicators = calculate_indicators(storage, ticker, ["atr"])
        if indicators and "atr_14" in indicators:
            atr_indicator = indicators["atr_14"]
            if atr_indicator is not None:
                atr_calc: float = float(atr_indicator)
                stop_loss_calc = entry_price - (2 * atr_calc)
                return max(stop_loss_calc, 0.0)

        # If ATR unavailable, use simple 5% stop loss
        logger.warning(
            "stop_loss_fallback",
            ticker=ticker,
            method="5_percent_default",
        )
        return entry_price * 0.95

    except Exception as e:
        logger.error(
            "stop_loss_calculation_error",
            ticker=ticker,
            error=str(e),
        )
        # Fallback to 5% stop loss
        return entry_price * 0.95


def _extract_target_price_from_thesis(thesis: str, entry_price: float) -> float | None:
    """Extract target price from thesis text.

    Looks for patterns like "target $180" or "price target of 200".

    Args:
        thesis: Thesis text from agent idea
        entry_price: Entry price for context

    Returns:
        Target price if found, or estimated target (entry + 10%) if not found
    """
    # Look for "target" followed by dollar amount or number
    patterns = [
        r"target\s+\$?(\d+\.?\d*)",
        r"price target\s+of\s+\$?(\d+\.?\d*)",
        r"upside to\s+\$?(\d+\.?\d*)",
    ]

    for pattern in patterns:
        match = re.search(pattern, thesis, re.IGNORECASE)
        if match:
            try:
                target = float(match.group(1))
                # Sanity check: target should be within reasonable range of entry
                if 0.5 * entry_price <= target <= 3.0 * entry_price:
                    return target
            except ValueError:
                continue

    # Default: 10% upside target
    return entry_price * 1.10
