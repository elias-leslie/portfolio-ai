"""Strategy, signals & portfolio workflows.

Thin async wrappers around existing business logic in tasks/.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, cast

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from app.logging_config import get_logger
from app.services.preferences_service import get_automation_preferences

from ..hatchet_app import hatchet
from ..utils.market_hours import NY_TZ, is_trading_day
from .models import EmptyInput, SeedInput, StrategyInput

logger = get_logger(__name__)

# Shared skip result for non-trading-day early exits
_SKIP_NON_TRADING_DAY = {"status": "skipped", "reason": "Not a trading day (weekend/holiday)"}


def _skip_if_not_trading_day(task_name: str) -> dict[str, Any] | None:
    """Return skip result if today is not a trading day, else None."""
    if not is_trading_day():
        logger.info("skipping_non_trading_day", task_name=task_name)
        return _SKIP_NON_TRADING_DAY
    return None


def _skip_weekly_with_holiday_fallback(task_name: str) -> dict[str, Any] | None:
    """Gate weekly jobs that run on Mon/Tue crons with holiday-Monday fallback.

    - Monday + trading day → run
    - Tuesday + Monday was NOT a trading day → run (holiday fallback)
    - Otherwise → skip
    """
    now = datetime.now(NY_TZ)
    weekday = now.weekday()  # 0=Mon, 1=Tue

    if weekday == 0:
        # Monday: run only if it's a trading day
        if is_trading_day():
            return None
        logger.info("skipping_monday_not_trading_day", task_name=task_name)
        return _SKIP_NON_TRADING_DAY

    if weekday == 1:
        # Tuesday: run only if Monday was a holiday (i.e. Monday was skipped)
        monday = (now - timedelta(days=1)).date()
        if not is_trading_day(check_date=monday):
            if is_trading_day():
                logger.info("running_tuesday_holiday_fallback", task_name=task_name)
                return None
            logger.info("skipping_tuesday_not_trading_day", task_name=task_name)
            return _SKIP_NON_TRADING_DAY
        logger.info("skipping_tuesday_fallback_not_needed", task_name=task_name)
        return {"status": "skipped", "reason": "Tuesday fallback not needed"}

    # Should not happen with Mon/Tue cron, but guard anyway
    logger.info("skipping_not_scheduled_day", task_name=task_name)
    return {"status": "skipped", "reason": "Not scheduled day"}


def _skip_if_strategy_research_disabled(task_name: str) -> dict[str, Any] | None:
    automation = get_automation_preferences()
    if bool(automation["scheduled_strategy_research_enabled"]["enabled"]):
        return None
    logger.info("skipping_strategy_research_disabled", task_name=task_name)
    return {"status": "skipped", "reason": "scheduled_strategy_research_disabled"}


@hatchet.task(
    name="portfolio-eval-strategy",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["0 4 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-eval-strategy'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def eval_strategy_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.strategy.performance_tasks import evaluate_strategy_performance

    return cast(dict[str, Any], await asyncio.to_thread(evaluate_strategy_performance))


@hatchet.task(
    name="portfolio-auto-promote",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["15 4 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-auto-promote'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def auto_promote_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.strategy.performance_tasks import auto_promote_strategies

    return cast(dict[str, Any], await asyncio.to_thread(auto_promote_strategies))


@hatchet.task(
    name="portfolio-daily-strategy",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["15 5 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-daily-strategy'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def daily_strategy_refresh_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    if skip := _skip_if_strategy_research_disabled("daily-strategy-refresh"):
        return skip
    if skip := _skip_if_not_trading_day("daily-strategy-refresh"):
        return skip
    from ..tasks.strategy.generation_tasks import daily_strategy_refresh

    return await asyncio.to_thread(daily_strategy_refresh)


@hatchet.task(
    name="portfolio-weekly-strategy-gen",
    input_validator=EmptyInput,
    execution_timeout="7200s",
    retries=1,
    on_crons=["0 5 * * 1,2"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-weekly-strategy-gen'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def weekly_strategy_gen_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    if skip := _skip_if_strategy_research_disabled("weekly-strategy-gen"):
        return skip
    if skip := _skip_weekly_with_holiday_fallback("weekly-strategy-gen"):
        return skip
    from ..tasks.strategy.generation_tasks import weekly_strategy_generation

    return cast(dict[str, Any], await asyncio.to_thread(weekly_strategy_generation))


@hatchet.task(
    name="portfolio-weekly-evolution",
    input_validator=EmptyInput,
    execution_timeout="7200s",
    retries=1,
    on_crons=["0 6 * * 1,2"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-weekly-evolution'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def weekly_evolution_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    if skip := _skip_if_strategy_research_disabled("weekly-evolution"):
        return skip
    if skip := _skip_weekly_with_holiday_fallback("weekly-evolution"):
        return skip
    from ..tasks.strategy.evolution_tasks import weekly_strategy_evolution

    return await asyncio.to_thread(weekly_strategy_evolution)


@hatchet.task(
    name="portfolio-daily-signals",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["30 21 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-daily-signals'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def daily_signals_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    if skip := _skip_if_not_trading_day("daily-signals"):
        return skip
    from ..tasks.strategy_signal_tasks import generate_daily_strategy_signals

    return await asyncio.to_thread(generate_daily_strategy_signals)


@hatchet.task(
    name="portfolio-auto-paper-trade",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["45 21 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-auto-paper-trade'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def auto_paper_trade_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    if skip := _skip_if_not_trading_day("auto-paper-trade"):
        return skip
    from ..tasks.strategy_signal_tasks import auto_paper_trade_from_signals

    return await asyncio.to_thread(auto_paper_trade_from_signals)


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


@hatchet.task(
    name="portfolio-trigger-from-seed",
    input_validator=SeedInput,
    execution_timeout="3600s",
    retries=1,
    concurrency=ConcurrencyExpression(
        expression="input.seed_id",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def trigger_from_seed_wf(input: SeedInput, ctx: Context) -> dict[str, Any]:
    if skip := _skip_if_strategy_research_disabled("trigger-from-seed"):
        return skip
    if skip := _skip_if_not_trading_day("trigger-from-seed"):
        return skip
    from ..tasks.strategy.generation_tasks import trigger_strategy_from_seed

    return await asyncio.to_thread(trigger_strategy_from_seed, seed_id=input.seed_id, symbol=input.symbol)


@hatchet.task(
    name="portfolio-trigger-top-strategies",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-trigger-top-strategies'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def trigger_top_strategies_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    if skip := _skip_if_strategy_research_disabled("trigger-top-strategies"):
        return skip
    if skip := _skip_if_not_trading_day("trigger-top-strategies"):
        return skip
    from ..tasks.strategy.generation_tasks import trigger_strategies_for_top_watchlist

    return await asyncio.to_thread(trigger_strategies_for_top_watchlist)


@hatchet.task(
    name="portfolio-generate-signal",
    input_validator=StrategyInput,
    execution_timeout="1800s",
    retries=1,
    concurrency=ConcurrencyExpression(
        expression="input.strategy_id",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def generate_signal_wf(input: StrategyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.strategy_signal_tasks import generate_signal_for_strategy_task

    return await asyncio.to_thread(
        generate_signal_for_strategy_task, strategy_id=input.strategy_id, symbol=input.symbol or ""
    )


@hatchet.task(
    name="portfolio-strategy-metrics",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["0 22 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-strategy-metrics'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def strategy_metrics_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.strategy_metrics_tasks import collect_daily_strategy_metrics

    return await asyncio.to_thread(collect_daily_strategy_metrics)
