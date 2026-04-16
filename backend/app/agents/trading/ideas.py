"""Strategy seed executor."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.storage.facade import PortfolioStorage

from app.logging_config import get_logger
from app.services.preferences_service import get_automation_preferences

logger = get_logger(__name__)


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

    logger.info("strategy_seed_stored", seed_id=seed_id, symbol=symbol, confidence=confidence)

    # Emit seed_created event for downstream triggers (auto-003)
    # This replaces direct task calls with centralized event handling
    workflow_triggered = False
    if confidence >= 7.0:
        try:
            automation = get_automation_preferences()
            if not bool(automation["scheduled_strategy_research_enabled"]["enabled"]):
                return {
                    "seed_id": seed_id,
                    "symbol": symbol,
                    "confidence": confidence,
                    "status": "stored",
                    "workflow_triggered": False,
                    "message": "Seed stored. Strategy workflow not triggered because background strategy research is disabled.",
                }

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
            logger.info("seed_created_event_emitted", seed_id=seed_id, symbol=symbol, confidence=confidence)

        except Exception as e:
            logger.warning("strategy_workflow_trigger_failed", seed_id=seed_id, symbol=symbol, error=str(e), exc_info=True)

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


__all__ = ["execute_store_strategy_seed"]
