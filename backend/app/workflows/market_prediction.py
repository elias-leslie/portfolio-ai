"""Scheduled market-prediction workflows."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from app.logging_config import get_logger
from app.services.market_prediction_cluster_weighting_service import (
    MarketPredictionClusterWeightingService,
)
from app.services.market_prediction_committee_service import (
    SUPPORTED_PREDICTION_WINDOWS,
    MarketPredictionCommitteeService,
)
from app.services.market_prediction_evaluation_service import MarketPredictionEvaluationService
from app.services.market_prediction_seat_weighting_service import (
    MarketPredictionSeatWeightingService,
)
from app.tasks.ingestion.price_ingestion import refresh_daily_ohlcv
from app.tasks.market_data.macro_calendar_pipeline import ingest_macro_calendar_events
from app.tasks.market_data.options_pipeline import fetch_options_activity_metrics
from app.utils.market_hours import is_trading_day

from ..hatchet_app import hatchet
from .data_refresh_schedules import (
    MACRO_CALENDAR_INGESTION_CRONS,
    MARKET_PREDICTION_AFTER_CLOSE_CRONS,
    MARKET_PREDICTION_MORNING_CRONS,
    MARKET_PREDICTION_SUNDAY_CRONS,
)
from .models import EmptyInput

logger = get_logger(__name__)


def _concurrency(name: str) -> ConcurrencyExpression:
    return ConcurrencyExpression(
        expression=f"'{name}'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    )


def run_market_prediction_cycle(
    *,
    committee_service: MarketPredictionCommitteeService | None = None,
    evaluation_service: MarketPredictionEvaluationService | None = None,
    seat_weighting_service: MarketPredictionSeatWeightingService | None = None,
    cluster_weighting_service: MarketPredictionClusterWeightingService | None = None,
    macro_calendar_ingestion_fn: Callable[..., dict[str, Any]] | None = ingest_macro_calendar_events,
    options_activity_fn: Callable[[], dict[str, Any]] | None = fetch_options_activity_metrics,
    ohlcv_refresh_fn: Callable[[], dict[str, Any]] | None = refresh_daily_ohlcv,
    as_of_ts: datetime | None = None,
) -> dict[str, Any]:
    effective_ts = as_of_ts or datetime.now(UTC)
    ohlcv_refresh: dict[str, Any]
    if ohlcv_refresh_fn is None:
        ohlcv_refresh = {"status": "skipped"}
    else:
        try:
            ohlcv_refresh = ohlcv_refresh_fn()
        except Exception as exc:
            logger.warning("ohlcv_refresh_for_prediction_failed", error=str(exc), exc_info=True)
            ohlcv_refresh = {"status": "failed", "error": str(exc)}
    macro_calendar_ingestion: dict[str, Any]
    if macro_calendar_ingestion_fn is None:
        macro_calendar_ingestion = {"status": "skipped"}
    else:
        try:
            macro_calendar_ingestion = macro_calendar_ingestion_fn(
                start_date=effective_ts.date(),
                horizon_days=60,
            )
        except Exception as exc:
            logger.warning("macro_calendar_ingestion_for_prediction_failed", error=str(exc), exc_info=True)
            macro_calendar_ingestion = {"status": "failed", "error": str(exc)}
    options_activity: dict[str, Any]
    if options_activity_fn is None:
        options_activity = {"status": "skipped"}
    else:
        try:
            options_activity = options_activity_fn()
        except Exception as exc:
            logger.warning("options_activity_for_prediction_failed", error=str(exc), exc_info=True)
            options_activity = {"status": "failed", "error": str(exc)}
    committee = committee_service or MarketPredictionCommitteeService()
    evaluation = evaluation_service or MarketPredictionEvaluationService()
    seat_weighting = seat_weighting_service or MarketPredictionSeatWeightingService()
    cluster_weighting = cluster_weighting_service or MarketPredictionClusterWeightingService()
    evaluations = evaluation.evaluate_due_predictions(as_of_date=effective_ts.date())
    generated_windows: list[int] = []
    for window_days in SUPPORTED_PREDICTION_WINDOWS:
        source_snapshot = committee.build_source_snapshot(effective_ts)
        evaluation.backfill_vote_evaluations(window_days=window_days, as_of_ts=effective_ts)
        review = seat_weighting.resolve_and_persist_review(window_days=window_days, as_of_ts=effective_ts)
        cluster_review = cluster_weighting.resolve_and_persist_review(
            window_days=window_days,
            as_of_ts=effective_ts,
            source_snapshot=source_snapshot,
        )
        committee.generate_snapshot(
            window_days=window_days,
            as_of_ts=effective_ts,
            review=review,
            cluster_review=cluster_review,
            source_snapshot=source_snapshot,
        )
        generated_windows.append(window_days)
    return {
        "status": "completed",
        "as_of_ts": effective_ts.isoformat(),
        "generated_windows": generated_windows,
        "evaluations_completed": len(evaluations),
        "ohlcv_refresh": ohlcv_refresh,
        "macro_calendar_ingestion": macro_calendar_ingestion,
        "options_activity": options_activity,
    }


@hatchet.task(
    name="portfolio-market-macro-calendar-ingestion",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=2,
    on_crons=MACRO_CALENDAR_INGESTION_CRONS,
    concurrency=_concurrency("portfolio-market-macro-calendar-ingestion"),
)
async def market_macro_calendar_ingestion_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    return await asyncio.to_thread(ingest_macro_calendar_events)


@hatchet.task(
    name="portfolio-market-prediction-morning-prep",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=MARKET_PREDICTION_MORNING_CRONS,
    concurrency=_concurrency("portfolio-market-prediction-morning-prep"),
)
async def market_prediction_morning_prep_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    if not is_trading_day():
        return {"status": "skipped", "reason": "not_trading_day"}
    return await asyncio.to_thread(run_market_prediction_cycle)


@hatchet.task(
    name="portfolio-market-prediction-after-close",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=MARKET_PREDICTION_AFTER_CLOSE_CRONS,
    concurrency=_concurrency("portfolio-market-prediction-after-close"),
)
async def market_prediction_after_close_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    if not is_trading_day():
        return {"status": "skipped", "reason": "not_trading_day"}
    return await asyncio.to_thread(run_market_prediction_cycle)


@hatchet.task(
    name="portfolio-market-prediction-sunday-prep",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=1,
    on_crons=MARKET_PREDICTION_SUNDAY_CRONS,
    concurrency=_concurrency("portfolio-market-prediction-sunday-prep"),
)
async def market_prediction_sunday_prep_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    return await asyncio.to_thread(run_market_prediction_cycle)
