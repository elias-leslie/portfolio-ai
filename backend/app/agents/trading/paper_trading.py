"""Paper trading executor."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.analytics.order_executor import OrderExecutor
from app.logging_config import get_logger

from .confidence import calculate_confidence_adjusted_position, get_confidence_tier

logger = get_logger(__name__)


def execute_create_paper_trade(
    storage: PortfolioStorage,
    agent_run_id: str,
    symbol: str,
    action: str,
    thesis: str,
    target_price: float | None = None,
    stop_loss_pct: float | None = None,
    confidence_score: float = 0.7,
) -> dict[str, object]:
    """Execute create_paper_trade tool for autonomous paper trading.

    Creates a paper trade with automatic cash management and position sizing.
    Position size is now confidence-adjusted (Section 1.2):
    - Low confidence (0-0.4): 1.25-2.5% position
    - Medium confidence (0.4-0.6): 5% position (base)
    - High confidence (0.6-0.8): 7.5% position
    - Very high confidence (0.8-1.0): 10% position

    Args:
        storage: PortfolioStorage instance
        agent_run_id: ID of the agent run
        symbol: Stock symbol
        action: 'buy' or 'sell'
        thesis: Investment thesis
        target_price: Optional target exit price
        stop_loss_pct: Optional stop loss percentage
        confidence_score: Confidence score (0.0-1.0) for position sizing

    Returns:
        Result dictionary with trade details or error
    """
    symbol = symbol.upper()
    action = action.lower()

    # Validate action
    if action not in ["buy", "sell"]:
        return {
            "status": "error",
            "error": f"Invalid action '{action}' (must be 'buy' or 'sell')",
        }

    # Normalize confidence score (handle 0-100 vs 0-1)
    normalized_confidence = (
        confidence_score / 100.0 if confidence_score > 1.0 else confidence_score
    )

    # Calculate confidence-adjusted position size (Section 1.2)
    adjusted_position_pct = calculate_confidence_adjusted_position(normalized_confidence)
    confidence_tier = get_confidence_tier(normalized_confidence)

    logger.info(
        f"Position sizing: confidence={normalized_confidence:.2f} ({confidence_tier}) "
        f"→ position_pct={adjusted_position_pct:.2%}"
    )

    # Calculate max affordable shares using confidence-adjusted sizing
    order_executor = OrderExecutor(storage)
    account_id = "paper_trading"
    max_shares = order_executor.calculate_max_shares(
        symbol, account_id, max_position_pct=adjusted_position_pct
    )

    if max_shares == 0:
        return {
            "status": "error",
            "symbol": symbol,
            "error": "Insufficient cash or failed to calculate position size",
        }

    # Create agent idea record
    idea_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    storage.insert_dict(
        "agent_ideas",
        {
            "id": idea_id,
            "agent_run_id": agent_run_id,
            "idea_type": action,  # "buy" or "sell"
            "title": f"{action.capitalize()} {symbol}",
            "thesis": thesis,
            "action": f"{action.capitalize()} {max_shares} shares of {symbol}",
            "confidence_score": (
                confidence_score / 100.0 if confidence_score > 1.0 else confidence_score
            ),
            "risk_level": "medium",  # Default risk
            "status": "pending",
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    )

    # Execute market order
    # Cast action to Literal type for type safety
    action_typed = cast(Literal["buy", "sell"], action)

    order_result = order_executor.execute_market_order(
        symbol=symbol,
        action=action_typed,
        shares=max_shares,
        account_id=account_id,
        trade_id=idea_id,
        notes=f"Agent paper trade: {thesis[:100]}",
    )

    if not order_result.get("filled"):
        error_msg = order_result.get("error", "Unknown error")
        logger.error(f"Failed to execute paper trade for {symbol}: {error_msg}")
        return {
            "status": "error",
            "symbol": symbol,
            "error": error_msg,
        }

    # Calculate stop loss price if not provided
    entry_price = order_result["price"]
    if stop_loss_pct is None:
        # Default: 2x ATR (will be calculated by paper trading update task)
        stop_loss_price = None
    elif action == "buy":
        stop_loss_price = entry_price * (1 - stop_loss_pct / 100)
    else:  # sell (short)
        stop_loss_price = entry_price * (1 + stop_loss_pct / 100)

    # Create idea_outcomes record
    now = datetime.now(UTC)
    storage.insert_dict(
        "idea_outcomes",
        {
            "idea_id": idea_id,
            "agent_run_id": agent_run_id,
            "symbol": symbol,
            "idea_type": action,
            "entry_price": entry_price,
            "entry_date": now.date().isoformat(),
            "target_price": target_price,
            "stop_loss_price": stop_loss_price,
            "current_price": entry_price,
            "current_return_pct": 0.0,
            "status": "open",
            "shares": max_shares,
            "entry_amount": order_result["amount"],
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        },
    )

    logger.info(
        f"Agent {agent_run_id} created paper trade: {action.upper()} {max_shares} {symbol} "
        f"@ ${entry_price:.2f} (${order_result['amount']:.2f})"
    )

    return {
        "status": "created",
        "trade_id": idea_id,
        "symbol": symbol,
        "action": action,
        "shares": max_shares,
        "entry_price": entry_price,
        "entry_amount": order_result["amount"],
        "target_price": target_price,
        "stop_loss_price": stop_loss_price,
        "cash_remaining": order_result["cash_after"],
        "message": f"Created paper trade: {action.upper()} {max_shares} {symbol} @ ${entry_price:.2f}",
    }


__all__ = ["execute_create_paper_trade"]
