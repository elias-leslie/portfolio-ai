"""Paper trading order creation and management from strategy signals."""

from __future__ import annotations

import uuid

from app.analytics._paper_trading_order_helpers import (
    acquire_position,
    build_strategy_trade_dict,
    fetch_strategy_metrics,
    insert_strategy_trade_records,
    validate_strategy_metrics,
)
from app.analytics.trade_calculations import calculate_stop_loss
from app.analytics.types import PaperTradeDict
from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import PortfolioStorage

logger = get_logger(__name__)


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
        insert_strategy_trade_records(storage, strategy_id, insert_data)
        logger.info(
            "paper_trade_created_from_strategy", strategy_id=strategy_id, symbol=symbol,
            entry_price=entry_price, signal_strength=signal_strength,
        )
        return insert_data
    except Exception as e:
        logger.error("paper_trade_create_error", strategy_id=strategy_id, symbol=symbol, error=str(e))
        return None
