"""Agent orchestration workflows."""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..constants import TRADING_DAYS_PER_YEAR
from ..hatchet_app import hatchet
from .models import SymbolInput


@hatchet.task(
    name="portfolio-schedule-new-symbol",
    input_validator=SymbolInput,
    retries=1,
    concurrency=ConcurrencyExpression(
        expression="input.symbol",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def schedule_new_symbol_wf(input: SymbolInput, ctx: Context) -> dict[str, Any]:
    """Orchestrating workflow that runs all new-symbol setup steps sequentially.

    Replaces the old schedule_new_symbol_tasks() which used .apply_async(countdown=N)
    for staggered execution. Here we use explicit sequential steps with sleeps.
    """
    from ..tasks.indicators.technical import update_technical_indicators
    from ..tasks.ingestion.fundamental_ingestion import ingest_fundamental_data
    from ..tasks.ingestion.price_ingestion import ingest_historical_ohlcv
    from ..tasks.reference_tasks import refresh_yfinance_reference_data
    from ..tasks.watchlist_tasks import refresh_single_symbol_scores_task

    results: dict[str, Any] = {"symbol": input.symbol, "steps": []}

    # Step 1: Ingest historical OHLCV
    r: Any = await asyncio.to_thread(ingest_historical_ohlcv, symbols=[input.symbol], days=TRADING_DAYS_PER_YEAR)
    results["steps"].append({"step": "ingest_ohlcv", "result": r})
    await asyncio.sleep(5)

    # Step 2: Ingest fundamentals
    r = await asyncio.to_thread(ingest_fundamental_data, symbols=[input.symbol])
    results["steps"].append({"step": "ingest_fundamentals", "result": r})
    await asyncio.sleep(5)

    # Step 3: Refresh reference data
    r = await asyncio.to_thread(refresh_yfinance_reference_data)
    results["steps"].append({"step": "refresh_reference", "result": r})
    await asyncio.sleep(5)

    # Step 4: Update technical indicators
    r = await asyncio.to_thread(update_technical_indicators, symbols=[input.symbol])
    results["steps"].append({"step": "update_indicators", "result": r})
    await asyncio.sleep(5)

    # Step 5: Refresh watchlist scores for this symbol
    r = await asyncio.to_thread(refresh_single_symbol_scores_task, symbol=input.symbol)
    results["steps"].append({"step": "refresh_scores", "result": r})

    return results
