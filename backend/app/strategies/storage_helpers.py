"""Helper functions for strategy storage operations."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.utils.db_helpers import generate_uuid
from app.utils.json_helpers import json_serializer


def ensure_symbol_exists(conn: Any, symbol: str) -> None:
    """Ensure symbol exists in symbols table.

    Args:
        conn: Database connection
        symbol: Stock symbol to check/insert
    """
    conn.execute(
        """
        INSERT INTO symbols (symbol, security_type, created_at)
        VALUES (%s, 'equity', NOW())
        ON CONFLICT (symbol) DO NOTHING
        """,
        (symbol,),
    )


def generate_strategy_name(symbol: str, strategy_type: str) -> str:
    """Generate strategy name.

    Args:
        symbol: Stock symbol
        strategy_type: Strategy type

    Returns:
        Strategy name (e.g., "AAPL_Momentum_2024Q4")
    """
    # Get current quarter
    now = datetime.now(UTC)
    quarter = (now.month - 1) // 3 + 1
    return f"{symbol}_{strategy_type.capitalize()}_{now.year}Q{quarter}"


def get_next_version(conn_manager: Any, symbol: str, name: str) -> int:
    """Get next version number for strategy.

    Args:
        conn_manager: Database connection manager
        symbol: Stock symbol
        name: Strategy name

    Returns:
        Next version number (1 if no existing versions)
    """
    with conn_manager.connection() as conn:
        rows = conn.execute(
            """
            SELECT MAX(version) as max_version
            FROM strategy_definitions
            WHERE symbol = %s AND name = %s
            """,
            (symbol, name),
        ).fetchall()

    if not rows or rows[0][0] is None:
        return 1

    return int(rows[0][0]) + 1


def serialize_strategy_fields(
    parameters: dict[str, Any],
    research_summary: dict[str, Any],
    backtest_metrics: list[dict[str, Any]],
) -> tuple[str, str, str]:
    """Serialize JSONB fields for storage.

    Args:
        parameters: Strategy parameters dict
        research_summary: Research insights dict
        backtest_metrics: Backtest results list

    Returns:
        Tuple of (parameters_json, research_summary_json, backtest_metrics_json)
    """
    parameters_json = json.dumps(parameters, default=json_serializer)
    research_summary_json = json.dumps(research_summary, default=json_serializer)
    backtest_metrics_json = json.dumps(backtest_metrics, default=json_serializer)
    return parameters_json, research_summary_json, backtest_metrics_json


def generate_strategy_id() -> str:
    """Generate a new strategy UUID.

    Returns:
        UUID string
    """
    return generate_uuid()
