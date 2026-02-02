"""Data converters for strategy storage."""

from __future__ import annotations

from typing import Any

from .models import StrategyDefinition


def row_to_strategy_definition(row: dict[str, Any]) -> StrategyDefinition:
    """Convert database row to StrategyDefinition.

    Args:
        row: Database row dict

    Returns:
        StrategyDefinition object
    """
    # Convert UUID to string, keep Decimal for Pydantic
    return StrategyDefinition(
        id=str(row["id"]),  # UUID → string
        name=row["name"],
        symbol=row["symbol"],
        strategy_type=row["strategy_type"],
        parameters=row["parameters"],
        research_summary=row["research_summary"],
        generation_reasoning=row["generation_reasoning"],
        backtest_metrics=row["backtest_metrics"],
        expected_sharpe=row["expected_sharpe"],
        expected_win_rate=row["expected_win_rate"],
        expected_max_drawdown=row["expected_max_drawdown"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        version=row["version"],
        status=row["status"],
        activation_date=row.get("activation_date"),
        archive_date=row.get("archive_date"),
        archive_reason=row.get("archive_reason"),
        live_trades_count=row.get("live_trades_count", 0),
        live_win_rate=row.get("live_win_rate"),
        live_sharpe_ratio=row.get("live_sharpe_ratio"),
        last_used_at=row.get("last_used_at"),
    )
