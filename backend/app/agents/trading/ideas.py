"""Investment ideas and strategy seed executors."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.analytics.paper_trading import create_paper_trade
from app.logging_config import get_logger

logger = get_logger(__name__)


def execute_store_idea(
    storage: PortfolioStorage, agent_run_id: str, **idea_data: object
) -> dict[str, object]:
    """Execute store_idea tool and automatically create a paper trade.

    Args:
        storage: PortfolioStorage instance
        agent_run_id: ID of the agent run
        **idea_data: Idea data fields

    Returns:
        Result dictionary with idea ID and status
    """
    idea_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    storage.insert_dict(
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
    paper_trade = create_paper_trade(storage, idea_id)

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
    storage: PortfolioStorage,
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
        storage: PortfolioStorage instance
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
    storage.insert_dict(
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
            with storage.connection() as conn:
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


__all__ = ["execute_store_idea", "execute_store_strategy_seed"]
