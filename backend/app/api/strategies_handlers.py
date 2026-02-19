"""Core strategy detail and status handler functions."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.logging_config import get_logger
from app.strategies.models import StrategyDefinition
from app.strategies.performance_utils import (
    calculate_performance_status,
    map_performance_flag_to_status,
)
from app.strategies.storage import get_strategy_storage
from app.utils.formatters import format_db_date, parse_float

from .strategies_models import StrategyDetail

logger = get_logger(__name__)


def _format_performance_history(perf_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format raw performance history rows for API response."""
    return [
        {
            "date": format_db_date(row["date"]),
            "trades_30d": row["trades_30d"],
            "win_rate_30d": parse_float(row["win_rate_30d"]),
            "sharpe_ratio_30d": parse_float(row["sharpe_ratio_30d"]),
            "max_drawdown_30d": parse_float(row["max_drawdown_30d"]),
            "status": row["status"],
        }
        for row in perf_data
    ]


def _normalize_backtest_metrics(
    backtest_metrics: dict[str, Any] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Ensure backtest_metrics is always a list."""
    if isinstance(backtest_metrics, dict):
        return [backtest_metrics]
    return backtest_metrics


async def handle_get_strategy(strategy_id: str, strategy: StrategyDefinition) -> StrategyDetail:
    """Build and return full strategy detail."""
    try:
        storage = get_strategy_storage()
        perf_data = storage.get_performance_history(strategy_id, limit=30)
        return StrategyDetail(
            id=strategy.id,
            name=strategy.name,
            symbol=strategy.symbol,
            strategy_type=strategy.strategy_type,
            parameters=strategy.parameters,
            research_summary=strategy.research_summary,
            generation_reasoning=strategy.generation_reasoning,
            backtest_metrics=_normalize_backtest_metrics(strategy.backtest_metrics),
            expected_sharpe=parse_float(strategy.expected_sharpe),
            expected_win_rate=parse_float(strategy.expected_win_rate),
            expected_max_drawdown=parse_float(strategy.expected_max_drawdown),
            live_trades_count=strategy.live_trades_count,
            live_win_rate=parse_float(strategy.live_win_rate),
            live_sharpe_ratio=parse_float(strategy.live_sharpe_ratio),
            status=strategy.status,
            version=strategy.version,
            created_at=format_db_date(strategy.created_at) or "",
            activation_date=format_db_date(strategy.activation_date),
            archive_date=format_db_date(strategy.archive_date),
            archive_reason=strategy.archive_reason,
            performance_history=_format_performance_history(perf_data),
        )
    except Exception as e:
        logger.exception("Failed to get strategy", strategy_id=strategy_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get strategy: {e!s}") from e


async def handle_update_strategy_status(
    strategy_id: str, strategy: StrategyDefinition, status: str, archive_reason: str | None
) -> dict[str, Any]:
    """Activate or archive a strategy and return updated summary."""
    try:
        storage = get_strategy_storage()
        if status == "active":
            storage.activate_strategy(strategy_id)
            logger.info("Strategy activated", strategy_id=strategy_id)
            message = f"Strategy {strategy.name} activated"
        else:
            reason = archive_reason or "Manual archival via API"
            storage.archive_strategy(strategy_id, reason)
            logger.info("Strategy archived", strategy_id=strategy_id, reason=reason)
            message = f"Strategy {strategy.name} archived"

        updated = storage.get_strategy_by_id(strategy_id)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated strategy")
        return {
            "strategy": {
                "id": updated.id,
                "name": updated.name,
                "symbol": updated.symbol,
                "status": updated.status,
                "version": updated.version,
            },
            "message": message,
        }
    except Exception as e:
        logger.exception("Failed to update strategy status", strategy_id=strategy_id, error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Failed to update strategy status: {e!s}"
        ) from e


def handle_get_strategy_performance(
    strategy_id: str, strategy: StrategyDefinition
) -> dict[str, Any]:
    """Return performance comparison dict for a strategy."""
    try:
        expected_sharpe = parse_float(strategy.expected_sharpe)
        actual_sharpe = parse_float(strategy.live_sharpe_ratio)
        performance_ratio, flag = calculate_performance_status(
            expected_sharpe, actual_sharpe, strategy.live_trades_count
        )
        return {
            "expected": {
                "sharpe": expected_sharpe or 0.0,
                "win_rate": parse_float(strategy.expected_win_rate),
                "max_drawdown": parse_float(strategy.expected_max_drawdown),
            },
            "actual_30d": {
                "sharpe": actual_sharpe or 0.0,
                "win_rate": parse_float(strategy.live_win_rate),
                "trades_count": strategy.live_trades_count,
            },
            "performance_ratio": performance_ratio or 0.0,
            "status": map_performance_flag_to_status(flag),
        }
    except Exception as e:
        logger.exception(
            "Failed to get strategy performance", strategy_id=strategy_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get strategy performance: {e!s}"
        ) from e
