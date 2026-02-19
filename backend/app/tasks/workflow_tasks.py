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

# Re-export public workflow functions
from app.tasks.workflow_tasks_gap import daily_gap_analysis_workflow

# Re-export helpers so existing callers continue to work
from app.tasks.workflow_tasks_helpers import (
    _commit_workflow_to_git,
    _execute_agent_with_error_handling,
    _get_available_data_range,
    _setup_agent_tools,
)
from app.tasks.workflow_tasks_trade import paper_trade_validation_workflow
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


def research_corroboration_workflow(topic: str, sources: list[str]) -> dict[str, object]:
    """Multi-agent research corroboration workflow (placeholder for future implementation)."""
    logger.info(f"Research corroboration workflow placeholder: {topic}")
    return {"status": "not_implemented", "topic": topic}
