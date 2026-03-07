"""Background tasks for agent execution.

This module defines background tasks for:
- Running AI agents (Discovery, Portfolio Analyzer)

For other background tasks, see:
- watchlist_tasks.py - Watchlist score refresh
- data_ingestion_tasks.py - Historical OHLCV data ingestion
- indicator_tasks.py - Technical indicator calculations
"""

from __future__ import annotations

from app.tasks.agent_helpers import run_agent_task

__all__ = [
    "run_discovery_agent",
    "run_portfolio_analyzer",
]


def run_discovery_agent() -> str:
    """Run discovery agent as a background task.

    Returns:
        Run ID of the agent execution
    """
    from app.agents.discovery import DiscoveryAgent

    return run_agent_task(
        agent_class=DiscoveryAgent,
        task_name="discovery_agent",
        context_type="discovery_analysis",
        confidence=0.8,
    )


def run_portfolio_analyzer() -> str:
    """Run portfolio analyzer agent as a background task.

    Returns:
        Run ID of the agent execution
    """
    from app.agents.portfolio_analyzer import PortfolioAnalyzerAgent

    return run_agent_task(
        agent_class=PortfolioAnalyzerAgent,
        task_name="portfolio_analyzer",
        context_type="portfolio_analysis",
        confidence=0.85,
    )
