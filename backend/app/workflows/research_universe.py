"""Research universe refresh workflow (S&P 500).

Weekly Hatchet workflow that reconciles ``research_universe_symbols``
against the upstream constituent feeds. Schedule: Mon 06:00 ET.

This workflow only manages membership; price-history backfill for new
arrivals is the responsibility of the existing OHLCV refresh chain (new
symbols will pick up data on the next ``portfolio-refresh-ohlcv`` run).
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from ..services import research_universe as universe_service
from .models import EmptyInput

RESEARCH_UNIVERSE_CRONS = ["0 11 * * 1"]  # Mon 06:00 ET == 11:00 UTC (DST-conservative; cron is UTC)


@hatchet.task(
    name="portfolio-research-universe-refresh",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=2,
    backoff_factor=2.0,
    on_crons=RESEARCH_UNIVERSE_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-research-universe-refresh'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def research_universe_refresh_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    result = await asyncio.to_thread(universe_service.refresh_universe)
    return {
        "added": result.added,
        "reactivated": result.reactivated,
        "departed": result.departed,
        "active_count": result.active_count,
        "source": result.source,
    }
