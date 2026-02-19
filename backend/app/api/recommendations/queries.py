"""Database queries for trade recommendations."""

from __future__ import annotations

from typing import Any, Literal

from app.storage.connection import get_connection_manager

from ._price_fetch import fetch_current_prices
from ._row_parser import parse_row
from .models import TradeRecommendation


def _build_recommendations_query(signal_type: Literal["BUY", "SELL", "all"]) -> str:
    """Build the SQL query string for fetching recommendations."""
    signal_filter = "AND ss.signal_type = %s" if signal_type != "all" else ""
    return f"""
        SELECT
            ss.symbol,
            ss.strategy_id,
            sd.name as strategy_name,
            sd.strategy_type,
            ss.signal_type,
            ss.signal_strength,
            ss.reasons,
            ss.market_data,
            ss.signal_date,
            ss.created_at,
            sd.expected_sharpe,
            wt.status as thesis_status,
            wt.cross_validation_score
        FROM strategy_signals ss
        JOIN strategy_definitions sd ON ss.strategy_id = sd.id
        LEFT JOIN watchlist_thesis wt ON ss.symbol = wt.symbol
            AND wt.status = 'active'
        WHERE sd.status = 'active'
          AND ss.signal_strength >= %s
          AND ss.signal_date >= CURRENT_DATE - INTERVAL '1 day'
          {signal_filter}
          AND (
            -- Path A: Event-Driven (thesis-based)
            (wt.status = 'active' AND wt.cross_validation_score >= 0.7)
            OR
            -- Path B: Technical (backtest-based)
            (sd.expected_sharpe >= 1.0)
          )
        ORDER BY ss.signal_strength DESC, ss.created_at DESC
        LIMIT %s
    """


def _fetch_rows(
    signal_type: Literal["BUY", "SELL", "all"],
    min_strength: int,
    limit: int,
) -> list[Any]:
    """Execute the recommendations query and return raw rows."""
    conn_mgr = get_connection_manager()
    query = _build_recommendations_query(signal_type)

    params: list[Any] = [min_strength]
    if signal_type != "all":
        params.append(signal_type)
    params.append(limit)

    with conn_mgr.connection() as conn:
        return conn.execute(query, params).fetchall()


def fetch_recommendations(
    min_strength: int,
    limit: int,
    signal_type: Literal["BUY", "SELL", "all"],
    portfolio_size: float,
    position_pct: float,
    validation_filter: Literal["thesis", "backtest", "both", "all"] | None,
) -> list[TradeRecommendation]:
    """Fetch and process trade recommendations from database.

    Args:
        min_strength: Minimum signal strength (0-10)
        limit: Maximum number of recommendations
        signal_type: Filter for BUY, SELL, or all signals
        portfolio_size: Portfolio value for position sizing
        position_pct: Position size as percentage of portfolio
        validation_filter: Filter by validation type

    Returns:
        List of TradeRecommendation objects
    """
    rows = _fetch_rows(signal_type, min_strength, limit)

    symbols = list({row[0] for row in rows if isinstance(row[0], str)})
    current_prices = fetch_current_prices(symbols)

    recommendations: list[TradeRecommendation] = []
    for row in rows:
        rec = parse_row(row, current_prices, portfolio_size, position_pct, validation_filter)
        if rec is not None:
            recommendations.append(rec)

    return recommendations


def fetch_recommended_symbols(min_strength: int) -> list[dict[str, Any]]:
    """Fetch list of symbols with active BUY recommendations.

    Args:
        min_strength: Minimum signal strength

    Returns:
        List of dicts with symbol and strength
    """
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ss.symbol, ss.signal_strength
            FROM strategy_signals ss
            JOIN strategy_definitions sd ON ss.strategy_id = sd.id
            WHERE sd.status = 'active'
              AND ss.signal_type = 'BUY'
              AND ss.signal_strength >= %s
              AND ss.signal_date >= CURRENT_DATE - INTERVAL '1 day'
            ORDER BY ss.signal_strength DESC
            """,
            (min_strength,),
        ).fetchall()

    return [{"symbol": r[0], "strength": r[1]} for r in rows]
