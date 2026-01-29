"""Celery tasks for agent execution and paper trading.

This module defines background tasks for:
- Running AI agents (Discovery, Portfolio Analyzer)
- Updating paper trades

For other background tasks, see:
- watchlist_tasks.py - Watchlist score refresh
- data_ingestion_tasks.py - Historical OHLCV data ingestion
- indicator_tasks.py - Technical indicator calculations
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.agents.discovery import DiscoveryAgent
from app.agents.llm_client import DualProviderClient
from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent
from app.agents.tools import AgentTools
from app.analytics.paper_trading import update_paper_trades
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.rules.loader import get_rules
from app.services import NewsService
from app.sources.fred import FREDSource
from app.storage import get_storage
from app.tasks.triggers import emit_event

if TYPE_CHECKING:
    from celery import Task
from app.storage.credential_loader import load_credentials_from_database

if TYPE_CHECKING:
    from app.storage import PortfolioStorage

logger = get_logger(__name__)


def _setup_agent_tools(storage: PortfolioStorage) -> AgentTools:
    """Initialize agent tools with all required dependencies.

    Args:
        storage: StorageFacade instance for database access

    Returns:
        Configured AgentTools instance with all sources and managers
    """
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


def _update_celery_task_id(storage: PortfolioStorage, task_id: str, run_id: str) -> None:
    """Update agent_runs table with Celery task ID.

    Args:
        storage: StorageFacade instance for database access
        task_id: Celery task ID
        run_id: Agent run ID
    """
    with storage.connection() as conn:
        conn.execute(
            """
            UPDATE agent_runs
            SET celery_task_id = ?
            WHERE id = ?
            """,
            [task_id, run_id],
        )
        conn.commit()


@celery_app.task(name="run_discovery_agent", bind=True)
def run_discovery_agent(self: Task[..., Any]) -> str:
    """Run discovery agent as a background task.

    Returns:
        Run ID of the agent execution
    """
    # Check if agentic features are enabled
    rules = get_rules()
    if not rules.thesis_management.thesis_generation_enabled:
        logger.info("discovery_agent_skipped", reason="thesis_generation_disabled")
        return "skipped:thesis_generation_disabled"

    task_id = self.request.id or "unknown"
    logger.info(
        "discovery_agent_task_started",
        task_id=task_id,
    )

    try:
        storage = get_storage()

        # Initialize agent tools
        agent_tools = _setup_agent_tools(storage)

        # Initialize LLM client (Gemini primary, Claude fallback)
        llm_client = DualProviderClient(primary="gemini")

        agent = DiscoveryAgent(storage=storage, tools=agent_tools, llm_client=llm_client)
        result = agent.run()
        run_id = result["run_id"]

        # Update agent_runs with celery_task_id
        _update_celery_task_id(storage, task_id, run_id)

        # Emit insight_generated event for cross-validation (FEAT-219)
        agent_response = result.get("response", "")
        if agent_response and len(agent_response) > 50:  # Skip trivial outputs
            emit_event(
                "insight_generated",
                {
                    "output": agent_response,
                    "context_type": "discovery_analysis",
                    "confidence": 0.8,  # Discovery agent default confidence
                },
            )

        logger.info(
            "discovery_agent_task_completed",
            task_id=task_id,
            run_id=run_id,
        )
        return run_id

    except Exception as e:
        logger.error(
            "discovery_agent_task_failed",
            task_id=task_id,
            error=str(e),
        )
        raise


@celery_app.task(name="run_portfolio_analyzer", bind=True)
def run_portfolio_analyzer(self: Task[..., Any]) -> str:
    """Run portfolio analyzer agent as a background task.

    Returns:
        Run ID of the agent execution
    """
    # Check if agentic features are enabled
    rules = get_rules()
    if not rules.thesis_management.thesis_generation_enabled:
        logger.info("portfolio_analyzer_skipped", reason="thesis_generation_disabled")
        return "skipped:thesis_generation_disabled"

    task_id = self.request.id or "unknown"
    logger.info(
        "portfolio_analyzer_task_started",
        task_id=task_id,
    )

    try:
        storage = get_storage()

        # Initialize agent tools
        agent_tools = _setup_agent_tools(storage)

        # Initialize LLM client (Gemini primary, Claude fallback)
        llm_client = DualProviderClient(primary="gemini")

        agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools, llm_client=llm_client)
        result = agent.run()
        run_id = result["run_id"]

        # Update agent_runs with celery_task_id
        _update_celery_task_id(storage, task_id, run_id)

        # Emit insight_generated event for cross-validation (FEAT-219)
        agent_response = result.get("response", "")
        if agent_response and len(agent_response) > 50:  # Skip trivial outputs
            emit_event(
                "insight_generated",
                {
                    "output": agent_response,
                    "context_type": "portfolio_analysis",
                    "confidence": 0.85,  # Portfolio analyzer default confidence
                },
            )

        logger.info(
            "portfolio_analyzer_task_completed",
            task_id=task_id,
            run_id=run_id,
        )
        return run_id

    except Exception as e:
        logger.error(
            "portfolio_analyzer_task_failed",
            task_id=task_id,
            error=str(e),
        )
        raise


@celery_app.task(name="update_paper_trades_task", bind=True)
def update_paper_trades_task(  # type: ignore[no-untyped-def]
    self, max_holding_days: int = 60
):
    """Update all open paper trades with current prices and check for exits.

    This task fetches current prices for all open paper trades, updates returns,
    and automatically closes trades that hit target/stop or exceed max holding period.
    Should be scheduled daily at market close + 30 minutes (4:30 PM ET).

    Args:
        max_holding_days: Maximum days to hold before auto-closing (default: 60)

    Returns:
        Dict with update statistics:
        - trades_updated: Number of trades updated
        - trades_closed: Number of trades closed
        - target_hits: Number of target price hits
        - stop_hits: Number of stop loss hits
        - expired: Number of trades closed due to time limit

    Example:
        >>> # Run immediately
        >>> update_paper_trades_task(max_holding_days=60)
        {"trades_updated": 10, "trades_closed": 2, "target_hits": 1, "stop_hits": 0, "expired": 1}

        >>> # Schedule as background task (daily at 4:30 PM ET)
        >>> update_paper_trades_task.delay()

    Note:
        This task should be configured in Celery beat schedule to run daily:
        ```python
        celery_app.conf.beat_schedule = {
            'update-paper-trades-daily': {
                'task': 'update_paper_trades_task',
                'schedule': crontab(hour=16, minute=30),  # 4:30 PM ET
            },
        }
        ```
    """
    task_id = self.request.id
    logger.info(
        "update_paper_trades_task_started",
        task_id=task_id,
        max_holding_days=max_holding_days,
    )

    try:
        storage = get_storage()

        # Update all open paper trades
        stats = update_paper_trades(storage, max_holding_days=max_holding_days)

        logger.info(
            "update_paper_trades_task_completed",
            task_id=task_id,
            **stats,
        )

        return stats

    except Exception as e:
        logger.error(
            "update_paper_trades_task_failed",
            task_id=task_id,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise
