"""Jenny operator workflows.

Thin async wrappers around Jenny operator routines.
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


@hatchet.task(
    name="portfolio-jenny-daily-operator",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["15 22 * * 1-5"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-jenny-daily-operator'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def jenny_daily_operator_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    if not is_trading_day():
        logger.info("jenny_daily_operator_skipped_non_trading_day")
        return {"status": "skipped", "reason": "Not a trading day (holiday)"}
    from ..tasks.jenny_operator_tasks import run_daily_operator_task

    return await asyncio.to_thread(run_daily_operator_task)


@hatchet.task(
    name="portfolio-jenny-weekly-learning",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["0 14 * * 6"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-jenny-weekly-learning'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def jenny_weekly_learning_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.jenny_operator_tasks import run_weekly_learning_task

    return await asyncio.to_thread(run_weekly_learning_task)
