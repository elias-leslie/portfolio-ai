"""Data refresh & market data workflows.

Thin async wrappers around existing business logic in tasks/.
"""

from __future__ import annotations

import asyncio
from typing import Any, cast

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..constants import TRADING_DAYS_PER_YEAR
from ..hatchet_app import hatchet
from .data_refresh_schedules import (
    DAILY_OHLCV_CRONS,
    FEAR_GREED_CALC_CRONS,
    FEAR_GREED_INPUTS_CRONS,
    FUNDAMENTAL_INGESTION_CRONS,
    HISTORICAL_OHLCV_MAINTENANCE_CRONS,
    MACRO_INDICATOR_INGESTION_CRONS,
    OPTIONS_ACTIVITY_CRONS,
    PUTCALL_RATIO_CRONS,
    TECHNICAL_INDICATOR_BACKFILL_CRONS,
    WATCHLIST_OHLCV_CRONS,
)
from .models import EmptyInput, SymbolsInput


@hatchet.task(
    name="portfolio-refresh-ohlcv",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=3,
    backoff_factor=2.0,
    on_crons=DAILY_OHLCV_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-refresh-ohlcv'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def refresh_daily_ohlcv_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..services import paper_trades
    from ..tasks.ingestion.price_ingestion import refresh_daily_ohlcv

    ohlcv_result: dict[str, Any] = dict(await asyncio.to_thread(refresh_daily_ohlcv))
    if ohlcv_result.get("status") == "failed":
        ohlcv_result["paper_trade_pnl"] = {"status": "skipped", "reason": "ohlcv_refresh_failed"}
        return ohlcv_result
    ohlcv_result["paper_trade_pnl"] = await asyncio.to_thread(paper_trades.update_pnl_for_open)
    return ohlcv_result


@hatchet.task(
    name="portfolio-refresh-watchlist-ohlcv",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=3,
    backoff_factor=2.0,
    on_crons=WATCHLIST_OHLCV_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-refresh-watchlist-ohlcv'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def refresh_watchlist_ohlcv_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.ingestion.price_ingestion import refresh_watchlist_ohlcv

    return await asyncio.to_thread(refresh_watchlist_ohlcv)


@hatchet.task(
    name="portfolio-backfill-indicators",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=TECHNICAL_INDICATOR_BACKFILL_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-backfill-indicators'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def backfill_indicators_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.indicators.technical import backfill_technical_indicators

    return await asyncio.to_thread(backfill_technical_indicators)


@hatchet.task(
    name="portfolio-fg-inputs",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=3,
    backoff_factor=2.0,
    on_crons=FEAR_GREED_INPUTS_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-fg-inputs'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def populate_fear_greed_inputs_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.market_data.fear_greed_pipeline import populate_fear_greed_inputs

    return cast(dict[str, Any], await asyncio.to_thread(populate_fear_greed_inputs))


@hatchet.task(
    name="portfolio-fg-calc",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=3,
    backoff_factor=2.0,
    on_crons=FEAR_GREED_CALC_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-fg-calc'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def calculate_fear_greed_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.indicators.fear_greed import calculate_fear_greed

    return cast(dict[str, Any], await asyncio.to_thread(calculate_fear_greed))


@hatchet.task(
    name="portfolio-maintain-historical",
    input_validator=EmptyInput,
    execution_timeout="7200s",
    retries=3,
    backoff_factor=2.0,
    on_crons=HISTORICAL_OHLCV_MAINTENANCE_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-maintain-historical'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def maintain_historical_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.market_data.historical_ohlcv_pipeline import maintain_historical_market_data

    return await asyncio.to_thread(maintain_historical_market_data)


@hatchet.task(
    name="portfolio-options-activity",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=OPTIONS_ACTIVITY_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-options-activity'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def fetch_options_activity_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.market_data.options_pipeline import fetch_options_activity_metrics

    return await asyncio.to_thread(fetch_options_activity_metrics)


@hatchet.task(
    name="portfolio-putcall-ratio",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=3,
    backoff_factor=2.0,
    on_crons=PUTCALL_RATIO_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-putcall-ratio'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def fetch_putcall_ratio_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.market_data.options_pipeline import fetch_putcall_ratio

    return await asyncio.to_thread(fetch_putcall_ratio)


@hatchet.task(
    name="portfolio-ingest-ohlcv",
    input_validator=SymbolsInput,
    execution_timeout="7200s",
    retries=3,
    backoff_factor=2.0,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-ingest-ohlcv'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def ingest_ohlcv_wf(input: SymbolsInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.ingestion.price_ingestion import ingest_historical_ohlcv

    return await asyncio.to_thread(ingest_historical_ohlcv, symbols=input.symbols, days=input.days or TRADING_DAYS_PER_YEAR)


@hatchet.task(
    name="portfolio-update-indicators",
    input_validator=SymbolsInput,
    execution_timeout="3600s",
    retries=3,
    backoff_factor=2.0,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-update-indicators'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def update_technical_indicators_wf(input: SymbolsInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.indicators.technical import update_technical_indicators

    return cast(dict[str, Any], await asyncio.to_thread(update_technical_indicators, symbols=input.symbols))


@hatchet.task(
    name="portfolio-ingest-fundamentals",
    input_validator=EmptyInput,
    execution_timeout="7200s",
    retries=2,
    backoff_factor=2.0,
    on_crons=FUNDAMENTAL_INGESTION_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-ingest-fundamentals'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def ingest_fundamental_data_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.ingestion.fundamental_ingestion import ingest_fundamental_data

    return await asyncio.to_thread(ingest_fundamental_data)


@hatchet.task(
    name="portfolio-ingest-macro",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=2,
    backoff_factor=2.0,
    on_crons=MACRO_INDICATOR_INGESTION_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-ingest-macro'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def ingest_macro_indicators_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.ingestion.fundamental_ingestion import ingest_macro_indicators

    return await asyncio.to_thread(ingest_macro_indicators)
