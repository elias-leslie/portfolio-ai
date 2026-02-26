"""Paper trading order creation and management from agent ideas and strategy signals."""

from __future__ import annotations

import datetime as dt
import uuid
from datetime import UTC, datetime
from typing import cast

from app.analytics._paper_trading_order_helpers import (
    acquire_position,
    build_strategy_trade_dict,
    fetch_strategy_metrics,
    insert_strategy_trade_records,
    validate_strategy_metrics,
)
from app.analytics.earnings_filter import should_block_for_earnings
from app.analytics.trade_calculations import (
    calculate_stop_loss,
    extract_symbol_from_title,
    extract_target_price_from_thesis,
)
from app.analytics.types import IdeaDetailsDict, PaperTradeDict
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import PortfolioStorage

logger = get_logger(__name__)


def fetch_idea_details(storage: PortfolioStorage, idea_id: str) -> IdeaDetailsDict | None:
    """Fetch agent idea details from database."""
    idea_result = storage.query(
        "SELECT id, agent_run_id, idea_type, title, thesis, action, created_at"
        " FROM agent_ideas WHERE id = ?",
        [idea_id],
    )
    if idea_result.is_empty():
        logger.warning("paper_trade_create_failed", reason="idea_not_found", idea_id=idea_id)
        return None
    return cast(IdeaDetailsDict, idea_result.to_dicts()[0])


def fetch_entry_price(storage: PortfolioStorage, symbol: str, idea_id: str) -> float | None:
    """Fetch current market price for symbol."""
    price_fetcher = PriceDataFetcher(storage)
    price_data = price_fetcher.fetch_price_data([symbol])
    if symbol not in price_data:
        logger.warning(
            "paper_trade_create_failed", reason="price_fetch_failed", idea_id=idea_id, symbol=symbol
        )
        return None
    return price_data[symbol].price


def build_paper_trade_record(
    idea: IdeaDetailsDict,
    symbol: str,
    entry_price: float,
    stop_loss_price: float | None,
    target_price: float | None,
    strategy_id: str | None = None,
) -> PaperTradeDict:
    """Build complete paper trade record for insertion."""
    idea_type = idea["action"].lower() if idea["action"] else "buy"
    if idea_type not in ["buy", "sell", "hold"]:
        idea_type = "buy"
    now = datetime.now(UTC)
    return cast(
        PaperTradeDict,
        {
            "idea_id": idea["id"],
            "agent_run_id": idea["agent_run_id"],
            "symbol": symbol,
            "idea_type": idea_type,
            "entry_price": entry_price,
            "entry_date": dt.date.today(),
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
    """Create a paper trade entry for an agent idea."""
    idea = fetch_idea_details(storage, idea_id)
    if not idea:
        return None

    symbol = extract_symbol_from_title(idea["title"])
    if not symbol:
        logger.warning(
            "paper_trade_create_failed", reason="symbol_not_extracted",
            idea_id=idea_id, title=idea["title"],
        )
        return None

    if should_block_for_earnings(storage, symbol):
        logger.warning(
            "paper_trade_blocked_earnings", idea_id=idea_id, symbol=symbol,
            reason="too_close_to_earnings",
        )
        return None

    entry_price = fetch_entry_price(storage, symbol, idea_id)
    if entry_price is None:
        return None

    stop_loss_price = calculate_stop_loss(storage, symbol, entry_price)
    if stop_loss_price is None:
        logger.warning(
            "paper_trade_blocked_no_atr", idea_id=idea_id, symbol=symbol,
            reason="insufficient_volatility_data_for_stop_loss",
        )
        return None

    target_price = extract_target_price_from_thesis(idea["thesis"], entry_price)
    insert_data = build_paper_trade_record(
        idea, symbol, entry_price, stop_loss_price, target_price, strategy_id
    )
    try:
        storage.insert_dict("idea_outcomes", dict(insert_data))  # type: ignore[arg-type]
        logger.info(
            "paper_trade_created", idea_id=idea_id, symbol=symbol,
            entry_price=entry_price, stop_loss_price=stop_loss_price, target_price=target_price,
        )
        return insert_data
    except Exception as e:
        logger.error("paper_trade_create_error", idea_id=idea_id, symbol=symbol, error=str(e))
        return None


def create_paper_trade_from_strategy_signal(
    storage: PortfolioStorage,
    strategy_id: str,
    symbol: str,
    signal_strength: int,
    signal_reasons: list[str] | None = None,
    backtest_run_id: str | None = None,
    min_sharpe: float = 1.0,
    min_win_rate: float = 0.30,
) -> PaperTradeDict | None:
    """Create a paper trade from a strategy signal."""
    idea_id = str(uuid.uuid4())
    sharpe, win_rate, max_drawdown = fetch_strategy_metrics(storage, strategy_id)
    if not validate_strategy_metrics(strategy_id, symbol, sharpe, win_rate, min_sharpe, min_win_rate):
        return None

    entry_price = fetch_entry_price(storage, symbol, idea_id)
    if entry_price is None:
        return None

    position = acquire_position(storage, strategy_id, symbol, entry_price)
    if position is None:
        return None
    shares, entry_amount = position

    stop_loss_price = calculate_stop_loss(storage, symbol, entry_price)
    if stop_loss_price is None:
        logger.warning(
            "paper_trade_blocked_no_atr", strategy_id=strategy_id, symbol=symbol,
            reason="insufficient_volatility_data_for_stop_loss",
        )
        return None

    insert_data = build_strategy_trade_dict(
        idea_id, strategy_id, symbol, entry_price, stop_loss_price,
        shares, entry_amount, sharpe, win_rate, max_drawdown, backtest_run_id,
    )
    try:
        insert_strategy_trade_records(
            storage, idea_id, strategy_id, symbol, signal_strength, signal_reasons, insert_data
        )
        logger.info(
            "paper_trade_created_from_strategy", strategy_id=strategy_id, symbol=symbol,
            entry_price=entry_price, signal_strength=signal_strength,
        )
        return insert_data
    except Exception as e:
        logger.error("paper_trade_create_error", strategy_id=strategy_id, symbol=symbol, error=str(e))
        return None
