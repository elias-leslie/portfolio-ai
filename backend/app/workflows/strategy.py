"""Strategy, signals & portfolio workflows.

Thin async wrappers around existing business logic in tasks/.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from .models import EmptyInput, SeedInput, StrategyInput, SymbolInput


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

    return await asyncio.to_thread(evaluate_strategy_performance)


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

    return await asyncio.to_thread(auto_promote_strategies)


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
    from ..tasks.strategy.generation_tasks import daily_strategy_refresh

    return await asyncio.to_thread(daily_strategy_refresh)


@hatchet.task(
    name="portfolio-weekly-strategy-gen",
    input_validator=EmptyInput,
    execution_timeout="7200s",
    retries=1,
    on_crons=["0 5 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-weekly-strategy-gen'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def weekly_strategy_gen_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.strategy.generation_tasks import weekly_strategy_generation

    return await asyncio.to_thread(weekly_strategy_generation)


@hatchet.task(
    name="portfolio-weekly-evolution",
    input_validator=EmptyInput,
    execution_timeout="7200s",
    retries=1,
    on_crons=["0 6 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-weekly-evolution'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def weekly_evolution_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
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
    from ..tasks.portfolio_tasks import update_portfolio_covariance

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
