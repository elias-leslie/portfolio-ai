"""Trade calculation helpers for paper trading.

Provides functions for calculating stop-loss prices, target prices,
and other trade metrics.
"""

from __future__ import annotations

import re
from typing import Any

from app.analytics.indicators import calculate_indicators
from app.logging_config import get_logger
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def calculate_stop_loss(storage: PortfolioStorage, ticker: str, entry_price: float) -> float | None:
    """Calculate stop-loss price using 2x ATR method.

    Args:
        storage: PortfolioStorage instance
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


def extract_target_price_from_thesis(thesis: str, entry_price: float) -> float | None:
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


def extract_ticker_from_title(title: str) -> str | None:
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


def check_exit_conditions(
    trade: dict[str, Any],
    current_price: float,
    holding_days: int,
    max_holding_days: int,
) -> tuple[bool, str | None, str]:
    """Check if trade should be closed based on exit conditions.

    Args:
        trade: Trade dictionary with entry_price, target_price, stop_loss_price, idea_type
        current_price: Current market price
        holding_days: Days since entry
        max_holding_days: Maximum allowed holding period

    Returns:
        Tuple of (should_close, exit_reason, status)
    """
    should_close = False
    exit_reason = None
    status = "open"
    idea_type = trade["idea_type"]

    # Check if target price hit
    if trade["target_price"] is not None:
        if idea_type == "sell":
            # For shorts, target is below entry
            if current_price <= trade["target_price"]:
                should_close = True
                exit_reason = "target"
                status = "target_hit"
        elif current_price >= trade["target_price"]:
            should_close = True
            exit_reason = "target"
            status = "target_hit"

    # Check if stop loss hit
    if not should_close and trade["stop_loss_price"] is not None:
        if idea_type == "sell":
            # For shorts, stop is above entry
            if current_price >= trade["stop_loss_price"]:
                should_close = True
                exit_reason = "stop"
                status = "stop_hit"
        elif current_price <= trade["stop_loss_price"]:
            should_close = True
            exit_reason = "stop"
            status = "stop_hit"

    # Check if max holding period exceeded
    if not should_close and holding_days >= max_holding_days:
        should_close = True
        exit_reason = "time_limit"
        status = "expired"

    return should_close, exit_reason, status
