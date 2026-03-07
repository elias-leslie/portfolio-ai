"""Multi-agent workflow tasks for autonomous trading intelligence.

This module is the public API surface for workflow tasks. Implementation
details live in the sibling modules:
  - workflow_tasks_helpers.py - shared helper utilities
  - workflow_tasks_gap.py     - daily gap analysis workflow
  - workflow_tasks_trade.py   - paper trade validation workflow
"""

from __future__ import annotations

# Re-export top-level module symbols that tests and callers may patch
from app.agents.llm_client import DualProviderClient
from app.agents.tools import AgentTools
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.logging_config import get_logger
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services import NewsService
from app.sources.fred import FREDSource
from app.storage.facade import PortfolioStorage
from app.tasks import (
    workflow_tasks_gap,
    workflow_tasks_helpers,
    workflow_tasks_trade,
    workflow_tasks_trade_agents,
    workflow_tasks_trade_backtest,
)

# Re-export helpers so existing callers continue to work
from app.tasks.workflow_tasks_helpers import (
    _commit_workflow_to_git,
    _execute_agent_with_error_handling,
    _get_available_data_range,
    _setup_agent_tools,
)
from app.utils.git_automation import commit_workflow_results

logger = get_logger(__name__)

__all__ = [
    "AgentTools",
    "DualProviderClient",
    "FREDSource",
    "NewsService",
    "PortfolioAnalytics",
    "PortfolioManager",
    "PortfolioStorage",
    "PriceDataFetcher",
    "WorkflowOrchestrator",
    "_commit_workflow_to_git",
    "_execute_agent_with_error_handling",
    "_get_available_data_range",
    "_setup_agent_tools",
    "commit_workflow_results",
    "daily_gap_analysis_workflow",
    "paper_trade_validation_workflow",
    "research_corroboration_workflow",
]


def _sync_gap_dependencies() -> None:
    """Keep the compatibility module patchable for tests and callers."""
    workflow_tasks_gap.DualProviderClient = DualProviderClient
    workflow_tasks_gap.PortfolioStorage = PortfolioStorage
    workflow_tasks_gap.WorkflowOrchestrator = WorkflowOrchestrator
    workflow_tasks_helpers.commit_workflow_results = commit_workflow_results
    workflow_tasks_gap._commit_workflow_to_git = _commit_workflow_to_git
    workflow_tasks_gap._execute_agent_with_error_handling = _execute_agent_with_error_handling


def _sync_trade_dependencies() -> None:
    """Keep the compatibility module patchable for tests and callers."""
    workflow_tasks_helpers.AgentTools = AgentTools
    workflow_tasks_helpers.NewsService = NewsService
    workflow_tasks_helpers.FREDSource = FREDSource
    workflow_tasks_helpers.PriceDataFetcher = PriceDataFetcher
    workflow_tasks_helpers.PortfolioManager = PortfolioManager
    workflow_tasks_helpers.PortfolioAnalytics = PortfolioAnalytics
    workflow_tasks_helpers.PortfolioStorage = PortfolioStorage
    workflow_tasks_helpers.commit_workflow_results = commit_workflow_results

    workflow_tasks_trade.DualProviderClient = DualProviderClient
    workflow_tasks_trade.PortfolioStorage = PortfolioStorage
    workflow_tasks_trade.WorkflowOrchestrator = WorkflowOrchestrator
    workflow_tasks_trade._setup_agent_tools = _setup_agent_tools
    workflow_tasks_trade._commit_workflow_to_git = _commit_workflow_to_git
    workflow_tasks_trade_backtest._setup_agent_tools = _setup_agent_tools
    workflow_tasks_trade_backtest._get_available_data_range = _get_available_data_range
    workflow_tasks_trade_backtest._resolve_strategy_params = workflow_tasks_helpers._resolve_strategy_params
    workflow_tasks_trade_agents.DualProviderClient = DualProviderClient


def daily_gap_analysis_workflow() -> dict[str, object]:
    """Compatibility wrapper that preserves module-level patch seams."""
    _sync_gap_dependencies()
    return workflow_tasks_gap.daily_gap_analysis_workflow()


def paper_trade_validation_workflow(
    strategy_id: str, symbol: str, action: str, thesis: str
) -> dict[str, object]:
    """Compatibility wrapper that preserves module-level patch seams."""
    _sync_trade_dependencies()
    return workflow_tasks_trade.paper_trade_validation_workflow(
        strategy_id=strategy_id,
        symbol=symbol,
        action=action,
        thesis=thesis,
    )


def research_corroboration_workflow(topic: str, sources: list[str]) -> dict[str, object]:
    """Multi-agent research corroboration workflow (placeholder for future implementation)."""
    logger.info(f"Research corroboration workflow placeholder: {topic}")
    return {"status": "not_implemented", "topic": topic}
