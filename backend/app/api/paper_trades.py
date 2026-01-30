"""Paper Trading API endpoints.

This module provides REST API endpoints for paper trading operations:
- List all paper trades (open + closed)
- Get single trade details with AI reasoning
- Close positions manually
- Get summary statistics
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.logging_config import get_logger
from app.models.paper_trades import (
    CloseTradeRequest,
    CloseTradeResponse,
    PaperTradeResponse,
    PaperTradesListResponse,
    PaperTradeSummaryResponse,
    ResetAccountRequest,
    ResetAccountResponse,
    UpdateSettingsRequest,
    UpdateSettingsResponse,
)
from app.services import paper_trades_service

logger = get_logger(__name__)

router = APIRouter(prefix="/api/paper-trades", tags=["paper-trades"])


@router.get("", response_model=PaperTradesListResponse)
async def list_paper_trades(
    status: Literal["open", "closed", "all"] = Query("all", description="Filter by trade status"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of trades to return"),
    offset: int = Query(0, ge=0, description="Number of trades to skip"),
) -> PaperTradesListResponse:
    """List all paper trades with optional status filter.

    Query Parameters:
        status: Filter by 'open', 'closed', or 'all' (default: all)
        limit: Maximum number of trades to return (default: 100, max: 500)
        offset: Number of trades to skip for pagination (default: 0)

    Returns:
        List of paper trades with full details including AI reasoning
    """
    try:
        return paper_trades_service.list_trades(status, limit, offset)
    except Exception as e:
        logger.error("failed_to_list_paper_trades", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch paper trades: {e}",
        ) from e


@router.get("/summary", response_model=PaperTradeSummaryResponse)
async def get_paper_trade_summary() -> PaperTradeSummaryResponse:
    """Get summary statistics for paper trading performance.

    Returns:
        Summary with win rate, average return, total P&L, etc.
    """
    try:
        return paper_trades_service.get_trade_summary()
    except Exception as e:
        logger.error("failed_to_get_summary", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch summary: {e}",
        ) from e


@router.get("/{trade_id}", response_model=PaperTradeResponse)
async def get_paper_trade(trade_id: str) -> PaperTradeResponse:
    """Get detailed information for a single paper trade.

    Path Parameters:
        trade_id: The idea_id of the paper trade

    Returns:
        Complete trade details including AI reasoning and backtest metrics
    """
    try:
        trade = paper_trades_service.get_single_trade(trade_id)
        if not trade:
            raise HTTPException(
                status_code=404,
                detail=f"Paper trade {trade_id} not found",
            )
        return trade
    except HTTPException:
        raise
    except Exception as e:
        logger.error("failed_to_get_paper_trade", trade_id=trade_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch paper trade: {e}",
        ) from e


@router.post("/{trade_id}/close", response_model=CloseTradeResponse)
async def close_paper_trade(
    trade_id: str,
    request: CloseTradeRequest,
) -> CloseTradeResponse:
    """Manually close an open paper trade.

    Path Parameters:
        trade_id: The idea_id of the paper trade to close

    Request Body:
        exit_price: Optional exit price (uses current_price if not provided)
        exit_reason: Reason for closing (default: "manual")

    Returns:
        Result of close operation with realized P&L
    """
    try:
        return paper_trades_service.close_trade(
            trade_id,
            request.exit_price,
            request.exit_reason,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400 if "not found" not in str(e) else 404,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("failed_to_close_trade", trade_id=trade_id, error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to close trade: {e}",
        ) from e


@router.post("/account/reset", response_model=ResetAccountResponse)
async def reset_paper_account(request: ResetAccountRequest) -> ResetAccountResponse:
    """Reset the paper trading account to starting balance.

    This will:
    1. Optionally close all open trades (at current prices)
    2. Reset cash balance to initial_cash (or new_starting_balance if provided)
    3. Optionally update the starting balance

    Request Body:
        new_starting_balance: Optional new starting balance
        close_open_trades: Whether to close open trades (default: True)

    Returns:
        Result of reset operation
    """
    try:
        return paper_trades_service.reset_account(
            request.new_starting_balance,
            request.close_open_trades,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404 if "not found" in str(e) else 500,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("failed_to_reset_account", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reset account: {e}",
        ) from e


@router.patch("/account/settings", response_model=UpdateSettingsResponse)
async def update_paper_settings(request: UpdateSettingsRequest) -> UpdateSettingsResponse:
    """Update paper trading account settings.

    Currently supports updating the starting balance without resetting.

    Request Body:
        starting_balance: New starting balance amount

    Returns:
        Updated settings
    """
    try:
        return paper_trades_service.update_settings(request.starting_balance)
    except ValueError as e:
        raise HTTPException(
            status_code=404 if "not found" in str(e) else 500,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("failed_to_update_settings", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update settings: {e}",
        ) from e
