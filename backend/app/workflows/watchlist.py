"""Watchlist workflows.

Thin async wrappers around existing business logic in tasks/.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from .models import EmptyInput, SymbolInput, WatchlistInput


@hatchet.task(
    name="portfolio-refresh-watchlist-scores",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["* * * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-refresh-watchlist-scores'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def refresh_watchlist_scores_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.watchlist_tasks import refresh_watchlist_scores_task

    return await asyncio.to_thread(refresh_watchlist_scores_task)


@hatchet.task(
    name="portfolio-refresh-single-symbol",
    input_validator=SymbolInput,
    execution_timeout="600s",
    retries=1,
    concurrency=ConcurrencyExpression(
        expression="input.symbol",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def refresh_single_symbol_wf(input: SymbolInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.watchlist_tasks import refresh_single_symbol_scores_task

    return await asyncio.to_thread(refresh_single_symbol_scores_task, symbol=input.symbol)


@hatchet.task(
    name="portfolio-refresh-news-sentiment",
    input_validator=WatchlistInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["25 * * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-refresh-news-sentiment'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def refresh_news_sentiment_wf(input: WatchlistInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.news_tasks import refresh_news_sentiment_task

    return await asyncio.to_thread(refresh_news_sentiment_task)


@hatchet.task(
    name="portfolio-discover-candidates",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["0 8 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-discover-candidates'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def discover_candidates_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.watchlist_discovery.discovery import discover_watchlist_candidates_task

    return await asyncio.to_thread(discover_watchlist_candidates_task)


@hatchet.task(
    name="portfolio-trim-underperforming",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=["30 8 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-trim-underperforming'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def trim_underperforming_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.watchlist_discovery.trimming import trim_underperforming_watchlist_task

    return await asyncio.to_thread(trim_underperforming_watchlist_task)
