"""Database queries for trade recommendations."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, cast

from app.logging_config import get_logger
from app.portfolio.price_fetcher import PriceDataFetcher
from app.storage import get_storage
from app.storage.connection import get_connection_manager

from .logic import (
    calculate_position_size,
    calculate_risk_reward,
    calculate_signal_status,
    calculate_stop_loss,
    calculate_target,
)
from .models import TradeRecommendation

logger = get_logger(__name__)


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
    conn_mgr = get_connection_manager()

    with conn_mgr.connection() as conn:
        # Build signal type filter
        signal_filter = ""
        if signal_type != "all":
            signal_filter = "AND ss.signal_type = %s"

        # Either/Or validation logic
        query = f"""
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

        params: list[Any] = [min_strength]
        if signal_type != "all":
            params.append(signal_type)
        params.append(limit)

        rows = conn.execute(query, params).fetchall()

    # Fetch real-time prices for all symbols
    symbols: list[str] = []
    for row in rows:
        sym = row[0]
        if isinstance(sym, str):
            symbols.append(sym)
    symbols = list(set(symbols))

    current_prices: dict[str, float] = {}

    if symbols:
        try:
            storage = get_storage()
            price_fetcher = PriceDataFetcher(storage)
            price_data = price_fetcher.fetch_price_data(symbols)
            current_prices = {sym: data.price for sym, data in price_data.items()}
        except Exception as e:
            logger.warning(f"Failed to fetch real-time prices: {e}")

    recommendations: list[TradeRecommendation] = []

    for row in rows:
        # Extract and validate row data
        symbol_raw = row[0]
        if not isinstance(symbol_raw, str):
            continue
        symbol: str = symbol_raw

        strategy_id = str(row[1])

        strategy_name_raw = row[2]
        if not isinstance(strategy_name_raw, str):
            continue
        strategy_name: str = strategy_name_raw

        strategy_type_raw = row[3]
        if not isinstance(strategy_type_raw, str):
            continue
        strategy_type: str = strategy_type_raw

        sig_type_raw = row[4]
        if not isinstance(sig_type_raw, str):
            continue
        sig_type: str = sig_type_raw

        strength_raw = row[5]
        if not isinstance(strength_raw, int):
            continue
        strength: int = strength_raw

        # Process reasons
        reasons_raw = row[6]
        reasons: list[str]
        if reasons_raw is None or not isinstance(reasons_raw, list):
            reasons = []
        else:
            reasons = [str(r) for r in reasons_raw if r is not None]

        # Process market data
        market_data_raw = row[7]
        market_data: dict[str, Any]
        if market_data_raw is None or not isinstance(market_data_raw, dict):
            market_data = {}
        else:
            market_data = market_data_raw

        signal_date_raw = row[8]
        created_at_raw = row[9]
        expected_sharpe = float(row[10]) if row[10] else None
        thesis_status_raw = row[11]
        cross_validation_score_raw = row[12]

        # Determine validation type
        has_thesis = (
            thesis_status_raw == "active"
            and cross_validation_score_raw is not None
            and float(cross_validation_score_raw) >= 0.7
        )
        has_backtest = expected_sharpe is not None and expected_sharpe >= 1.0

        if has_thesis and has_backtest:
            validation_type: Literal["thesis", "backtest", "both"] = "both"
        elif has_thesis:
            validation_type = "thesis"
        else:
            validation_type = "backtest"

        # Apply validation filter
        if validation_filter and validation_filter != "all":
            if validation_filter == "both":
                if validation_type != "both":
                    continue
            elif validation_type not in (validation_filter, "both"):
                continue

        # Get entry price from market data
        price_value = market_data.get("price", 0)
        entry_price = float(price_value) if price_value else 0.0
        if entry_price <= 0:
            continue

        # Get current real-time price
        current_price = current_prices.get(symbol, entry_price)

        # Calculate signal status
        price_change_pct, signal_status = calculate_signal_status(
            sig_type, entry_price, current_price
        )

        # Skip invalidated signals
        if signal_status == "invalidated":
            logger.info(
                f"Skipping {symbol}: signal invalidated (price change: {price_change_pct:.1f}%)"
            )
            continue

        # Calculate position sizing
        dollars, shares = calculate_position_size(current_price, portfolio_size, position_pct)
        stop_loss = calculate_stop_loss(current_price)
        target_price = calculate_target(current_price)
        risk_reward = calculate_risk_reward(current_price, stop_loss, target_price)

        # Handle date conversions
        signal_date_str: str = ""
        if isinstance(signal_date_raw, (date, datetime)):
            signal_date_str = signal_date_raw.isoformat()
        elif isinstance(signal_date_raw, str):
            signal_date_str = signal_date_raw

        generated_at_str: str | None = None
        if isinstance(created_at_raw, (date, datetime)):
            generated_at_str = created_at_raw.isoformat()
        elif isinstance(created_at_raw, str):
            generated_at_str = created_at_raw

        recommendations.append(
            TradeRecommendation(
                symbol=symbol,
                strategy_id=strategy_id,
                strategy_name=strategy_name,
                strategy_type=strategy_type,
                signal_strength=strength,
                signal_type=cast(Literal["BUY", "SELL", "HOLD"], sig_type),
                signal_reasons=reasons,
                entry_price=entry_price,
                current_price=current_price,
                price_change_pct=round(price_change_pct, 2),
                signal_status=signal_status,
                stop_loss=stop_loss,
                target_price=target_price,
                position_size_dollars=dollars,
                position_size_shares=shares,
                risk_reward_ratio=risk_reward,
                expected_sharpe=expected_sharpe,
                signal_date=signal_date_str,
                generated_at=generated_at_str,
                validation_type=validation_type,
            )
        )

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
