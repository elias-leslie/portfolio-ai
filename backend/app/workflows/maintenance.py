"""Maintenance & cleanup workflows.

Thin async wrappers around existing business logic in tasks/.
Hatchet workflows with cron scheduling.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from .models import CleanupInput, EmptyInput, WatchlistInput


@hatchet.task(
    name="portfolio-vacuum-db",
    input_validator=EmptyInput,
    execution_timeout="7200s",
    retries=1,
    on_crons=["30 3 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-vacuum-db'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def vacuum_db_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.maintenance_tasks import vacuum_database_task

    return await asyncio.to_thread(vacuum_database_task)


@hatchet.task(
    name="portfolio-cleanup-news",
    input_validator=CleanupInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["0 4 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-news'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_news_wf(input: CleanupInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.maintenance_tasks import cleanup_old_news_task

    return await asyncio.to_thread(cleanup_old_news_task, days=input.days or 90, dry_run=input.dry_run)


@hatchet.task(
    name="portfolio-cleanup-agent-runs",
    input_validator=CleanupInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["15 4 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-agent-runs'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_old_agent_runs_wf(input: CleanupInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.maintenance_tasks import cleanup_old_agent_runs_task

    return await asyncio.to_thread(cleanup_old_agent_runs_task, days=input.days or 30, dry_run=input.dry_run)


@hatchet.task(
    name="portfolio-cleanup-orphaned",
    input_validator=CleanupInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["30 4 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-orphaned'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_orphaned_wf(input: CleanupInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.maintenance_tasks import cleanup_orphaned_data_task

    return await asyncio.to_thread(cleanup_orphaned_data_task, dry_run=input.dry_run)


@hatchet.task(
    name="portfolio-cleanup-backups",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["45 4 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-backups'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_old_backups_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.cleanup.artifact_cleanup import cleanup_old_backups_task

    return await asyncio.to_thread(cleanup_old_backups_task)


@hatchet.task(
    name="portfolio-cleanup-models",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["5 5 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-models'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_old_models_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.cleanup.artifact_cleanup import cleanup_old_models_task

    return await asyncio.to_thread(cleanup_old_models_task)


@hatchet.task(
    name="portfolio-cleanup-solution-state",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["25 5 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-solution-state'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_solution_state_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.cleanup.artifact_cleanup import cleanup_solution_state_task

    return await asyncio.to_thread(cleanup_solution_state_task)


@hatchet.task(
    name="portfolio-db-size",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=1,
    on_crons=["36 5 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-db-size'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def db_size_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.maintenance_tasks import get_database_size_task

    return await asyncio.to_thread(get_database_size_task)


@hatchet.task(
    name="portfolio-cleanup-logs",
    input_validator=CleanupInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["0 2 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-logs'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_old_logs_wf(input: CleanupInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.cleanup.log_cleanup import cleanup_old_logs_task

    return await asyncio.to_thread(cleanup_old_logs_task, days=input.days or 7, dry_run=input.dry_run)


@hatchet.task(
    name="portfolio-cleanup-temp",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["15 2 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-temp'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_temp_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.cleanup.temp_cleanup import cleanup_temp_files_task

    return await asyncio.to_thread(cleanup_temp_files_task)


@hatchet.task(
    name="portfolio-check-disk",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=1,
    on_crons=["0 */6 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-check-disk'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def check_disk_space_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.cleanup.disk_monitoring import check_disk_space_task

    return await asyncio.to_thread(check_disk_space_task)


@hatchet.task(
    name="portfolio-data-freshness",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=3,
    backoff_factor=2.0,
    on_crons=["0 */2 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-data-freshness'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def maintain_data_freshness_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.data_freshness_tasks import maintain_data_freshness

    return await asyncio.to_thread(maintain_data_freshness)


@hatchet.task(
    name="portfolio-check-freshness",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=3,
    backoff_factor=2.0,
    on_crons=["0 */2 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-check-freshness'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def check_all_data_freshness_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.data_freshness_tasks import check_all_data_freshness

    return await asyncio.to_thread(check_all_data_freshness)


@hatchet.task(
    name="portfolio-source-health",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["30 */6 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-source-health'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def check_data_source_health_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.source_health_tasks import check_data_source_health

    return await asyncio.to_thread(check_data_source_health)


@hatchet.task(
    name="portfolio-cleanup-debug",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["15 6 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-debug'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_debug_captures_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.artifact_tasks import cleanup_debug_captures

    return await asyncio.to_thread(cleanup_debug_captures)


@hatchet.task(
    name="portfolio-cleanup-versions",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["0 6 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-cleanup-versions'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def cleanup_old_versions_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.artifact_tasks import cleanup_old_versions

    return await asyncio.to_thread(cleanup_old_versions)


@hatchet.task(
    name="portfolio-reset-source-metrics",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=1,
)
async def reset_source_metrics_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.news_profiling_tasks import reset_source_metrics_task

    return await asyncio.to_thread(reset_source_metrics_task)


@hatchet.task(
    name="portfolio-profile-news",
    input_validator=WatchlistInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["0 */12 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-profile-news'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def profile_news_wf(input: WatchlistInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.news_profiling_tasks import profile_news_sources_task

    return await asyncio.to_thread(profile_news_sources_task, user_id=input.user_id)
