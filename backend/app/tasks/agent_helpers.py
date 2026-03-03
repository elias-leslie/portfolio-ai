"""Helper functions for agent task execution.

Extracted from agent_tasks.py to keep task registration thin.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from app.agents.llm_client import DualProviderClient
from app.agents.tools import AgentTools
from app.analytics.paper_trading import update_paper_trades
from app.analytics.types import PaperTradeStatsDict
from app.logging_config import get_logger
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services import NewsService
from app.sources.fred import FREDSource
from app.storage import get_storage
from app.storage.credential_loader import load_credentials_from_database
from app.tasks.triggers import emit_event
from app.utils.task_lifecycle import task_cleanup

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)

MIN_MEANINGFUL_RESPONSE_LENGTH = 50


def setup_agent_tools(storage: PortfolioStorage) -> AgentTools:
    """Initialize agent tools with all required dependencies."""
    load_credentials_from_database()
    news_service = NewsService(storage)
    news_service.refresh_ttl_from_preferences()
    news_service.refresh_max_articles_from_preferences()
    fred_source = FREDSource()
    price_fetcher = PriceDataFetcher(storage)
    portfolio_mgr = PortfolioManager(storage)
    analytics = PortfolioAnalytics()

    return AgentTools(
        storage=storage,
        news_service=news_service,
        fred_source=fred_source,
        price_fetcher=price_fetcher,
        portfolio_mgr=portfolio_mgr,
        analytics=analytics,
    )


def update_celery_task_id(storage: PortfolioStorage, task_id: str, run_id: str) -> None:
    """Update agent_runs table with task ID."""
    with storage.connection() as conn:
        cursor = conn.execute(
            """
            UPDATE agent_runs
            SET celery_task_id = ?
            WHERE id = ?
            """,
            [task_id, run_id],
        )
        if cursor.rowcount == 0:
            logger.warning("update_celery_task_id_no_match", run_id=run_id, task_id=task_id)
        conn.commit()


def emit_insight_if_meaningful(agent_response: str, context_type: str, confidence: float) -> None:
    """Emit insight_generated event if the agent response is non-trivial."""
    if agent_response and len(agent_response) > MIN_MEANINGFUL_RESPONSE_LENGTH:
        emit_event(
            "insight_generated",
            {
                "output": agent_response,
                "context_type": context_type,
                "confidence": confidence,
            },
        )


def run_agent_task(
    agent_class: Any,
    task_name: str,
    context_type: str,
    confidence: float,
) -> str:
    """Run a single agent task with standard lifecycle management.

    Args:
        agent_class: Agent class to instantiate and run
        task_name: Human-readable name for logging (e.g. "discovery_agent")
        context_type: Event context type for insight emission
        confidence: Default confidence for emitted insight events

    Returns:
        Run ID of the agent execution, or "skipped:..." prefix on skip.
    """
    from app.rules.loader import get_rules

    rules = get_rules()
    if not rules.thesis_management.thesis_generation_enabled:
        logger.info("agent_task_skipped", task_name=task_name, reason="thesis_generation_disabled")
        return "skipped:thesis_generation_disabled"

    task_id = str(uuid.uuid4())
    logger.info("agent_task_started", task_name=task_name, task_id=task_id)

    llm_client: DualProviderClient | None = None
    try:
        storage = get_storage()
        agent_tools = setup_agent_tools(storage)
        llm_client = DualProviderClient(primary="gemini")

        agent = agent_class(storage=storage, tools=agent_tools, llm_client=llm_client)
        result = agent.run()
        run_id = result.get("run_id")
        if not run_id:
            raise ValueError(f"Agent {task_name} returned result without run_id: {result.keys()}")

        update_celery_task_id(storage, task_id, run_id)
        emit_insight_if_meaningful(result.get("response", ""), context_type, confidence)

        logger.info("agent_task_completed", task_name=task_name, task_id=task_id, run_id=run_id)
        return run_id

    except Exception as e:
        logger.error("agent_task_failed", task_name=task_name, task_id=task_id, error=str(e), error_type=type(e).__name__)
        raise
    finally:
        if llm_client is not None:
            llm_client.close()
        task_cleanup(f"run_{task_name}")


def run_paper_trades_update(max_holding_days: int = 60) -> PaperTradeStatsDict:
    """Update all open paper trades with current prices and check for exits.

    Args:
        max_holding_days: Maximum days to hold before auto-closing (default: 60)

    Returns:
        Dict with update statistics (trades_updated, trades_closed, target_hits,
        stop_hits, expired).
    """
    task_id = str(uuid.uuid4())
    logger.info(
        "update_paper_trades_task_started",
        task_id=task_id,
        max_holding_days=max_holding_days,
    )

    try:
        storage = get_storage()
        stats = update_paper_trades(storage, max_holding_days=max_holding_days)
        logger.info("update_paper_trades_task_completed", task_id=task_id, **stats)
        return stats

    except Exception as e:
        logger.error(
            "update_paper_trades_task_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
