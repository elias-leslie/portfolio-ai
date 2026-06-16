"""Reference data & fundamentals workflows.

Thin async wrappers around existing business logic in tasks/.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from ..services.preferences_service import get_automation_preferences
from .models import EmptyInput


@hatchet.task(
    name="portfolio-yfinance-ref",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=3,
    backoff_factor=2.0,
    on_crons=["2 4 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-yfinance-ref'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def yfinance_ref_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.reference_tasks import refresh_yfinance_reference_data

    return await asyncio.to_thread(refresh_yfinance_reference_data)


@hatchet.task(
    name="portfolio-valuation-metrics",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["30 4 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-valuation-metrics'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def valuation_metrics_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.reference_tasks import parse_valuation_metrics

    return await asyncio.to_thread(parse_valuation_metrics)


@hatchet.task(
    name="portfolio-analyst-revisions",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["0 7 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-analyst-revisions'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def refresh_analyst_revisions_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.reference_tasks import refresh_analyst_revisions

    return await asyncio.to_thread(refresh_analyst_revisions)


@hatchet.task(
    name="portfolio-earnings-surprises",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["10 5 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-earnings-surprises'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def earnings_surprises_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.ingestion.analytics_ingestion import update_earnings_surprises

    return await asyncio.to_thread(update_earnings_surprises)


@hatchet.task(
    name="portfolio-financial-health",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["15 5 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-financial-health'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def financial_health_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.reference_tasks import refresh_financial_health_scores_isolated

    return await asyncio.to_thread(refresh_financial_health_scores_isolated)


@hatchet.task(
    name="portfolio-risk-metrics",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["39 5 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-risk-metrics'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def refresh_risk_metrics_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.reference_tasks import refresh_risk_metrics

    return await asyncio.to_thread(refresh_risk_metrics)


@hatchet.task(
    name="portfolio-corporate-actions",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["30 6 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-corporate-actions'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def corporate_actions_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.market_data.corporate_actions_pipeline import fetch_corporate_actions

    return await asyncio.to_thread(fetch_corporate_actions)


@hatchet.task(
    name="portfolio-sec-cik",
    input_validator=EmptyInput,
    execution_timeout="3600s",
    retries=1,
    on_crons=["5 6 * * 0"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-sec-cik'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def refresh_sec_cik_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from ..tasks.maintenance_tasks import refresh_sec_cik_cache

    return await asyncio.to_thread(refresh_sec_cik_cache)


@hatchet.task(
    name="portfolio-retrain-ml",
    input_validator=EmptyInput,
    execution_timeout="7200s",
    retries=1,
    on_crons=["0 5 * * *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-retrain-ml'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def retrain_ml_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    automation = get_automation_preferences()
    if not bool(automation["scheduled_ml_labeling_enabled"]["enabled"]):
        return {"status": "skipped", "reason": "scheduled_ml_labeling_disabled"}
    from ..tasks.ml_training_tasks import retrain_article_quality_model

    return await asyncio.to_thread(retrain_article_quality_model)


@hatchet.task(
    name="portfolio-aca-landscape",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=2,
    backoff_factor=4.0,
    # Nov 15 yearly: CMS publishes the next plan year's QHP landscape PUF
    # around open enrollment (Nov 1), so ingest the upcoming plan year.
    on_crons=["0 6 15 11 *"],
    concurrency=ConcurrencyExpression(
        expression="'portfolio-aca-landscape'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def aca_landscape_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    from datetime import UTC, datetime

    from ..services.aca_marketplace_ingest_service import AcaMarketplaceIngestService

    plan_year = datetime.now(UTC).year + 1
    return await asyncio.to_thread(
        lambda: AcaMarketplaceIngestService().ingest(plan_year=plan_year)
    )
