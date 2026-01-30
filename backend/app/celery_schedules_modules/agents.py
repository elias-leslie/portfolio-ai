"""Autonomous AI agent tasks."""

from typing import Any

from celery.schedules import crontab

from .constants import EXPIRY_30_MIN


def get_tasks() -> dict[str, dict[str, Any]]:
    """Autonomous AI agent tasks.

    Discovery Agent and Portfolio Analyzer generate investment ideas daily
    at 03:30 UTC to fulfill VISION.md requirement for autonomous scheduling.

    Returns:
        Dict of Celery Beat task definitions for AI agent tasks
    """
    return {
        "run-discovery-agent-daily": {
            "task": "run_discovery_agent",
            "schedule": crontab(hour=3, minute=36),  # Daily at 03:36 UTC (staggered)
            "options": {"expires": EXPIRY_30_MIN},  # 30-minute expiry
        },
        "run-portfolio-analyzer-daily": {
            "task": "run_portfolio_analyzer",
            "schedule": crontab(hour=3, minute=39),  # Daily at 03:39 UTC (staggered)
            "options": {"expires": EXPIRY_30_MIN},  # 30-minute expiry
        },
    }
