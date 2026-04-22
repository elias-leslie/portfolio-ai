"""Scheduled market-prediction workflows."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

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
from app.utils.market_hours import is_trading_day

from ..hatchet_app import hatchet
from .data_refresh_schedules import (
    MARKET_PREDICTION_AFTER_CLOSE_CRONS,
    MARKET_PREDICTION_MORNING_CRONS,
    MARKET_PREDICTION_SUNDAY_CRONS,
)
from .models import EmptyInput


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
    as_of_ts: datetime | None = None,
) -> dict[str, Any]:
    effective_ts = as_of_ts or datetime.now(UTC)
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
    }


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
