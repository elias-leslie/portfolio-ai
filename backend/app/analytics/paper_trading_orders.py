"""Paper trading order creation and management.

This module handles the creation of new paper trades from agent ideas,
including fetching idea details, current prices, and building trade records.
"""

from __future__ import annotations

import datetime as dt
from datetime import UTC, datetime
from typing import cast

from app.analytics.trade_calculations import (
    calculate_stop_loss,
    extract_target_price_from_thesis,
    extract_ticker_from_title,
)
from app.analytics.types import IdeaDetailsDict, PaperTradeDict
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def fetch_idea_details(storage: PortfolioStorage, idea_id: str) -> IdeaDetailsDict | None:
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

    return cast(IdeaDetailsDict, idea_result.to_dicts()[0])


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
    idea: IdeaDetailsDict,
    ticker: str,
    entry_price: float,
    stop_loss_price: float | None,
    target_price: float | None,
    strategy_id: str | None = None,
) -> PaperTradeDict:
    """Build complete paper trade record for insertion.

    Args:
        idea: Agent idea data
        ticker: Stock ticker symbol
        entry_price: Entry price
        stop_loss_price: Stop loss price (optional)
        target_price: Target price (optional)
        strategy_id: Strategy ID that generated this trade (optional)

    Returns:
        Dict with complete paper trade record
    """
    idea_type = idea["action"].lower() if idea["action"] else "buy"
    if idea_type not in ["buy", "sell", "hold"]:
        idea_type = "buy"

    entry_date = dt.date.today()
    now = datetime.now(UTC)

    return cast(
        PaperTradeDict,
        {
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
            "strategy_id": strategy_id,
        },
    )


def create_paper_trade_from_idea(  # noqa: PLR0911
    storage: PortfolioStorage, idea_id: str, strategy_id: str | None = None
) -> PaperTradeDict | None:
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

    # Check earnings proximity (GAP-003)
    from app.analytics.earnings_filter import should_block_for_earnings

    if should_block_for_earnings(storage, ticker):
        logger.warning(
            "paper_trade_blocked_earnings",
            idea_id=idea_id,
            ticker=ticker,
            reason="too_close_to_earnings",
        )
        return None

    # Fetch current price
    entry_price = fetch_entry_price(storage, ticker, idea_id)
    if entry_price is None:
        return None

    # Calculate stop-loss and target price
    stop_loss_price = calculate_stop_loss(storage, ticker, entry_price)
    if stop_loss_price is None:
        logger.warning(
            "paper_trade_blocked_no_atr",
            idea_id=idea_id,
            ticker=ticker,
            reason="insufficient_volatility_data_for_stop_loss",
        )
        return None

    target_price = extract_target_price_from_thesis(idea["thesis"], entry_price)

    # Build paper trade record
    insert_data = build_paper_trade_record(
        idea, ticker, entry_price, stop_loss_price, target_price, strategy_id
    )

    # Insert into database
    try:
        # Convert PaperTradeDict to dict for storage (date/datetime will be handled by insert_dict)
        storage.insert_dict("idea_outcomes", dict(insert_data))  # type: ignore[arg-type]
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


def create_paper_trade_from_strategy_signal(
    storage: PortfolioStorage,
    strategy_id: str,
    symbol: str,
    signal_strength: int,
    signal_reasons: list[str] | None = None,
) -> PaperTradeDict | None:
    """Create a paper trade from a strategy signal.

    This is used by the auto paper trading task to create trades
    when a strategy generates a BUY signal.

    Args:
        storage: PortfolioStorage instance
        strategy_id: Strategy UUID that generated the signal
        symbol: Stock ticker symbol
        signal_strength: Signal strength (0-10)
        signal_reasons: Reasons for the signal

    Returns:
        Dict with paper trade details if successful, None if failed
    """
    import uuid

    from app.analytics.trade_calculations import calculate_stop_loss

    # Generate a unique idea_id for this trade
    idea_id = str(uuid.uuid4())

    # Fetch current price
    entry_price = fetch_entry_price(storage, symbol, idea_id)
    if entry_price is None:
        return None

    # Calculate stop-loss based on ATR
    stop_loss_price = calculate_stop_loss(storage, symbol, entry_price)
    if stop_loss_price is None:
        logger.warning(
            "paper_trade_blocked_no_atr",
            strategy_id=strategy_id,
            symbol=symbol,
            reason="insufficient_volatility_data_for_stop_loss",
        )
        return None

    # Calculate target price (default 15% above entry)
    target_price = entry_price * 1.15

    # Build the trade record
    entry_date = dt.date.today()
    now = datetime.now(UTC)

    insert_data: PaperTradeDict = {
        "idea_id": idea_id,
        "agent_run_id": f"strategy:{strategy_id}",
        "ticker": symbol,
        "idea_type": "buy",
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
        "strategy_id": strategy_id,
    }

    # Also create an agent_ideas record (required for foreign key)
    thesis = f"Auto-generated from strategy signal. Strength: {signal_strength}/10. "
    if signal_reasons:
        thesis += "Reasons: " + ", ".join(signal_reasons[:3])

    try:
        # Create agent_ideas record first
        storage.insert_dict(
            "agent_ideas",
            {
                "id": idea_id,
                "agent_run_id": f"strategy:{strategy_id}",
                "idea_type": "buy",
                "title": f"Buy {symbol}",
                "thesis": thesis,
                "action": f"Buy {symbol}",
                "confidence_score": signal_strength * 10,  # Convert 0-10 to 0-100
                "risk_level": "medium",
                "status": "pending",
                "created_at": now.isoformat(),
            },
        )

        # Create idea_outcomes record
        storage.insert_dict("idea_outcomes", dict(insert_data))  # type: ignore[arg-type]

        logger.info(
            "paper_trade_created_from_strategy",
            strategy_id=strategy_id,
            symbol=symbol,
            entry_price=entry_price,
            signal_strength=signal_strength,
        )
        return insert_data

    except Exception as e:
        logger.error(
            "paper_trade_create_error",
            strategy_id=strategy_id,
            symbol=symbol,
            error=str(e),
        )
        return None
