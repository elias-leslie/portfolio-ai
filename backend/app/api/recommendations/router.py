"""API endpoints for trade recommendations."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from app.logging_config import get_logger
from app.middleware.cache import invalidate_endpoint_cache
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services.household_portfolio_totals import get_effective_portfolio_totals
from app.storage import get_storage
from app.storage.connection import get_connection_manager

from .logic import DEFAULT_PORTFOLIO_SIZE, DEFAULT_POSITION_PCT
from .models import RecommendationsResponse
from .queries import fetch_recommendations, fetch_recommended_symbols

logger = get_logger(__name__)

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("", response_model=RecommendationsResponse)
@router.get("/", response_model=RecommendationsResponse, include_in_schema=False)
async def get_recommendations(
    min_strength: int = Query(5, ge=0, le=10, description="Minimum signal strength"),
    limit: int = Query(20, ge=1, le=100, description="Maximum recommendations"),
    signal_type: Literal["BUY", "SELL", "all"] = Query("BUY", description="Filter by signal type"),
    portfolio_size: float | None = Query(
        None, ge=1000, description="Portfolio size override for sizing"
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
        resolved_portfolio_size = portfolio_size or get_effective_portfolio_totals(
            get_storage(), include_paper=False
        ).effective_invested_total_value
        if resolved_portfolio_size <= 0:
            resolved_portfolio_size = DEFAULT_PORTFOLIO_SIZE

        recommendations = fetch_recommendations(
            min_strength=min_strength,
            limit=limit,
            signal_type=signal_type,
            portfolio_size=resolved_portfolio_size,
            position_pct=position_pct,
            validation_filter=validation_filter,
        )

        # Calculate summary statistics
        buy_count = sum(1 for r in recommendations if r.signal_type == "BUY")
        sell_count = sum(1 for r in recommendations if r.signal_type == "SELL")
        total_position = sum(r.position_size_dollars for r in recommendations)

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
                "portfolio_size": resolved_portfolio_size,
                "position_pct": position_pct,
            },
        )

    except Exception as e:
        logger.exception("get_recommendations_failed", error=str(e))
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
        symbols = fetch_recommended_symbols(min_strength)
        return {
            "symbols": symbols,
            "count": len(symbols),
        }

    except Exception as e:
        logger.exception("get_recommended_symbols_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get symbols: {e!s}") from e


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
        logger.exception("track_in_portfolio_failed", symbol=symbol, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to track: {e!s}") from e
