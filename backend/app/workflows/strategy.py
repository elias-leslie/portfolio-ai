"""Surviving portfolio + universe-refresh workflows.

Short-term strategy generation, evolution, signals, and screening were
removed when the project pivoted away from per-strategy backtesting.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from app.logging_config import get_logger

from ..hatchet_app import hatchet
from ..utils.market_hours import is_trading_day
from .models import EmptyInput

logger = get_logger(__name__)

_SKIP_NON_TRADING_DAY = {"status": "skipped", "reason": "Not a trading day (weekend/holiday)"}


def _skip_if_not_trading_day(task_name: str) -> dict[str, Any] | None:
    if not is_trading_day():
        logger.info("skipping_non_trading_day", task_name=task_name)
        return _SKIP_NON_TRADING_DAY
    return None


@hatchet.task(
    name="portfolio-snapshots",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["33 21 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-snapshots'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def portfolio_snapshots_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.portfolio_tasks import save_portfolio_snapshots_task

    return await asyncio.to_thread(save_portfolio_snapshots_task)


@hatchet.task(
    name="portfolio-covariance",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["30 5 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-covariance'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def covariance_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.ingestion.analytics_ingestion import update_portfolio_covariance

    return await asyncio.to_thread(update_portfolio_covariance)


@hatchet.task(
    name="portfolio-rules-validation",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["8 3 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-rules-validation'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def rules_validation_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.rules_validation_tasks import daily_rules_validation

    return await asyncio.to_thread(daily_rules_validation)


@hatchet.task(
    name="portfolio-weekly-optimization",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["10 3 * * 1"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-weekly-optimization'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def weekly_optimization_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.rules_validation_tasks import weekly_optimization_review

    return await asyncio.to_thread(weekly_optimization_review)


