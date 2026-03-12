"""Monitoring and thesis workflows.

Thin async wrappers around existing business logic in tasks/.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from .models import EmptyInput


@hatchet.task(
    name="portfolio-monitor-theses",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["0 3 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-monitor-theses'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def monitor_theses_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.thesis_monitoring_tasks import monitor_thesis_health_task

    return await asyncio.to_thread(monitor_thesis_health_task)
