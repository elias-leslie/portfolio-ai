"""Macro economic calendar ingestion workflow."""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from app.tasks.market_data.macro_calendar_pipeline import ingest_macro_calendar_events

from ..hatchet_app import hatchet
from .data_refresh_schedules import MACRO_CALENDAR_INGESTION_CRONS
from .models import EmptyInput


@hatchet.task(
    name="portfolio-market-macro-calendar-ingestion",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=2,
    on_crons=MACRO_CALENDAR_INGESTION_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-market-macro-calendar-ingestion'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def market_macro_calendar_ingestion_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    return await asyncio.to_thread(ingest_macro_calendar_events)
