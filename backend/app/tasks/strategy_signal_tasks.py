"""Strategy signal generation tasks.

Generates daily trading signals for active strategies by evaluating
current market conditions against strategy parameters.

Schedule: Daily at 15:00 UTC (after US market close)
"""

from __future__ import annotations

from typing import Any

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.storage import get_strategy_storage
from app.watchlist.signal_classifier import classify_signal

from .strategy_signal_helpers import (
    build_signal_inputs,
    fetch_current_market_data,
    make_empty_signal_results,
    make_signal_result,
    process_paper_trade_signal,
    query_todays_buy_signals,
    record_signal_error,
    record_signal_result,
    store_signal,
)

logger = get_logger(__name__)


def generate_signal_for_strategy(strategy_id: str, symbol: str) -> dict[str, Any]:
    """Generate a trading signal for a specific strategy.

    Args:
        strategy_id: UUID of the strategy
        symbol: Stock symbol

    Returns:
        Dict with signal_type, strength, reasons, and market_data snapshot
    """
    conn_mgr = get_connection_manager()
    strategy_storage = get_strategy_storage()

    strategy = strategy_storage.get_strategy_by_id(strategy_id)
    if not strategy:
        return {"error": f"Strategy {strategy_id} not found"}
    if strategy.status != "active":
        return {"error": f"Strategy {strategy_id} is not active (status={strategy.status})"}

    with conn_mgr.connection() as conn:
        market_data = fetch_current_market_data(conn, symbol)
        if not market_data:
            return {"error": f"No market data available for {symbol}"}

        signal_inputs = build_signal_inputs(market_data)
        signal = classify_signal(signal_inputs)

        signal_type = signal.signal_type.value
        if signal_type == "AVOID":
            signal_type = "SELL"

        return make_signal_result(
            strategy_id=strategy_id,
            symbol=symbol,
            signal_type=signal_type,
            signal_strength=signal.strength.value,
            reasons=signal.reasons,
            market_data=market_data,
        )


def generate_daily_strategy_signals() -> dict[str, Any]:
    """Generate signals for all active strategies.

    Schedule: Daily at 15:00 UTC (after US market close)

    Returns:
        Summary dict with counts and any errors
    """
    logger.info("daily_strategy_signal_generation_started")

    conn_mgr = get_connection_manager()
    strategy_storage = get_strategy_storage()
    active_strategies = strategy_storage.list_strategies(status="active", limit=100)

    if not active_strategies:
        logger.info("no_active_strategies_found")
        return make_empty_signal_results(0)

    logger.info("evaluating_strategies", count=len(active_strategies))
    results = make_empty_signal_results(len(active_strategies))

    with conn_mgr.connection() as conn:
        for strategy in active_strategies:
            _process_one_strategy_signal(conn, strategy, results)
        conn.commit()

    logger.info(
        "Daily signal generation completed",
        strategies=results["strategies_evaluated"],
        signals=results["signals_generated"],
        buy=results["buy_signals"],
        sell=results["sell_signals"],
        errors=len(results["errors"]),
    )
    return results


def _process_one_strategy_signal(
    conn: Any, strategy: Any, results: dict[str, Any]
) -> None:
    """Generate and store the signal for a single strategy, updating results in place."""
    try:
        signal_data = generate_signal_for_strategy(strategy.id, strategy.symbol)

        if "error" in signal_data:
            record_signal_error(results, strategy.id, strategy.symbol, signal_data["error"])
            return

        signal_id = store_signal(conn, signal_data)
        if not signal_id:
            return

        record_signal_result(results, signal_data)
        logger.info(
            "Signal generated",
            strategy_id=strategy.id,
            symbol=strategy.symbol,
            signal_type=signal_data["signal_type"],
            strength=signal_data["signal_strength"],
        )

    except Exception as e:
        logger.exception(
            "Failed to generate signal",
            strategy_id=strategy.id,
            symbol=strategy.symbol,
            error=str(e),
        )
        record_signal_error(results, strategy.id, strategy.symbol, str(e))


def generate_signal_for_strategy_task(strategy_id: str, symbol: str) -> dict[str, Any]:
    """Task wrapper for single strategy signal generation.

    Can be called on-demand via API.
    """
    return generate_signal_for_strategy(strategy_id, symbol)


def auto_paper_trade_from_signals(min_signal_strength: int = 5) -> dict[str, Any]:
    """Create paper trades from BUY signals.

    Schedule: Daily at 21:45 UTC (after signals generated)

    Args:
        min_signal_strength: Minimum signal strength to trigger trade (0-10)

    Returns:
        Summary dict with counts and any errors
    """
    from app.storage import get_storage

    logger.info("auto_paper_trade_from_signals_started", min_strength=min_signal_strength)

    conn_mgr = get_connection_manager()
    storage = get_storage()

    results: dict[str, Any] = {
        "status": "completed",
        "signals_evaluated": 0,
        "trades_created": 0,
        "skipped_existing_position": 0,
        "skipped_low_strength": 0,
        "rejected_validation": 0,
        "errors": [],
    }

    with conn_mgr.connection() as conn:
        signals = query_todays_buy_signals(conn, min_signal_strength)
        results["signals_evaluated"] = len(signals)
        logger.info("buy_signals_found", count=len(signals))

        for signal in signals:
            process_paper_trade_signal(conn, storage, signal, results)

    logger.info(
        "Auto paper trading completed",
        signals=results["signals_evaluated"],
        trades=results["trades_created"],
        skipped=results["skipped_existing_position"],
        rejected_validation=results["rejected_validation"],
        errors=len(results["errors"]),
    )
    return results
