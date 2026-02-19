"""Strategy signal and evolution API endpoint handlers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.logging_config import get_logger
from app.strategies.models import StrategyDefinition
from app.strategies.storage import get_strategy_storage
from app.tasks.strategy_signal_tasks import generate_signal_for_strategy
from app.utils.formatters import format_db_date, parse_float

logger = get_logger(__name__)


def _get_stored_signal(strategy_id: str) -> dict[str, Any] | None:
    """Return the most recent stored signal or None."""
    storage = get_strategy_storage()
    signals = storage.get_strategy_signals(strategy_id, limit=1)
    return signals[0] if signals else None


async def handle_get_strategy_signal(
    strategy_id: str, strategy: StrategyDefinition
) -> dict[str, Any]:
    """Get current trading signal, using stored or generating fresh."""
    try:
        signal = _get_stored_signal(strategy_id)
        if signal:
            return {
                "strategy_id": strategy_id,
                "symbol": strategy.symbol,
                "signal_type": signal["signal_type"],
                "signal_strength": signal["signal_strength"],
                "reasons": signal["reasons"],
                "market_data": signal["market_data"],
                "generated_at": format_db_date(signal["created_at"]),
                "source": "stored",
            }

        signal_data = generate_signal_for_strategy(strategy_id, strategy.symbol)
        if "error" in signal_data:
            raise HTTPException(status_code=400, detail=signal_data["error"])
        signal_data["source"] = "generated"
        return signal_data

    except Exception as e:
        logger.exception("Failed to get strategy signal", strategy_id=strategy_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get strategy signal: {e!s}") from e


async def handle_generate_strategy_signal(
    strategy_id: str, strategy: StrategyDefinition
) -> dict[str, Any]:
    """Force generate a new signal and store it."""
    try:
        signal_data = generate_signal_for_strategy(strategy_id, strategy.symbol)
        if "error" in signal_data:
            raise HTTPException(status_code=400, detail=signal_data["error"])

        storage = get_strategy_storage()
        signal_id = storage.store_signal(signal_data)
        signal_data["signal_id"] = signal_id
        signal_data["source"] = "generated"
        return signal_data

    except Exception as e:
        logger.exception(
            "Failed to generate strategy signal", strategy_id=strategy_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to generate strategy signal: {e!s}"
        ) from e


def _format_seed_info(seed_raw: dict[str, Any]) -> dict[str, Any]:
    """Format raw seed data for API response."""
    return {
        "id": seed_raw["id"],
        "thesis": seed_raw["thesis"],
        "confidence": seed_raw["confidence"],
        "created_at": format_db_date(seed_raw["created_at"]),
    }


def _format_backtests(backtests_raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format raw backtest records for API response."""
    return [
        {
            **bt,
            "start_date": format_db_date(bt["start_date"]),
            "end_date": format_db_date(bt["end_date"]),
            "created_at": format_db_date(bt["created_at"]),
        }
        for bt in backtests_raw
    ]


def _format_signals(signals_raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format raw signal records for API response."""
    return [
        {
            **sig,
            "signal_date": format_db_date(sig["signal_date"]),
            "created_at": format_db_date(sig["created_at"]),
        }
        for sig in signals_raw
    ]


async def handle_get_strategy_evolution(
    strategy_id: str, strategy: StrategyDefinition
) -> dict[str, Any]:
    """Get full evolution timeline for a strategy."""
    try:
        storage = get_strategy_storage()

        seed_raw = storage.get_seed_by_strategy_id(strategy_id)
        seed_info = _format_seed_info(seed_raw) if seed_raw else None

        backtests = _format_backtests(storage.get_backtest_runs(strategy_id, limit=5))
        signals = _format_signals(storage.get_strategy_signals(strategy_id, limit=10))
        trades = [
            {**trade, "entry_date": format_db_date(trade["entry_date"])}
            for trade in storage.get_symbol_trades(strategy.symbol, limit=10)
        ]

        return {
            "strategy_id": strategy_id,
            "name": strategy.name,
            "symbol": strategy.symbol,
            "status": strategy.status,
            "seed": seed_info,
            "backtests": backtests,
            "signals": signals,
            "trades": trades,
            "performance": {
                "expected_sharpe": parse_float(strategy.expected_sharpe),
                "live_sharpe": parse_float(strategy.live_sharpe_ratio),
                "live_win_rate": parse_float(strategy.live_win_rate),
                "total_trades": strategy.live_trades_count or 0,
            },
        }

    except Exception as e:
        logger.exception("Failed to get strategy evolution", strategy_id=strategy_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to get strategy evolution: {e!s}"
        ) from e
