"""Jenny operator workflows.

Thin async wrappers around Jenny operator routines.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from app.logging_config import get_logger
from app.services.preferences_service import get_automation_preferences

from ..hatchet_app import hatchet
from ..utils.market_hours import is_trading_day
from .models import EmptyInput, PriceCheckInput

logger = get_logger(__name__)


@hatchet.task(
    name="portfolio-jenny-daily-operator",
    input_validator=EmptyInput,
    retries=1,
    on_crons=["15 22 * * 1-5"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-jenny-daily-operator'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def jenny_daily_operator_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    automation = get_automation_preferences()
    if not bool(automation["scheduled_jenny_operator_enabled"]["enabled"]):
        logger.info("jenny_daily_operator_skipped_disabled")
        return {"status": "skipped", "reason": "scheduled_jenny_operator_disabled"}
    if not is_trading_day():
        logger.info("jenny_daily_operator_skipped_non_trading_day", evaluated_date=str(date.today()))
        return {"status": "skipped", "reason": "Not a trading day (holiday)"}
    from ..tasks.jenny_operator_tasks import run_daily_operator_task

    return await asyncio.to_thread(run_daily_operator_task)


@hatchet.task(
    name="portfolio-jenny-weekly-learning",
    input_validator=EmptyInput,
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


@hatchet.task(
    name="portfolio-jenny-daily-household-maintenance",
    input_validator=EmptyInput,
    retries=1,
    on_crons=["15 13 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-jenny-daily-household-maintenance'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def jenny_daily_household_maintenance_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.jenny_operator_tasks import run_daily_household_maintenance_task

    return await asyncio.to_thread(run_daily_household_maintenance_task)


@hatchet.task(
    name="portfolio-jenny-weekly-price-check",
    input_validator=PriceCheckInput,
    execution_timeout="3600s",
    retries=0,
    on_crons=["30 13 * * 6"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-jenny-weekly-price-check'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def jenny_weekly_price_check_wf(input: PriceCheckInput, ctx: Context) -> dict[str, Any]:
    """Cross-vendor price check. Cron is gated OFF until the preference flips;
    manual runs arrive with a pre-queued run_id and bypass the gate."""
    from app.services.household_price_check_service import HouseholdPriceCheckService

    service = HouseholdPriceCheckService()
    run_id = input.run_id
    if run_id is None:
        automation = get_automation_preferences()
        if not bool(automation["scheduled_price_check_enabled"]["enabled"]):
            logger.info("price_check_skipped_disabled")
            return {"status": "skipped", "reason": "scheduled_price_check_disabled"}
        run_id, already_running = await asyncio.to_thread(
            lambda: service.start_run(
                triggered_by=input.triggered_by,
                product_limit=input.product_limit,
                product_ids=input.product_ids,
                shopping_list_id=input.shopping_list_id,
            )
        )
        if already_running:
            logger.info("price_check_skipped_already_running", run_id=run_id)
            return {"status": "skipped", "reason": "already_running", "run_id": run_id}
    from ..tasks.jenny_operator_tasks import run_weekly_price_check_task

    return await asyncio.to_thread(run_weekly_price_check_task, run_id)
