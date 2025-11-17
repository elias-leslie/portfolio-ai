"""Paper trading API endpoints.

This module provides REST API endpoints for paper trading operations:
- Manual trade creation
- Transaction history
- Trade management
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal, cast

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.analytics.order_executor import OrderExecutor
from app.analytics.transaction_logger import TransactionLogger
from app.logging_config import get_logger
from app.storage import get_storage

logger = get_logger(__name__)

router = APIRouter(prefix="/api/paper-trading", tags=["paper-trading"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateTradeRequest(BaseModel):
    """Request model for creating a manual paper trade."""

    ticker: str = Field(..., description="Stock ticker symbol")
    action: str = Field(..., description="Trade action: 'buy' or 'sell'")
    thesis: str = Field(..., description="Investment thesis for this trade")
    target_price: float | None = Field(None, description="Optional target exit price")
    stop_loss_pct: float | None = Field(None, description="Optional stop loss percentage")


class CreateTradeResponse(BaseModel):
    """Response model for trade creation."""

    status: str
    trade_id: str | None = None
    ticker: str | None = None
    action: str | None = None
    shares: int | None = None
    entry_price: float | None = None
    entry_amount: float | None = None
    target_price: float | None = None
    stop_loss_price: float | None = None
    cash_remaining: float | None = None
    message: str
    error: str | None = None


class TransactionResponse(BaseModel):
    """Response model for transaction records."""

    id: str
    trade_id: str
    transaction_type: str
    ticker: str
    shares: int
    price: float
    amount: float
    cash_before: float
    cash_after: float
    timestamp: str
    notes: str | None


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/trades", response_model=CreateTradeResponse)
async def create_paper_trade(request: CreateTradeRequest) -> CreateTradeResponse:
    """Create a manual paper trade.

    This endpoint allows users to create paper trades manually through the UI.
    It validates cash availability, calculates position sizing, and executes
    the trade using the same flow as agent-created trades.

    Args:
        request: Trade creation request with ticker, action, thesis, and optional
                target/stop loss

    Returns:
        Trade creation response with execution details

    Raises:
        HTTPException: If trade creation fails
    """
    storage = get_storage()
    order_executor = OrderExecutor(storage)

    # Validate inputs
    ticker = request.ticker.upper()
    action = request.action.lower()

    if action not in ["buy", "sell"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action '{action}' (must be 'buy' or 'sell')",
        )

    # Calculate max affordable shares (5% of account)
    account_id = "paper_trading"
    max_shares = order_executor.calculate_max_shares(ticker, account_id, max_position_pct=0.05)

    if max_shares == 0:
        raise HTTPException(
            status_code=400,
            detail="Insufficient cash or failed to calculate position size",
        )

    # Create agent idea record (agent_run_id = "manual" for manual trades)
    idea_id = str(uuid.uuid4())

    storage.insert_dict(
        "agent_ideas",
        {
            "id": idea_id,
            "agent_run_id": "manual",  # Special ID for manual trades
            "idea_type": action,
            "title": f"{action.capitalize()} {ticker}",
            "thesis": request.thesis,
            "action": f"{action.capitalize()} {max_shares} shares of {ticker}",
            "confidence_score": 70,  # Default confidence for manual trades
            "risk_level": "medium",  # Default risk
            "status": "pending",
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        },
    )

    # Execute market order
    # Cast action to Literal type for type safety
    action_typed = cast(Literal["buy", "sell"], action)

    order_result = order_executor.execute_market_order(
        ticker=ticker,
        action=action_typed,
        shares=max_shares,
        account_id=account_id,
        trade_id=idea_id,
        notes=f"Manual paper trade: {request.thesis[:100]}",
    )

    if not order_result.get("filled"):
        error_msg = order_result.get("error", "Unknown error")
        logger.error(f"Failed to execute manual paper trade for {ticker}: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    # Calculate stop loss price if provided
    entry_price = order_result["price"]
    stop_loss_price = None

    if request.stop_loss_pct is not None:
        if action == "buy":
            stop_loss_price = entry_price * (1 - request.stop_loss_pct / 100)
        else:  # sell (short)
            stop_loss_price = entry_price * (1 + request.stop_loss_pct / 100)

    # Create idea_outcomes record
    storage.insert_dict(
        "idea_outcomes",
        {
            "idea_id": idea_id,
            "agent_run_id": "manual",
            "ticker": ticker,
            "idea_type": action,
            "entry_price": entry_price,
            "entry_date": datetime.now(UTC).date(),
            "target_price": request.target_price,
            "stop_loss_price": stop_loss_price,
            "current_price": entry_price,
            "current_return_pct": 0.0,
            "status": "open",
            "shares": max_shares,
            "entry_amount": order_result["amount"],
            "created_at": datetime.now(UTC),
            "updated_at": datetime.now(UTC),
        },
    )

    logger.info(
        f"Manual paper trade created: {action.upper()} {max_shares} {ticker} "
        f"@ ${entry_price:.2f} (${order_result['amount']:.2f})"
    )

    return CreateTradeResponse(
        status="created",
        trade_id=idea_id,
        ticker=ticker,
        action=action,
        shares=max_shares,
        entry_price=entry_price,
        entry_amount=order_result["amount"],
        target_price=request.target_price,
        stop_loss_price=stop_loss_price,
        cash_remaining=order_result["cash_after"],
        message=f"Created paper trade: {action.upper()} {max_shares} {ticker} @ ${entry_price:.2f}",
    )


@router.get("/transactions")
async def get_transactions(limit: int = 100) -> list[dict[str, str | int | float | None]]:
    """Get recent paper trade transactions.

    Returns a list of all transaction records (entries and exits) ordered by
    timestamp (newest first). Each transaction includes ticker, shares, price,
    cash balances, and notes.

    Args:
        limit: Maximum number of transactions to return (default 100)

    Returns:
        List of transaction records
    """
    storage = get_storage()
    transaction_logger = TransactionLogger(storage)

    transactions = transaction_logger.get_transactions(limit=limit)

    return transactions


@router.get("/transactions/{trade_id}")
async def get_trade_transactions(trade_id: str) -> list[dict[str, str | int | float | None]]:
    """Get all transactions for a specific trade.

    Returns entry and exit transactions for a paper trade, useful for auditing
    and understanding the complete lifecycle of a trade.

    Args:
        trade_id: ID of the trade (idea_id)

    Returns:
        List of transaction records for the trade

    Raises:
        HTTPException: If trade not found
    """
    storage = get_storage()
    transaction_logger = TransactionLogger(storage)

    transactions = transaction_logger.get_transactions(trade_id=trade_id)

    if not transactions:
        raise HTTPException(status_code=404, detail=f"No transactions found for trade {trade_id}")

    return transactions
