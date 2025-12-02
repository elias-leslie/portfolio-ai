"""API endpoints for trade recommendations.

Provides recommendations for top trades based on active strategy signals.
Used by /recommendations page to show actionable trades.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.logging_config import get_logger
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
    entry_price: float
    stop_loss: float
    target_price: float
    position_size_dollars: float
    position_size_shares: int
    risk_reward_ratio: float
    expected_sharpe: float | None
    signal_date: str
    generated_at: str | None


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


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/", response_model=RecommendationsResponse)
async def get_recommendations(
    min_strength: int = Query(5, ge=0, le=10, description="Minimum signal strength"),
    limit: int = Query(20, ge=1, le=100, description="Maximum recommendations"),
    signal_type: Literal["BUY", "SELL", "all"] = Query("BUY", description="Filter by signal type"),
    portfolio_size: float = Query(DEFAULT_PORTFOLIO_SIZE, ge=1000, description="Portfolio size for sizing"),
    position_pct: float = Query(DEFAULT_POSITION_PCT, ge=0.01, le=0.25, description="Position size %"),
) -> RecommendationsResponse:
    """Get top trade recommendations from active strategies.

    Returns BUY signals from today with signal_strength >= min_strength,
    sorted by strength descending. Includes position sizing calculations.

    Args:
        min_strength: Minimum signal strength (0-10)
        limit: Maximum number of recommendations
        signal_type: Filter for BUY, SELL, or all signals
        portfolio_size: Portfolio value for position sizing
        position_pct: Position size as percentage of portfolio

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
                    sd.expected_sharpe
                FROM strategy_signals ss
                JOIN strategy_definitions sd ON ss.strategy_id = sd.id
                WHERE sd.status = 'active'
                  AND ss.signal_strength >= %s
                  AND ss.signal_date >= CURRENT_DATE - INTERVAL '1 day'
                  {signal_filter}
                ORDER BY ss.signal_strength DESC, ss.created_at DESC
                LIMIT %s
            """

            params: list[Any] = [min_strength]
            if signal_type != "all":
                params.append(signal_type)
            params.append(limit)

            rows = conn.execute(query, params).fetchall()

        recommendations: list[TradeRecommendation] = []
        buy_count = 0
        sell_count = 0
        total_position = 0.0

        for row in rows:
            symbol = row[0]
            strategy_id = str(row[1])
            strategy_name = row[2]
            strategy_type = row[3]
            sig_type = row[4]
            strength = row[5]
            reasons = row[6] or []
            market_data = row[7] or {}
            signal_date = row[8]
            created_at = row[9]
            expected_sharpe = float(row[10]) if row[10] else None

            # Get entry price from market data
            entry_price = float(market_data.get("price", 0))
            if entry_price <= 0:
                continue  # Skip if no valid price

            # Calculate position sizing
            dollars, shares = _calculate_position_size(entry_price, portfolio_size, position_pct)
            stop_loss = _calculate_stop_loss(entry_price)
            target_price = _calculate_target(entry_price)
            risk_reward = _calculate_risk_reward(entry_price, stop_loss, target_price)

            recommendations.append(
                TradeRecommendation(
                    symbol=symbol,
                    strategy_id=strategy_id,
                    strategy_name=strategy_name,
                    strategy_type=strategy_type,
                    signal_strength=strength,
                    signal_type=sig_type,
                    signal_reasons=reasons,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    position_size_dollars=dollars,
                    position_size_shares=shares,
                    risk_reward_ratio=risk_reward,
                    expected_sharpe=expected_sharpe,
                    signal_date=signal_date.isoformat() if signal_date else "",
                    generated_at=created_at.isoformat() if created_at else None,
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
                ) if recommendations else 0,
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


@router.post("/track/{symbol}", response_model=dict[str, Any])
async def track_recommendation(
    symbol: str,
    strategy_id: str = Query(..., description="Strategy ID to link"),
    position_size: float = Query(DEFAULT_PORTFOLIO_SIZE * DEFAULT_POSITION_PCT, description="Position size in dollars"),
) -> dict[str, Any]:
    """Create a portfolio position from a recommendation.

    Links the position to the strategy for performance tracking.

    Args:
        symbol: Stock symbol
        strategy_id: Strategy UUID to link
        position_size: Position size in dollars

    Returns:
        Created position details
    """
    from app.portfolio.manager import PortfolioManager
    from app.storage import get_storage

    try:
        conn_mgr = get_connection_manager()
        storage = get_storage()

        with conn_mgr.connection() as conn:
            # Verify strategy exists and is active
            strategy = conn.execute(
                "SELECT name, symbol FROM strategy_definitions WHERE id = %s AND status = 'active'",
                (strategy_id,),
            ).fetchone()

            if not strategy:
                raise HTTPException(status_code=404, detail=f"Active strategy {strategy_id} not found")

            if strategy[1] != symbol:
                raise HTTPException(
                    status_code=400,
                    detail=f"Symbol mismatch: strategy is for {strategy[1]}, not {symbol}",
                )

            # Get current price
            price_row = conn.execute(
                "SELECT close FROM day_bars WHERE ticker = %s ORDER BY date DESC LIMIT 1",
                (symbol,),
            ).fetchone()

            if not price_row:
                raise HTTPException(status_code=404, detail=f"No price data for {symbol}")

            entry_price = float(price_row[0])
            shares = int(position_size / entry_price)

            # Get first account (or create paper account if none exist)
            account_row = conn.execute(
                "SELECT id FROM portfolio_accounts ORDER BY created_at LIMIT 1"
            ).fetchone()

            if not account_row:
                raise HTTPException(
                    status_code=400,
                    detail="No portfolio account exists. Create an account first.",
                )

            account_id = account_row[0]

        # Use PortfolioManager for proper position creation
        manager = PortfolioManager(storage)
        position = manager.add_position(
            account_id=account_id,
            symbol=symbol,
            shares=shares,
            cost_basis=entry_price,
            position_type="long",
            strategy_id=strategy_id,
        )

        return {
            "status": "created",
            "position": {
                "id": position.id,
                "symbol": position.symbol,
                "shares": position.shares,
                "cost_basis": position.cost_basis,
                "strategy_id": strategy_id,
                "strategy_name": strategy[0],
            },
            "message": f"Position created for {shares} shares of {symbol} at ${entry_price:.2f}",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to track recommendation", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to track: {e!s}") from e
