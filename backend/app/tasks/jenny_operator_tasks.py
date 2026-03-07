"""Jenny operator task wrappers.

Thin wrappers so Hatchet schedules call the same service layer as the API.
"""

from __future__ import annotations

from typing import Any

from app.services.jenny_operator_service import JennyOperatorService


def run_daily_operator_task() -> dict[str, Any]:
    """Run Jenny's daily operator review."""
    result = JennyOperatorService().run_daily_operator(triggered_by="scheduled")
    return result.model_dump()


def run_weekly_learning_task() -> dict[str, Any]:
    """Run Jenny's weekly learning and scorecard refresh."""
    result = JennyOperatorService().run_weekly_learning(triggered_by="scheduled")
    return result.model_dump()
