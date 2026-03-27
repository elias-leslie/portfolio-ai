"""Maintenance & cleanup workflows.

Thin async wrappers around existing business logic in tasks/.
Hatchet workflows with cron scheduling.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, cast

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from ..tasks.artifact_tasks import cleanup_debug_captures
from ..tasks.cleanup.artifact_cleanup import cleanup_old_backups_task, cleanup_old_models_task
from ..tasks.cleanup.disk_monitoring import check_disk_space_task
from ..tasks.cleanup.log_cleanup import cleanup_old_logs_task, rotate_logs_task
from ..tasks.cleanup.temp_cleanup import cleanup_temp_files_task
from ..tasks.data_freshness_tasks import check_all_data_freshness, maintain_data_freshness
from ..tasks.maintenance_tasks import (
    cleanup_maintenance_tables_task,
    cleanup_old_agent_runs_task,
    cleanup_old_news_task,
    cleanup_old_watchlist_snapshots_task,
    cleanup_orphaned_data_task,
    get_database_size_task,
    vacuum_database_task,
)
from ..tasks.news_profiling_tasks import profile_news_sources_task, reset_source_metrics_task
from ..tasks.source_health_tasks import check_data_source_health
from .models import CleanupInput, EmptyInput, WatchlistInput


def _concurrency(name: str) -> ConcurrencyExpression:
    return ConcurrencyExpression(
        expression=f"'{name}'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    )


def _empty_wf(
    name: str,
    timeout: str,
    crons: list[str],
    fn: Callable[[], Any],
    *,
    retries: int = 1,
    backoff_factor: float | None = None,
) -> Any:
    kw: dict[str, Any] = {"on_crons": crons}
    if backoff_factor is not None:
        kw["backoff_factor"] = backoff_factor

    @hatchet.task(
        name=name,
        input_validator=EmptyInput,
        execution_timeout=timeout,
        retries=retries,
        concurrency=_concurrency(name),
        **kw,
    )
    async def _wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
        return await asyncio.to_thread(fn)

    return _wf


def _cleanup_wf(
    name: str,
    timeout: str,
    crons: list[str],
    fn: Callable[..., Any],
    default_days: int | None = None,
) -> Any:
    @hatchet.task(
        name=name,
        input_validator=CleanupInput,
        execution_timeout=timeout,
        retries=1,
        on_crons=crons,
        concurrency=_concurrency(name),
    )
    async def _wf(input: CleanupInput, ctx: Context) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"dry_run": input.dry_run}
        if default_days is not None:
            kwargs["days"] = input.days or default_days
        return await asyncio.to_thread(fn, **kwargs)

    return _wf


rotate_logs_wf = _empty_wf("portfolio-rotate-logs", "1800s", ["45 1 * * *"], rotate_logs_task)
vacuum_db_wf = _empty_wf("portfolio-vacuum-db", "7200s", ["30 3 * * 0"], vacuum_database_task)
db_size_wf = _empty_wf("portfolio-db-size", "600s", ["36 5 * * *"], get_database_size_task)
cleanup_old_backups_wf = _empty_wf(
    "portfolio-cleanup-backups", "3600s", ["45 4 * * 0"], cleanup_old_backups_task
)
cleanup_old_models_wf = _empty_wf(
    "portfolio-cleanup-models", "3600s", ["5 5 * * 0"], cleanup_old_models_task
)
cleanup_temp_wf = _empty_wf(
    "portfolio-cleanup-temp", "1800s", ["15 2 * * *"], cleanup_temp_files_task
)
check_disk_space_wf = _empty_wf(
    "portfolio-check-disk", "600s", ["0 */6 * * *"], check_disk_space_task
)
check_data_source_health_wf = _empty_wf(
    "portfolio-source-health", "1800s", ["30 */6 * * *"], check_data_source_health
)
cleanup_debug_captures_wf = _empty_wf(
    "portfolio-cleanup-debug", "1800s", ["15 6 * * *"], cleanup_debug_captures
)
maintain_data_freshness_wf = _empty_wf(
    "portfolio-data-freshness", "1800s", ["0 */2 * * *"], maintain_data_freshness,
    retries=3, backoff_factor=2.0,
)
check_all_data_freshness_wf = _empty_wf(
    "portfolio-check-freshness", "1800s", ["0 */2 * * *"], check_all_data_freshness,
    retries=3, backoff_factor=2.0,
)
cleanup_news_wf = _cleanup_wf(
    "portfolio-cleanup-news", "3600s", ["0 4 * * 0"], cleanup_old_news_task, 90
)
cleanup_old_agent_runs_wf = _cleanup_wf(
    "portfolio-cleanup-agent-runs", "3600s", ["15 4 * * 0"], cleanup_old_agent_runs_task, 30
)
cleanup_orphaned_wf = _cleanup_wf(
    "portfolio-cleanup-orphaned", "3600s", ["30 4 * * 0"], cleanup_orphaned_data_task
)
cleanup_snapshots_wf = _cleanup_wf(
    "portfolio-cleanup-snapshots", "3600s", ["0 5 * * 0"], cleanup_old_watchlist_snapshots_task, 60
)
cleanup_maintenance_wf = _cleanup_wf(
    "portfolio-cleanup-maintenance", "3600s", ["30 5 * * 0"], cleanup_maintenance_tables_task, 90
)
cleanup_old_logs_wf = _cleanup_wf(
    "portfolio-cleanup-logs", "1800s", ["0 2 * * *"], cleanup_old_logs_task, 7
)


@hatchet.task(
    name="portfolio-reset-source-metrics",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=1,
)
async def reset_source_metrics_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    return cast(dict[str, Any], await asyncio.to_thread(reset_source_metrics_task))


@hatchet.task(
    name="portfolio-profile-news",
    input_validator=WatchlistInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["0 */12 * * *"],
    concurrency=_concurrency("portfolio-profile-news"),
)
async def profile_news_wf(input: WatchlistInput, ctx: Context) -> dict[str, Any]:
    return cast(dict[str, Any], await asyncio.to_thread(profile_news_sources_task, user_id=input.user_id))
