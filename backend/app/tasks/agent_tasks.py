"""Background tasks for agent execution and paper trading.

This module defines background tasks for:
- Running AI agents (Discovery, Portfolio Analyzer)
- Updating paper trades

For other background tasks, see:
- watchlist_tasks.py - Watchlist score refresh
- data_ingestion_tasks.py - Historical OHLCV data ingestion
- indicator_tasks.py - Technical indicator calculations
"""

from __future__ import annotations

from app.tasks.agent_helpers import run_agent_task, run_paper_trades_update

__all__ = [
    "run_discovery_agent",
    "run_portfolio_analyzer",
    "update_paper_trades_task",
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


def update_paper_trades_task(max_holding_days: int = 60):  # type: ignore[no-untyped-def]
    """Update all open paper trades with current prices and check for exits.

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
    """
    return run_paper_trades_update(max_holding_days=max_holding_days)
