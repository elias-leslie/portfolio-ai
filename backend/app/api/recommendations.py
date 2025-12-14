"""API endpoints for trade recommendations.

Provides recommendations for top trades based on active strategy signals.
Used by /recommendations page to show actionable trades.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.logging_config import get_logger
from app.middleware.cache import invalidate_endpoint_cache
from app.storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


# ============================================================================
# Constants
# ============================================================================

# Default portfolio size for position sizing
DEFAULT_PORTFOLIO_SIZE = 100_000.0

# Default position size as percentage of portfolio
DEFAULT_POSITION_PCT = 0.05  # 5%

# Default stop loss percentage
DEFAULT_STOP_LOSS_PCT = 0.08  # 8%

# Default target gain percentage
DEFAULT_TARGET_GAIN_PCT = 0.15  # 15%


# ============================================================================
# Response Models
# ============================================================================


class TradeRecommendation(BaseModel):
    """Single trade recommendation."""

    symbol: str
    strategy_id: str
    strategy_name: str
    strategy_type: str
    signal_strength: int = Field(ge=0, le=10)
    signal_type: Literal["BUY", "SELL", "HOLD"]
    signal_reasons: list[str]
    entry_price: float  # Price when signal was generated
    current_price: float  # Real-time current price
    price_change_pct: float  # % change since signal
    signal_status: Literal["valid", "better_entry", "caution", "invalidated"]
    stop_loss: float
    target_price: float
    position_size_dollars: float
    position_size_shares: int
    risk_reward_ratio: float
    expected_sharpe: float | None
    signal_date: str
    generated_at: str | None
    validation_type: Literal["thesis", "backtest", "both"] = Field(
        ..., description="Type of validation (thesis, backtest, or both)"
    )


class RecommendationsResponse(BaseModel):
    """Response containing trade recommendations."""

    recommendations: list[TradeRecommendation]
    total: int
    summary: dict[str, Any]


# ============================================================================
# Helper Functions
# ============================================================================


def _calculate_position_size(
    entry_price: float,
    portfolio_size: float = DEFAULT_PORTFOLIO_SIZE,
    position_pct: float = DEFAULT_POSITION_PCT,
) -> tuple[float, int]:
    """Calculate position size in dollars and shares.

    Args:
        entry_price: Current price per share
        portfolio_size: Total portfolio value
        position_pct: Percentage of portfolio per position

    Returns:
        Tuple of (dollars, shares)
    """
    dollars = portfolio_size * position_pct
    shares = int(dollars / entry_price) if entry_price > 0 else 0
    return dollars, shares


def _calculate_stop_loss(entry_price: float, pct: float = DEFAULT_STOP_LOSS_PCT) -> float:
    """Calculate stop loss price."""
    return round(entry_price * (1 - pct), 2)


def _calculate_target(entry_price: float, pct: float = DEFAULT_TARGET_GAIN_PCT) -> float:
    """Calculate target price."""
    return round(entry_price * (1 + pct), 2)


def _calculate_risk_reward(entry: float, stop: float, target: float) -> float:
    """Calculate risk/reward ratio."""
    risk = entry - stop
    reward = target - entry
    if risk <= 0:
        return 0.0
    return round(reward / risk, 2)


def _calculate_signal_status(
    signal_type: str, entry_price: float, current_price: float
) -> tuple[float, Literal["valid", "better_entry", "caution", "invalidated"]]:
    """Calculate signal status based on price movement since signal.

    For BUY signals:
    - Price dropped 0-5%: "better_entry" (more attractive)
    - Price within ±5%: "valid"
    - Price rose >5%: "caution" (may have missed entry)
    - Price dropped >15% or rose >15%: "invalidated" (something changed)

    For SELL signals: Opposite logic.

    Returns:
        Tuple of (price_change_pct, status)
    """
    if entry_price <= 0:
        return 0.0, "valid"

    price_change_pct = ((current_price - entry_price) / entry_price) * 100

    if signal_type == "BUY":
        if price_change_pct < -15 or price_change_pct > 15:
            return price_change_pct, "invalidated"
        if price_change_pct < -5:
            return price_change_pct, "better_entry"  # Significant drop = better buy
        if price_change_pct > 5:
            return price_change_pct, "caution"  # Rose too much, may have missed
        if price_change_pct < 0:
            return price_change_pct, "better_entry"  # Small drop = slightly better
        return price_change_pct, "valid"
    if price_change_pct < -15 or price_change_pct > 15:
        return price_change_pct, "invalidated"
    if price_change_pct > 5:
        return price_change_pct, "better_entry"  # Rose = better sell price
    if price_change_pct < -5:
        return price_change_pct, "caution"  # Dropped, may have missed
    if price_change_pct > 0:
        return price_change_pct, "better_entry"
    return price_change_pct, "valid"


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/", response_model=RecommendationsResponse)
async def get_recommendations(
    min_strength: int = Query(5, ge=0, le=10, description="Minimum signal strength"),
    limit: int = Query(20, ge=1, le=100, description="Maximum recommendations"),
    signal_type: Literal["BUY", "SELL", "all"] = Query("BUY", description="Filter by signal type"),
    portfolio_size: float = Query(
        DEFAULT_PORTFOLIO_SIZE, ge=1000, description="Portfolio size for sizing"
    ),
    position_pct: float = Query(
        DEFAULT_POSITION_PCT, ge=0.01, le=0.25, description="Position size %"
    ),
    validation_filter: Literal["thesis", "backtest", "both", "all"] | None = Query(
        None, description="Filter by validation type"
    ),
) -> RecommendationsResponse:
    """Get top trade recommendations from active strategies.

    Returns BUY signals from today with signal_strength >= min_strength,
    sorted by strength descending. Includes position sizing calculations.

    Only includes symbols validated through EITHER:
    - Path A (Event-Driven): Active thesis with cross_validation_score >= 0.7
    - Path B (Technical): Active strategy with expected_sharpe >= 1.0

    Args:
        min_strength: Minimum signal strength (0-10)
        limit: Maximum number of recommendations
        signal_type: Filter for BUY, SELL, or all signals
        portfolio_size: Portfolio value for position sizing
        position_pct: Position size as percentage of portfolio
        validation_filter: Filter by validation type (thesis, backtest, both, all)

    Returns:
        List of trade recommendations with full details
    """
    try:
        conn_mgr = get_connection_manager()

        with conn_mgr.connection() as conn:
            # Build signal type filter
            signal_filter = ""
            if signal_type != "all":
                signal_filter = "AND ss.signal_type = %s"

            # Either/Or validation logic:
            # Include if:
            #   - Path A: thesis.status = 'active' AND thesis.cross_validation_score >= 0.7
            #   - Path B: sd.expected_sharpe >= 1.0
            # Exclude if NEITHER condition is met
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
        from app.portfolio.price_fetcher import PriceDataFetcher
        from app.storage import get_storage

        # Extract symbols and ensure they're all strings
        symbols: list[str] = []
        for row in rows:
            sym = row[0]
            if isinstance(sym, str):
                symbols.append(sym)
        symbols = list(set(symbols))  # Deduplicate

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
        buy_count = 0
        sell_count = 0
        total_position = 0.0

        for row in rows:
            # Extract and validate row data with proper types
            symbol_raw = row[0]
            if not isinstance(symbol_raw, str):
                continue  # Skip invalid symbols
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

            # Type annotate reasons and market_data with proper validation
            reasons_raw = row[6]
            reasons: list[str]
            if reasons_raw is None or not isinstance(reasons_raw, list):
                reasons = []
            else:
                # Ensure all items are strings
                reasons = [str(r) for r in reasons_raw if r is not None]

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

            # Determine validation type based on what criteria are met
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
            else:  # has_backtest (must be true due to WHERE clause)
                validation_type = "backtest"

            # Apply validation filter if specified
            # "all" or None = no filtering
            # "thesis" = include thesis OR both (inclusive)
            # "backtest" = include backtest OR both (inclusive)
            # "both" = only include both (highest confidence filter)
            if validation_filter and validation_filter != "all":
                if validation_filter == "both":
                    # Only show items with BOTH validations
                    if validation_type != "both":
                        continue
                elif validation_type not in (validation_filter, "both"):
                    # Inclusive: show matching type OR "both" (which includes both types)
                    continue

            # Get entry price from market data (when signal was generated)
            # market_data is guaranteed to be dict at this point
            price_value = market_data.get("price", 0)
            entry_price = float(price_value) if price_value else 0.0
            if entry_price <= 0:
                continue  # Skip if no valid price

            # Get current real-time price
            current_price = current_prices.get(symbol, entry_price)

            # Calculate signal status based on price movement
            price_change_pct, signal_status = _calculate_signal_status(
                sig_type, entry_price, current_price
            )

            # Skip invalidated signals
            if signal_status == "invalidated":
                logger.info(
                    f"Skipping {symbol}: signal invalidated (price change: {price_change_pct:.1f}%)"
                )
                continue

            # Calculate position sizing based on CURRENT price
            dollars, shares = _calculate_position_size(current_price, portfolio_size, position_pct)
            stop_loss = _calculate_stop_loss(current_price)
            target_price = _calculate_target(current_price)
            risk_reward = _calculate_risk_reward(current_price, stop_loss, target_price)

            # Handle signal_date conversion
            signal_date_str: str = ""
            if isinstance(signal_date_raw, (date, datetime)):
                signal_date_str = signal_date_raw.isoformat()
            elif isinstance(signal_date_raw, str):
                signal_date_str = signal_date_raw

            # Handle created_at conversion
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

            # Update counts
            if sig_type == "BUY":
                buy_count += 1
            elif sig_type == "SELL":
                sell_count += 1
            total_position += dollars

        return RecommendationsResponse(
            recommendations=recommendations,
            total=len(recommendations),
            summary={
                "buy_signals": buy_count,
                "sell_signals": sell_count,
                "hold_signals": len(recommendations) - buy_count - sell_count,
                "total_position_size": round(total_position, 2),
                "avg_signal_strength": round(
                    sum(r.signal_strength for r in recommendations) / len(recommendations), 1
                )
                if recommendations
                else 0,
                "portfolio_size": portfolio_size,
                "position_pct": position_pct,
            },
        )

    except Exception as e:
        logger.exception("Failed to get recommendations", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get recommendations: {e!s}") from e


@router.get("/symbols", response_model=dict[str, Any])
async def get_recommended_symbols(
    min_strength: int = Query(5, ge=0, le=10, description="Minimum signal strength"),
) -> dict[str, Any]:
    """Get list of symbols with active BUY recommendations.

    Lighter endpoint for quick lookups.

    Returns:
        Dict with symbols list and count
    """
    try:
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

        symbols = [{"symbol": r[0], "strength": r[1]} for r in rows]

        return {
            "symbols": symbols,
            "count": len(symbols),
        }

    except Exception as e:
        logger.exception("Failed to get recommended symbols", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get symbols: {e!s}") from e


@router.post("/paper-trade/{symbol}", response_model=dict[str, Any])
async def paper_trade_recommendation(
    symbol: str,
    strategy_id: str = Query(..., description="Strategy ID to link"),
) -> dict[str, Any]:
    """Create a paper trade from a recommendation.

    Uses the proper paper trading flow with strategy linkage and backtest metrics.
    Creates records in agent_ideas and idea_outcomes that appear on /trading page.

    Args:
        symbol: Stock symbol
        strategy_id: Strategy UUID to link

    Returns:
        Paper trade details
    """
    from app.analytics.paper_trading_orders import create_paper_trade_from_strategy_signal
    from app.storage import get_storage

    try:
        conn_mgr = get_connection_manager()
        storage = get_storage()

        with conn_mgr.connection() as conn:
            # Get strategy details and signal strength
            strategy = conn.execute(
                """SELECT sd.name, ss.signal_strength
                   FROM strategy_definitions sd
                   LEFT JOIN strategy_signals ss ON sd.id = ss.strategy_id
                     AND ss.symbol = %s
                     AND ss.signal_date >= CURRENT_DATE - INTERVAL '1 day'
                   WHERE sd.id = %s AND sd.status = 'active'
                   ORDER BY ss.signal_date DESC NULLS LAST
                   LIMIT 1""",
                (symbol, strategy_id),
            ).fetchone()

            if not strategy:
                raise HTTPException(
                    status_code=404, detail=f"Active strategy {strategy_id} not found"
                )

            signal_strength = (
                int(strategy[1]) if strategy[1] else 7
            )  # Default to 7 if no recent signal

        # Use the proper paper trading function with backtest metrics
        trade = create_paper_trade_from_strategy_signal(
            storage=storage,
            strategy_id=strategy_id,
            symbol=symbol,
            signal_strength=signal_strength,
            signal_reasons=["Manual paper trade from recommendations page"],
        )

        if not trade:
            raise HTTPException(
                status_code=400,
                detail="Failed to create paper trade (insufficient data or cash)",
            )

        return {
            "status": "created",
            "trade": {
                "idea_id": trade["idea_id"],
                "symbol": symbol,
                "entry_price": trade["entry_price"],
                "target_price": trade.get("target_price"),
                "stop_loss_price": trade.get("stop_loss_price"),
                "strategy_name": strategy[0],
                "backtest_sharpe": trade.get("backtest_sharpe"),
                "backtest_win_rate": trade.get("backtest_win_rate"),
            },
            "message": f"Paper trade: bought {symbol} at ${trade['entry_price']:.2f}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to create paper trade", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to paper trade: {e!s}") from e


@router.post("/track/{symbol}", response_model=dict[str, Any])
async def track_in_portfolio(
    symbol: str,
    strategy_id: str = Query(..., description="Strategy ID to link"),
    account_id: str = Query(..., description="Portfolio account ID"),
    shares: int = Query(..., ge=1, description="Number of shares"),
) -> dict[str, Any]:
    """Add recommendation to real portfolio.

    Creates a position in the specified portfolio account.

    Args:
        symbol: Stock symbol
        strategy_id: Strategy UUID to link
        account_id: Portfolio account to add to
        shares: Number of shares to track

    Returns:
        Created position details
    """
    from app.portfolio.manager import PortfolioManager
    from app.storage import get_storage

    try:
        conn_mgr = get_connection_manager()
        storage = get_storage()

        with conn_mgr.connection() as conn:
            # Verify strategy
            strategy = conn.execute(
                "SELECT name, symbol FROM strategy_definitions WHERE id = %s",
                (strategy_id,),
            ).fetchone()

            if not strategy:
                raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

            # Verify account exists and is NOT paper
            account = conn.execute(
                "SELECT id, name, account_type FROM portfolio_accounts WHERE id = %s",
                (account_id,),
            ).fetchone()

            if not account:
                raise HTTPException(status_code=404, detail=f"Account {account_id} not found")

            if account[2] == "paper":
                raise HTTPException(
                    status_code=400,
                    detail="Use 'Paper Trade' for paper accounts, not 'Track in Portfolio'",
                )

        # Get real-time price for cost basis
        from app.portfolio.price_fetcher import PriceDataFetcher

        price_fetcher = PriceDataFetcher(storage)
        try:
            price_data = price_fetcher.fetch_price_data([symbol])
            entry_price = price_data[symbol].price
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"No price data for {symbol}: {e}") from e

        # Create position
        manager = PortfolioManager(storage)
        position = manager.add_position(
            account_id=account_id,
            symbol=symbol,
            shares=shares,
            cost_basis=entry_price,
            position_type="long",
            strategy_id=strategy_id,
        )

        # Invalidate portfolio cache so new position shows immediately
        invalidate_endpoint_cache("/api/portfolio/", method="GET")
        invalidate_endpoint_cache("/api/portfolio/analytics", method="GET")

        return {
            "status": "created",
            "position": {
                "id": position.id,
                "symbol": position.symbol,
                "shares": position.shares,
                "cost_basis": position.cost_basis,
                "account_name": account[1],
                "strategy_name": strategy[0],
            },
            "message": f"Added {shares} shares of {symbol} to {account[1]} at ${entry_price:.2f}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to track in portfolio", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to track: {e!s}") from e
