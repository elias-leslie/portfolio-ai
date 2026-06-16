"""Recurring household property valuation refresh workflow."""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from .data_refresh_schedules import PROPERTY_VALUATION_CRONS
from .models import EmptyInput


@hatchet.task(
    name="portfolio-refresh-property-valuations",
    input_validator=EmptyInput,
    execution_timeout="900s",
    retries=1,
    on_crons=PROPERTY_VALUATION_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-refresh-property-valuations'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def refresh_property_valuations_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from app.services.household_finance_service import HouseholdFinanceService

    return await asyncio.to_thread(
        HouseholdFinanceService().refresh_due_property_valuations,
        max_age_days=30,
    )
