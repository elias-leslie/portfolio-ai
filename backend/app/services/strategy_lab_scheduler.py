"""APScheduler setup for Strategy Lab evaluator."""

from __future__ import annotations

from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services.strategy_lab_evaluator import EVALUATION_INTERVAL_MINUTES, StrategyLabEvaluator


def create_strategy_lab_scheduler(evaluator: StrategyLabEvaluator | None = None) -> Any:
    """Create APScheduler async scheduler for Strategy Lab evaluation."""
    service = evaluator or StrategyLabEvaluator()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        service.evaluate_all_active_strategies,
        "interval",
        minutes=EVALUATION_INTERVAL_MINUTES,
        id="strategy_lab_evaluator",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler
