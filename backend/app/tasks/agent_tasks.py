"""Celery tasks for agent execution.

This module defines background tasks for running AI agents asynchronously.
"""

from __future__ import annotations

from app.agents.discovery import DiscoveryAgent
from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent
from app.agents.tools import AgentTools
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.sources.fred import FREDSource
from app.sources.news import GoogleNewsSource
from app.storage import get_storage

logger = get_logger(__name__)


@celery_app.task(name="run_discovery_agent", bind=True)  # type: ignore[misc]
def run_discovery_agent(self) -> str:  # type: ignore[no-untyped-def]
    """Run discovery agent as a background task.

    Returns:
        Run ID of the agent execution
    """
    task_id = self.request.id
    logger.info(
        "discovery_agent_task_started",
        task_id=task_id,
    )

    try:
        storage = get_storage()

        # Initialize agent tools
        news_source = GoogleNewsSource()
        fred_source = FREDSource()
        price_fetcher = PriceDataFetcher(storage)
        portfolio_mgr = PortfolioManager(storage)
        analytics = PortfolioAnalytics()

        agent_tools = AgentTools(
            storage=storage,
            news_source=news_source,
            fred_source=fred_source,
            price_fetcher=price_fetcher,
            portfolio_mgr=portfolio_mgr,
            analytics=analytics,
        )

        agent = DiscoveryAgent(storage=storage, tools=agent_tools)
        result = agent.run()
        run_id = result["run_id"]

        # Update agent_runs with celery_task_id
        with storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET celery_task_id = ?
                WHERE id = ?
                """,
                [task_id, run_id],
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


@celery_app.task(name="run_portfolio_analyzer", bind=True)  # type: ignore[misc]
def run_portfolio_analyzer(self) -> str:  # type: ignore[no-untyped-def]
    """Run portfolio analyzer agent as a background task.

    Returns:
        Run ID of the agent execution
    """
    task_id = self.request.id
    logger.info(
        "portfolio_analyzer_task_started",
        task_id=task_id,
    )

    try:
        storage = get_storage()

        # Initialize agent tools
        news_source = GoogleNewsSource()
        fred_source = FREDSource()
        price_fetcher = PriceDataFetcher(storage)
        portfolio_mgr = PortfolioManager(storage)
        analytics = PortfolioAnalytics()

        agent_tools = AgentTools(
            storage=storage,
            news_source=news_source,
            fred_source=fred_source,
            price_fetcher=price_fetcher,
            portfolio_mgr=portfolio_mgr,
            analytics=analytics,
        )

        agent = PortfolioAnalyzerAgent(storage=storage, tools=agent_tools)
        result = agent.run()
        run_id = result["run_id"]

        # Update agent_runs with celery_task_id
        with storage.connection() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET celery_task_id = ?
                WHERE id = ?
                """,
                [task_id, run_id],
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
