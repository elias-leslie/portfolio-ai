"""Research universe refresh workflow (S&P 500).

Weekly Hatchet workflow that reconciles ``research_universe_symbols``
against the upstream constituent feeds. Schedule: Mon 06:00 ET.

After membership reconciliation, the workflow chains
``portfolio-ingest-ohlcv`` against any newly-added or reactivated symbols
so the L2 scanner has the ~252 trading days of bars it needs to score
them on the next ``macro_gate`` → ``scanner`` chain. Continuing-member
prices are kept fresh by the daily ``portfolio-refresh-ohlcv`` job.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..constants import TRADING_DAYS_PER_YEAR
from ..hatchet_app import hatchet
from ..services import research_universe as universe_service
from .models import EmptyInput, SymbolsInput

RESEARCH_UNIVERSE_CRONS = ["0 11 * * 1"]  # Mon 06:00 ET == 11:00 UTC (DST-conservative; cron is UTC)

# Trading-day lookback for new-arrival backfill. Scanner's longest factor
# (52WHighProximity) needs ~252 bars; the scanner service itself fetches
# 260 with a buffer.
NEW_ARRIVAL_BACKFILL_DAYS = TRADING_DAYS_PER_YEAR


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
    new_symbols = sorted({*result.added_symbols, *result.reactivated_symbols})

    if new_symbols:
        # Lazy import to avoid cyclic registration at Hatchet boot.
        from .data_refresh import ingest_ohlcv_wf

        await ingest_ohlcv_wf.aio_run_no_wait(
            SymbolsInput(symbols=new_symbols, days=NEW_ARRIVAL_BACKFILL_DAYS),
        )

    return {
        "added": result.added,
        "reactivated": result.reactivated,
        "departed": result.departed,
        "active_count": result.active_count,
        "source": result.source,
        "backfill_symbols": len(new_symbols),
    }
