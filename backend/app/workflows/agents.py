"""Agent and workflow orchestration workflows.

Thin async wrappers around existing business logic in tasks/.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from .models import EmptyInput, SymbolInput


@hatchet.task(
    name="portfolio-run-discovery-agent",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["36 3 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-run-discovery-agent'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def run_discovery_agent_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.agent_tasks import run_discovery_agent

    result = await asyncio.to_thread(run_discovery_agent)
    return {"result": result}


@hatchet.task(
    name="portfolio-run-portfolio-analyzer",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["39 3 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-run-portfolio-analyzer'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def run_portfolio_analyzer_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.agent_tasks import run_portfolio_analyzer

    result = await asyncio.to_thread(run_portfolio_analyzer)
    return {"result": result}


@hatchet.task(
    name="portfolio-schedule-new-symbol",
    input_validator=SymbolInput,
    execution_timeout="7200s",
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
    r: Any = await asyncio.to_thread(ingest_historical_ohlcv, symbols=[input.symbol], days=252)
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
