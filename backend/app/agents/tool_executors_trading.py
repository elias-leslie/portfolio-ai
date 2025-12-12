"""Trading tool executors for agent trading operations.

This module provides execution logic for trading tools:
- store_idea: Store investment ideas
- add_symbol: Add symbols to watchlist
- remove_symbol: Remove symbols from watchlist
- create_paper_trade: Create paper trades
- run_backtest: Execute backtests for strategy validation

Section 1.2: Confidence → Leverage enforcement added.
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Literal, cast

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.analytics.order_executor import OrderExecutor
from app.analytics.paper_trading import create_paper_trade
from app.backtest.storage import create_backtest_run, get_backtest_run, update_backtest_status
from app.logging_config import get_logger

logger = get_logger(__name__)

# Confidence tier → position size multiplier mapping (Section 1.2)
# Higher confidence = larger positions, lower confidence = smaller positions
CONFIDENCE_LEVERAGE_MAP = {
    "very_low": {"min": 0.0, "max": 0.2, "multiplier": 0.25, "max_position_pct": 0.0125},
    "low": {"min": 0.2, "max": 0.4, "multiplier": 0.5, "max_position_pct": 0.025},
    "medium": {"min": 0.4, "max": 0.6, "multiplier": 1.0, "max_position_pct": 0.05},
    "high": {"min": 0.6, "max": 0.8, "multiplier": 1.5, "max_position_pct": 0.075},
    "very_high": {"min": 0.8, "max": 1.0, "multiplier": 2.0, "max_position_pct": 0.10},
}


def get_confidence_tier(confidence: float) -> str:
    """Get confidence tier from confidence score.

    Args:
        confidence: Confidence score (0.0-1.0)

    Returns:
        Tier name: very_low, low, medium, high, very_high
    """
    if confidence >= 0.8:
        return "very_high"
    if confidence >= 0.6:
        return "high"
    if confidence >= 0.4:
        return "medium"
    if confidence >= 0.2:
        return "low"
    return "very_low"


def calculate_confidence_adjusted_position(
    confidence: float, base_max_position_pct: float = 0.05
) -> float:
    """Calculate position size adjusted for confidence level.

    Args:
        confidence: Confidence score (0.0-1.0)
        base_max_position_pct: Base position size (default 5%)

    Returns:
        Adjusted max_position_pct
    """
    tier = get_confidence_tier(confidence)
    tier_config = CONFIDENCE_LEVERAGE_MAP[tier]
    return tier_config["max_position_pct"]


class TradingTools:
    """Trading tool executors for agents."""

    def __init__(self, storage: PortfolioStorage) -> None:
        """Initialize trading tools.

        Args:
            storage: PortfolioStorage instance
        """
        self.storage = storage
        self.order_executor = OrderExecutor(storage)

    def execute_store_idea(self, agent_run_id: str, **idea_data: object) -> dict[str, object]:
        """Execute store_idea tool and automatically create a paper trade.

        Args:
            agent_run_id: ID of the agent run
            **idea_data: Idea data fields

        Returns:
            Result dictionary with idea ID and status
        """
        idea_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        self.storage.insert_dict(
            "agent_ideas",
            {
                "id": idea_id,
                "agent_run_id": agent_run_id,
                "idea_type": str(idea_data.get("idea_type")),
                "title": str(idea_data.get("title")),
                "thesis": str(idea_data.get("thesis")),
                "action": str(idea_data.get("action")),
                "confidence_score": (
                    cast(float, idea_data.get("confidence_score")) / 100.0
                    if cast(float, idea_data.get("confidence_score")) > 1.0
                    else cast(float, idea_data.get("confidence_score"))
                ),
                "risk_level": str(idea_data.get("risk_level")),
                "reward_estimate": cast(float, idea_data.get("reward_estimate")),
                "portfolio_impact": cast(float, idea_data.get("portfolio_impact")),
                "data_needed": str(idea_data.get("data_needed")),
                "risks": str(idea_data.get("risks")),
                "status": "pending",
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            },
        )

        logger.info(f"Stored idea {idea_id}: {idea_data.get('title')}")

        # Automatically create paper trade for this idea
        paper_trade = create_paper_trade(self.storage, idea_id)

        if paper_trade:
            logger.info(
                f"Created paper trade for idea {idea_id}: "
                f"{paper_trade['symbol']} @ ${paper_trade['entry_price']}"
            )
            return {
                "idea_id": idea_id,
                "status": "stored",
                "paper_trade_created": True,
                "symbol": paper_trade["symbol"],
            }
        logger.warning(f"Failed to create paper trade for idea {idea_id}")
        return {"idea_id": idea_id, "status": "stored", "paper_trade_created": False}

    def execute_store_strategy_seed(
        self,
        agent_run_id: str,
        symbol: str,
        thesis: str,
        confidence: float,
        source_data: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Execute store_strategy_seed tool to create a strategy seed.

        Seeds are AI-generated investment ideas with required symbol. High-confidence
        seeds (>=7) automatically trigger strategy_research_workflow.

        Args:
            agent_run_id: ID of the agent run
            symbol: Stock symbol (REQUIRED - fixes broken Ideas system)
            thesis: Investment thesis explaining the opportunity
            confidence: Confidence score (1-10 scale)
            source_data: Optional context data (news, economic indicators)

        Returns:
            Result dictionary with seed ID, status, and workflow trigger info
        """
        # Normalize symbol
        symbol = symbol.upper().strip()
        if not symbol:
            return {"status": "error", "error": "Symbol is required"}

        # Normalize confidence to 1-10 scale
        if confidence > 10:
            confidence = confidence / 10.0  # Handle 0-100 input
        confidence = max(1.0, min(10.0, confidence))

        seed_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # Store seed in strategy_seeds table
        self.storage.insert_dict(
            "strategy_seeds",
            {
                "id": seed_id,
                "symbol": symbol,
                "thesis": thesis,
                "confidence": confidence,
                "agent_run_id": agent_run_id,
                "source_type": "discovery",
                "source_data": str(source_data) if source_data else None,
                "status": "pending",
                "created_at": now.isoformat(),
            },
        )

        logger.info(f"Stored strategy seed {seed_id}: {symbol} (confidence: {confidence})")

        # Emit seed_created event for downstream triggers (auto-003)
        # This replaces direct task calls with centralized event handling
        workflow_triggered = False
        if confidence >= 7.0:
            try:
                from app.tasks.triggers import emit_event

                # Update seed status to processing
                with self.storage.connection() as conn:
                    conn.execute(
                        "UPDATE strategy_seeds SET status = 'processing', processed_at = %s WHERE id = %s",
                        [now.isoformat(), seed_id],
                    )
                    conn.commit()

                # Emit event (triggers strategy workflow via centralized handler)
                emit_event(
                    "seed_created",
                    {
                        "seed_id": seed_id,
                        "symbol": symbol,
                        "confidence": confidence,
                        "thesis": thesis[:200] if thesis else "",
                    },
                )
                workflow_triggered = True
                logger.info(f"Emitted seed_created event for {seed_id} (confidence: {confidence})")

            except Exception as e:
                logger.warning(f"Failed to trigger strategy workflow for seed {seed_id}: {e}")

        return {
            "seed_id": seed_id,
            "symbol": symbol,
            "confidence": confidence,
            "status": "stored",
            "workflow_triggered": workflow_triggered,
            "message": (
                f"Seed stored. Strategy workflow {'triggered' if workflow_triggered else 'not triggered (confidence < 7)'}."
            ),
        }

    def execute_add_symbol(
        self,
        agent_run_id: str,
        symbol: str,
        reason: str,
        expected_return_pct: float,
        time_horizon_days: int,
    ) -> dict[str, object]:
        """Execute add_symbol tool to autonomously add symbols to watchlist.

        Args:
            agent_run_id: ID of the agent run (for ownership tracking)
            symbol: Stock symbol
            reason: Why adding this symbol
            expected_return_pct: Expected return percentage
            time_horizon_days: Time horizon in days

        Returns:
            Result dictionary with status and details
        """
        symbol = symbol.upper()

        # Check if symbol already exists
        existing = self.storage.query(
            "SELECT id, added_by FROM watchlist_items WHERE symbol = $1", [symbol]
        )

        if not existing.is_empty():
            added_by = existing.get_column("added_by")[0]
            return {
                "status": "exists",
                "symbol": symbol,
                "added_by": added_by,
                "message": f"{symbol} already in watchlist (added by {added_by})",
            }

        # Create watchlist item with ownership tracking
        item_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        metadata = {
            "reason": reason,
            "expected_return_pct": expected_return_pct,
            "time_horizon_days": time_horizon_days,
            "added_by_agent": agent_run_id,
        }

        try:
            # Ensure symbol exists in symbols table (FK constraint)
            with self.storage.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO symbols (symbol, security_type, created_at)
                    VALUES (%s, 'equity', %s)
                    ON CONFLICT (symbol) DO NOTHING
                    """,
                    [symbol, now.isoformat()],
                )
                conn.commit()

            self.storage.insert_dict(
                "watchlist_items",
                {
                    "id": item_id,
                    "symbol": symbol,
                    "metadata": str(metadata),
                    "added_by": agent_run_id,
                    "added_at": now.isoformat(),
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                },
            )

            logger.info(f"Agent {agent_run_id} added {symbol} to watchlist: {reason}")

            return {
                "status": "added",
                "symbol": symbol,
                "item_id": item_id,
                "message": f"Added {symbol} to watchlist (expected {expected_return_pct}% in {time_horizon_days} days)",
            }

        except Exception as e:
            logger.error(f"Failed to add {symbol} to watchlist: {e}")
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e),
            }

    def execute_remove_symbol(
        self, agent_run_id: str, symbol: str, reason: str
    ) -> dict[str, object]:
        """Execute remove_symbol tool with ownership validation.

        Agents can ONLY remove symbols they added. This prevents agents from
        removing user-added symbols or symbols added by other agents.

        Args:
            agent_run_id: ID of the agent run
            symbol: Stock symbol to remove
            reason: Why removing this symbol

        Returns:
            Result dictionary with status and details
        """
        symbol = symbol.upper()

        # Check if symbol exists and get ownership
        existing = self.storage.query(
            "SELECT id, added_by, added_at FROM watchlist_items WHERE symbol = $1", [symbol]
        )

        if existing.is_empty():
            return {
                "status": "not_found",
                "symbol": symbol,
                "message": f"{symbol} not in watchlist",
            }

        item_id = existing.get_column("id")[0]
        added_by = existing.get_column("added_by")[0]
        added_at = existing.get_column("added_at")[0]

        # Ownership validation
        if added_by != agent_run_id:
            if added_by == "user":
                return {
                    "status": "forbidden",
                    "symbol": symbol,
                    "added_by": added_by,
                    "message": f"Cannot remove {symbol} - user-added symbols can only be removed by users",
                }
            return {
                "status": "forbidden",
                "symbol": symbol,
                "added_by": added_by,
                "message": f"Cannot remove {symbol} - added by different agent ({added_by})",
            }

        # Time threshold check (30 days minimum)
        days_since_added = (datetime.now(UTC) - added_at).days
        if days_since_added < 30:
            return {
                "status": "too_soon",
                "symbol": symbol,
                "days_since_added": days_since_added,
                "message": f"Cannot remove {symbol} - only {days_since_added} days since added (need 30+)",
            }

        # Remove symbol
        try:
            with self.storage.connection() as conn:
                conn.execute("DELETE FROM watchlist_items WHERE id = $1", [item_id])

            logger.info(
                f"Agent {agent_run_id} removed {symbol} from watchlist after {days_since_added} days: {reason}"
            )

            return {
                "status": "removed",
                "symbol": symbol,
                "days_held": days_since_added,
                "message": f"Removed {symbol} from watchlist (held {days_since_added} days): {reason}",
            }

        except Exception as e:
            logger.error(f"Failed to remove {symbol}: {e}")
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e),
            }

    def execute_create_paper_trade(
        self,
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
        account_id = "paper_trading"
        max_shares = self.order_executor.calculate_max_shares(
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

        self.storage.insert_dict(
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

        order_result = self.order_executor.execute_market_order(
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
        self.storage.insert_dict(
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

    def execute_run_backtest(
        self,
        agent_run_id: str,
        symbol: str,
        start_date: str,
        end_date: str,
        initial_capital: float = 100000.0,
        strategy_name: str = "signal_classifier",
        min_signal_strength: int = 7,
        max_holding_days: int = 60,
        position_sizing_method: str = "fixed_dollars",
        position_size_value: float = 10000.0,
    ) -> dict[str, object]:
        """Execute run_backtest tool for strategy validation.

        Runs backtest synchronously and waits for completion (agents need results
        to make decisions). Uses Celery task but blocks until done.

        Args:
            agent_run_id: ID of the agent run
            symbol: Stock symbol
            start_date: Backtest start date (ISO format: YYYY-MM-DD)
            end_date: Backtest end date (ISO format: YYYY-MM-DD)
            initial_capital: Starting capital (default: 100000.0)
            strategy_name: Strategy to use (default: 'signal_classifier')
            min_signal_strength: Minimum signal strength (1-10, default: 7)
            max_holding_days: Maximum holding period (default: 60)
            position_sizing_method: 'fixed_dollars' or 'fixed_shares' (default: 'fixed_dollars')
            position_size_value: Position size in dollars or shares (default: 10000.0)

        Returns:
            Result dictionary with backtest metrics or error
        """
        symbol = symbol.upper()

        # Validate date format and parse
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)

            if end < start:
                return {
                    "status": "error",
                    "error": f"end_date ({end_date}) must be >= start_date ({start_date})",
                }
        except ValueError as e:
            return {
                "status": "error",
                "error": f"Invalid date format (use YYYY-MM-DD): {e}",
            }

        try:
            # Create backtest run record
            run_id = create_backtest_run(
                storage=self.storage,
                strategy_name=strategy_name,
                symbol=symbol,
                start_date=start,
                end_date=end,
                initial_capital=Decimal(str(initial_capital)),
            )

            logger.info(
                f"Agent {agent_run_id} started backtest {run_id}: {symbol} "
                f"({start_date} to {end_date})"
            )

            # Update status to running
            update_backtest_status(self.storage, run_id, "running")

            # Launch Celery task (lazy import to avoid circular dependency)
            from app.tasks.backtest_tasks import run_backtest_task

            run_backtest_task.delay(
                run_id=run_id,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                initial_capital=initial_capital,
                strategy_name=strategy_name,
                min_signal_strength=min_signal_strength,
                max_holding_days=max_holding_days,
                position_sizing_method=position_sizing_method,
                position_size_value=position_size_value,
            )

            # Wait for task completion (synchronous for agent decision-making)
            # Poll database for completion (max 5 minutes)
            max_wait_seconds = 300
            poll_interval = 2
            elapsed = 0

            while elapsed < max_wait_seconds:
                time.sleep(poll_interval)
                elapsed += poll_interval

                # Check backtest status
                run = get_backtest_run(self.storage, run_id)

                if not run:
                    return {
                        "status": "error",
                        "error": f"Backtest run {run_id} not found",
                    }

                if run.status == "completed":
                    logger.info(
                        f"Backtest {run_id} completed: "
                        f"Sharpe {run.sharpe_ratio:.2f}, Win Rate {run.win_rate:.1f}%, "
                        f"Return {run.total_return_pct:.2f}%, Drawdown {run.max_drawdown_pct:.2f}%"
                    )

                    return {
                        "status": "completed",
                        "backtest_run_id": run_id,
                        "symbol": symbol,
                        "sharpe_ratio": float(run.sharpe_ratio) if run.sharpe_ratio else 0.0,
                        "win_rate": float(run.win_rate) if run.win_rate else 0.0,
                        "max_drawdown_pct": (
                            float(run.max_drawdown_pct) if run.max_drawdown_pct else 0.0
                        ),
                        "total_return_pct": (
                            float(run.total_return_pct) if run.total_return_pct else 0.0
                        ),
                        "num_trades": run.num_trades if run.num_trades else 0,
                        "message": (
                            f"Backtest complete: Sharpe {run.sharpe_ratio:.2f}, "
                            f"Win Rate {run.win_rate:.1f}%, Return {run.total_return_pct:.2f}%"
                        ),
                    }

                if run.status == "failed":
                    error_msg = run.error_message or "Unknown error"
                    logger.error(f"Backtest {run_id} failed: {error_msg}")
                    return {
                        "status": "error",
                        "backtest_run_id": run_id,
                        "symbol": symbol,
                        "error": f"Backtest failed: {error_msg}",
                    }

            # Timeout
            logger.warning(f"Backtest {run_id} timed out after {max_wait_seconds}s")
            return {
                "status": "timeout",
                "backtest_run_id": run_id,
                "symbol": symbol,
                "error": f"Backtest timed out after {max_wait_seconds}s",
            }

        except Exception as e:
            logger.error(f"Failed to execute backtest for {symbol}: {e}")
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e),
            }


__all__ = ["TradingTools"]
