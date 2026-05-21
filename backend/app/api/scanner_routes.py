"""L2 quantitative scanner API.

Read endpoints expose persisted scanner runs + per-symbol scores. The
manual run endpoint only enqueues the workflow; scanner writes still live
inside the workflow path.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from ..logging_config import get_logger
from ..scanner import repository
from ..scanner.factors import FACTOR_NAMES

logger = get_logger(__name__)
router = APIRouter(prefix="/api/scanner", tags=["scanner"])


class ScannerRunResponse(BaseModel):
    run_id: str
    run_date: str
    gate_zone: str
    gate_score: float | None = None
    universe_size: int
    scored_count: int
    skip_reason: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class ScannerTriggerResponse(BaseModel):
    status: str
    workflow: str
    message: str


class ScannerScoreResponse(BaseModel):
    symbol: str
    rank: int
    composite_pct: float | None
    factor_coverage: float | None
    factors: dict[str, float | None]
    percentiles: dict[str, float | None]


class ScannerLatestResponse(BaseModel):
    run: ScannerRunResponse
    scores: list[ScannerScoreResponse]
    factor_order: list[str]


class ScannerHistoryResponse(BaseModel):
    runs: list[ScannerRunResponse]


class SymbolHistoryRow(BaseModel):
    run_date: str
    gate_zone: str
    composite_pct: float | None
    rank: int
    factor_coverage: float | None
    percentiles: dict[str, float | None]


class ScannerSymbolResponse(BaseModel):
    symbol: str
    history: list[SymbolHistoryRow]


def _run_to_response(row: dict[str, Any]) -> ScannerRunResponse:
    return ScannerRunResponse(**row)


def _score_to_response(row: dict[str, Any]) -> ScannerScoreResponse:
    factors = {name: row.get(name) for name in FACTOR_NAMES}
    percentiles = {name: row.get(f"{name}_pct") for name in FACTOR_NAMES}
    return ScannerScoreResponse(
        symbol=row["symbol"],
        rank=int(row["rank"]),
        composite_pct=row.get("composite_pct"),
        factor_coverage=row.get("factor_coverage"),
        factors=factors,
        percentiles=percentiles,
    )


async def _enqueue_scanner_workflow() -> None:
    from ..workflows.models import EmptyInput  # noqa: PLC0415
    from ..workflows.scanner import scanner_wf  # noqa: PLC0415

    await scanner_wf.aio_run_no_wait(EmptyInput())


@router.post(
    "/run",
    response_model=ScannerTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_run() -> ScannerTriggerResponse:
    """Manually queue the L2 scanner workflow.

    The scanner workflow chains committee fan-out after the scanner output is
    persisted, so callers do not need a second trigger for the blended view.
    """
    try:
        await _enqueue_scanner_workflow()
    except Exception as exc:
        logger.exception("scanner_manual_trigger_failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="scanner_trigger_failed",
        ) from exc
    return ScannerTriggerResponse(
        status="queued",
        workflow="portfolio-scanner",
        message="Scanner run queued. Committee fan-out will follow scanner completion.",
    )


@router.get("/latest", response_model=ScannerLatestResponse)
async def latest(
    limit: int = Query(default=50, ge=1, le=500),
) -> ScannerLatestResponse:
    run = await run_in_threadpool(repository.get_latest_run)
    if run is None:
        raise HTTPException(status_code=503, detail="scanner_no_runs_yet")
    scores: list[dict[str, Any]] = []
    if run.get("skip_reason") is None:
        scores = await run_in_threadpool(
            repository.get_scores_for_run, UUID(run["run_id"]), limit=limit
        )
    return ScannerLatestResponse(
        run=_run_to_response(run),
        scores=[_score_to_response(row) for row in scores],
        factor_order=list(FACTOR_NAMES),
    )


@router.get("/history", response_model=ScannerHistoryResponse)
async def history(days: int = Query(default=60, ge=1, le=730)) -> ScannerHistoryResponse:
    runs = await run_in_threadpool(repository.get_run_history, days)
    return ScannerHistoryResponse(runs=[_run_to_response(row) for row in runs])


@router.get("/symbol/{ticker}", response_model=ScannerSymbolResponse)
async def by_symbol(
    ticker: str,
    days: int = Query(default=90, ge=1, le=365),
) -> ScannerSymbolResponse:
    ticker = ticker.upper().strip()
    rows = await run_in_threadpool(repository.get_history_for_symbol, ticker, days)
    if not rows:
        raise HTTPException(status_code=404, detail=f"no_scanner_history_for_{ticker}")
    return ScannerSymbolResponse(
        symbol=ticker,
        history=[
            SymbolHistoryRow(
                run_date=row["run_date"],
                gate_zone=row["gate_zone"],
                composite_pct=row.get("composite_pct"),
                rank=row["rank"],
                factor_coverage=row.get("factor_coverage"),
                percentiles={name: row.get(f"{name}_pct") for name in FACTOR_NAMES},
            )
            for row in rows
        ],
    )
