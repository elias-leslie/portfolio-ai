"""Strategy research workflow - orchestrates research-driven strategy generation.

This workflow:
1. Aggregates market research from all sources
2. Generates strategy via LLM agent
3. Optimizes parameters via backtesting
4. Stores strategy in database
5. Commits results to git
"""

from __future__ import annotations

import uuid
from typing import Any

from app.agents.workflows.strategy_research_helpers import run_workflow_steps
from app.logging_config import get_logger

logger = get_logger(__name__)


async def strategy_research_workflow(
    symbol: str,
    force_regenerate: bool = False,
) -> dict[str, Any]:
    """Generate new strategy from market research.

    Steps:
    1. Check if active strategy exists (skip if exists unless force=True)
    2. Aggregate market research
    3. Generate strategy via LLM agent
    4. Optimize parameters via backtesting
    5. Store strategy in database
    6. Commit to git with research summary

    Args:
        symbol: Stock symbol
        force_regenerate: Regenerate even if active strategy exists

    Returns:
        Dict with workflow results:
        - workflow_id: Workflow UUID
        - status: "completed", "skipped", "blocked", or "failed"
        - strategy_id: Strategy UUID (if completed)
        - commit_sha: Git commit SHA (if completed)
        - message: Status message
        - error_message: Error details (if failed)
    """
    workflow_id = str(uuid.uuid4())
    logger.info(
        "Starting strategy research workflow",
        workflow_id=workflow_id,
        symbol=symbol,
        force_regenerate=force_regenerate,
    )
    try:
        return await run_workflow_steps(symbol, workflow_id, force_regenerate)
    except Exception as e:
        logger.exception(
            "Strategy research workflow failed",
            workflow_id=workflow_id,
            symbol=symbol,
            error=str(e),
        )
        return {
            "workflow_id": workflow_id,
            "status": "failed",
            "error_message": str(e),
            "message": f"Workflow failed: {str(e)[:100]}",
        }
