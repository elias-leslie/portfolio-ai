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

from app.analytics.calculation_engine import (
    calculate_atr_stop_loss,
    calculate_position_size_from_risk,
)
from app.analytics.order_executor import OrderExecutor
from app.analytics.transaction_logger import TransactionLogger
from app.analytics.types import TransactionDict
from app.logging_config import get_logger
from app.rules import get_rules
from app.storage import get_storage
from app.utils.market_hours import is_market_open

logger = get_logger(__name__)

router = APIRouter(prefix="/api/paper-trading", tags=["paper-trading"])


# ============================================================================
# Request/Response Models
# ============================================================================


class CreateTradeRequest(BaseModel):
    """Request model for creating a manual paper trade."""

    symbol: str = Field(..., description="Stock symbol")
    action: Literal["buy"] = Field(..., description="Trade action: 'buy' only")
    thesis: str = Field(..., description="Investment thesis for this trade")
    target_price: float | None = Field(None, description="Optional target exit price")
    stop_loss_pct: float | None = Field(None, description="Optional stop loss percentage")


class CreateTradeResponse(BaseModel):
    """Response model for trade creation."""

    status: str
    trade_id: str | None = None
    symbol: str | None = None
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
    symbol: str
    shares: int
    price: float
    amount: float
    cash_before: float
    cash_after: float
    timestamp: str
    notes: str | None
    # Slippage fields (FEAT-210)
    expected_price: float | None = None
    slippage_amount: float | None = None
    slippage_bps: float | None = None
    adv: float | None = None
    slippage_model: str | None = None


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
        request: Trade creation request with symbol, action, thesis, and optional
                target/stop loss

    Returns:
        Trade creation response with execution details

    Raises:
        HTTPException: If trade creation fails
    """
    storage = get_storage()
    order_executor = OrderExecutor(storage)

    # Validate inputs
    symbol = request.symbol.upper()
    action = request.action.lower()

    # Check market hours
    if not is_market_open():
        raise HTTPException(
            status_code=400,
            detail="Market is closed. Paper trading is only available during market hours (9:30 AM - 4:00 PM ET, Mon-Fri, excluding holidays).",
        )

    # Calculate max affordable shares (5% of account)
    account_id = "paper_trading"
    rules = get_rules()

    # Create agent idea record (agent_run_id = "manual" for manual trades)
    idea_id = str(uuid.uuid4())

    storage.insert_dict(
        "agent_ideas",
        {
            "id": idea_id,
            "agent_run_id": "manual",  # Special ID for manual trades
            "idea_type": action,
            "title": f"{action.capitalize()} {symbol}",
            "thesis": request.thesis,
            "action": f"{action.capitalize()} {symbol}",
            "confidence_score": 0.7,  # Default confidence for manual trades (0-1 scale)
            "risk_level": "medium",  # Default risk
            "status": "pending",
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )

    # Create placeholder idea_outcomes record BEFORE order execution
    # This is required for foreign key constraint in paper_trade_transactions
    # We'll update it with actual execution details after order fills
    storage.insert_dict(
        "idea_outcomes",
        {
            "idea_id": idea_id,
            "agent_run_id": "manual",
            "symbol": symbol,
            "idea_type": action,
            "entry_price": 0.0,  # Placeholder, will update after execution
            "entry_date": datetime.now(UTC).date().isoformat(),
            "target_price": request.target_price,
            "stop_loss_price": None,  # Will calculate after execution
            "current_price": 0.0,  # Placeholder
            "current_return_pct": 0.0,
            "status": "open",
            "shares": 0,
            "entry_amount": 0.0,  # Placeholder
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )

    price_data = order_executor.price_fetcher.fetch_price_data([symbol])
    if symbol not in price_data or price_data[symbol].error:
        raise HTTPException(status_code=400, detail=f"Failed to fetch price for {symbol}")

    entry_price = price_data[symbol].price
    stop_loss_price = (
        round(entry_price * (1 - request.stop_loss_pct / 100.0), 2)
        if request.stop_loss_pct is not None
        else calculate_atr_stop_loss(storage, symbol, entry_price)
    )
    if stop_loss_price is None:
        raise HTTPException(
            status_code=400,
            detail="Cannot calculate an ATR-backed stop loss for this symbol",
        )

    cash_balance = order_executor.cash_manager.get_cash_balance(account_id)
    risk_budget = cash_balance * rules.position_sizing.default_risk_percent
    risk_based_shares = calculate_position_size_from_risk(
        entry_price,
        stop_loss_price,
        risk_budget,
    )
    cap_based_shares = order_executor.calculate_max_shares(
        symbol,
        account_id,
        max_position_pct=rules.paper_trading.default_position_pct,
    )
    max_shares = min(risk_based_shares or 0, cap_based_shares)

    if max_shares <= 0:
        raise HTTPException(
            status_code=400,
            detail="Insufficient cash or failed to calculate position size",
        )

    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE idea_outcomes
            SET shares = $1,
                target_price = $2,
                stop_loss_price = $3,
                updated_at = NOW()
            WHERE idea_id = $4
            """,
            [max_shares, request.target_price, stop_loss_price, idea_id],
        )
        conn.commit()

    action_typed = cast(Literal["buy"], action)
    order_result = order_executor.execute_market_order(
        symbol=symbol,
        action=action_typed,
        shares=max_shares,
        account_id=account_id,
        trade_id=idea_id,
        notes=f"Manual paper trade: {request.thesis[:100]}",
    )

    if not order_result.get("filled"):
        error_msg = order_result.get("error", "Unknown error")
        logger.error(f"Failed to execute manual paper trade for {symbol}: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

    # Update idea_outcomes record with actual execution details
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE idea_outcomes
            SET entry_price = $1,
                entry_amount = $2,
                current_price = $3,
                stop_loss_price = $4,
                updated_at = NOW()
            WHERE idea_id = $5
            """,
            [
                entry_price,
                order_result["amount"],
                entry_price,
                stop_loss_price,
                idea_id,
            ],
        )
        conn.commit()  # Commit UPDATE to database

    logger.info(
        f"Manual paper trade created: {action.upper()} {max_shares} {symbol} "
        f"@ ${entry_price:.2f} (${order_result['amount']:.2f})"
    )

    return CreateTradeResponse(
        status="created",
        trade_id=idea_id,
        symbol=symbol,
        action=action,
        shares=max_shares,
        entry_price=entry_price,
        entry_amount=order_result["amount"],
        target_price=request.target_price,
        stop_loss_price=stop_loss_price,
        cash_remaining=order_result["cash_after"],
        message=f"Created paper trade: {action.upper()} {max_shares} {symbol} @ ${entry_price:.2f}",
    )


@router.get("/transactions")
async def get_transactions(limit: int = 100) -> list[TransactionDict]:
    """Get recent paper trade transactions.

    Returns a list of all transaction records (entries and exits) ordered by
    timestamp (newest first). Each transaction includes symbol, shares, price,
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
async def get_trade_transactions(trade_id: str) -> list[TransactionDict]:
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
