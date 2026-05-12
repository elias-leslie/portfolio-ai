"""REST routes for the Investment Committee.

Endpoints:

- ``POST   /api/committee/runs``            — start a new run (returns run_id)
- ``GET    /api/committee/runs/{id}``       — current snapshot + event history
- ``POST   /api/committee/runs/{id}/approve``  — execute the paper trade
- ``POST   /api/committee/runs/{id}/feedback`` — user injects a new claim mid-run
- ``POST   /api/committee/runs/{id}/retro``    — start a retro run with parent
- ``POST   /api/committee/runs/{id}/pause``    — cooperative pause
- ``POST   /api/committee/runs/{id}/resume``   — resume from pause
- ``POST   /api/committee/runs/{id}/abort``    — abort the run

SSE stream is in ``committee_stream.py`` to keep the streaming
content-type path isolated from the JSON routes.

Auth mirrors the existing /api/portfolio/* dependency: we accept the
authenticated household_id from the request and scope all reads to
that household. Today the project is single-household; the dep is
shared and will tighten when multi-household lands.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.agents.committee import GRAPH_VERSION, graph, store, stream
from app.logging_config import get_logger
from app.services import paper_trades as paper_trades_svc

logger = get_logger(__name__)

router = APIRouter(prefix="/api/committee", tags=["committee"])


class StartRunRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    parent_run_id: str | None = None


class StartRunResponse(BaseModel):
    run_id: str
    symbol: str
    status: str
    graph_version: str


class FeedbackRequest(BaseModel):
    user_input: str = Field(..., min_length=1, max_length=4000)


class ApproveResponse(BaseModel):
    paper_trade_id: str
    run_id: str
    symbol: str
    action: str
    qty: float
    price: float


class RunSnapshotResponse(BaseModel):
    run: dict[str, Any]
    events: list[dict[str, Any]]


@router.post("/runs", response_model=StartRunResponse, status_code=status.HTTP_201_CREATED)
async def start_run(
    payload: StartRunRequest, background_tasks: BackgroundTasks
) -> StartRunResponse:
    """Create the run row, register the stream, and dispatch the runner.

    The runner executes as a background task so the HTTP handler can
    return immediately with the run_id; the client then opens the SSE
    stream to follow progress.
    """
    household_id = _resolve_household_id()
    run_id = await run_in_threadpool(
        store.create_run,
        symbol=payload.symbol,
        household_id=household_id,
        parent_run_id=payload.parent_run_id,
        graph_version=GRAPH_VERSION,
    )
    await stream.register(run_id)
    background_tasks.add_task(
        _run_committee_safely,
        run_id=run_id,
        symbol=payload.symbol,
        household_id=household_id,
        parent_run_id=payload.parent_run_id,
    )
    return StartRunResponse(
        run_id=run_id,
        symbol=payload.symbol.upper(),
        status="pending",
        graph_version=GRAPH_VERSION,
    )


@router.get("/runs/{run_id}", response_model=RunSnapshotResponse)
async def get_run(run_id: str) -> RunSnapshotResponse:
    """Return the run + event history for SSE replay or detail view."""
    _validate_uuid(run_id)
    run = await run_in_threadpool(store.get_run_summary, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"committee_run {run_id} not found")
    events = await run_in_threadpool(store.load_events, run_id)
    return RunSnapshotResponse(run=run, events=events)


@router.post("/runs/{run_id}/approve", response_model=ApproveResponse)
async def approve_run(run_id: str) -> ApproveResponse:
    """Execute the paper trade for an approved decision."""
    _validate_uuid(run_id)
    try:
        result = await run_in_threadpool(paper_trades_svc.execute_from_run, run_id)
    except paper_trades_svc.PaperTradeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApproveResponse(
        paper_trade_id=result.id,
        run_id=run_id,
        symbol=result.symbol,
        action=result.action,
        qty=result.qty,
        price=result.price,
    )


@router.post("/runs/{run_id}/feedback")
async def submit_feedback(run_id: str, payload: FeedbackRequest) -> dict[str, Any]:
    """Persist a user feedback claim against an in-progress run.

    The actual feedback round (re-scoring by analysts + risk + PM
    revise check) is enqueued for the running graph to consume — for
    this initial cut we persist the claim and emit a
    ``run.feedback.received`` event; the consensus-shift round is the
    next iteration's scope.
    """
    _validate_uuid(run_id)
    run = await run_in_threadpool(store.get_run_summary, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"committee_run {run_id} not found")
    if run["status"] in {"complete", "approved", "aborted", "failed"}:
        # We still accept feedback so the user's claim is logged for the
        # retro/audit trail, but warn that the live re-evaluation won't fire.
        logger.info("committee_feedback_post_terminal", run_id=run_id, status=run["status"])

    # Compute the round number = (count of existing inputs) + 1.
    existing_events = await run_in_threadpool(store.load_events, run_id)
    round_idx = (
        sum(1 for e in existing_events if e.get("type") == "run.feedback.received") + 1
    )
    seq = await run_in_threadpool(store.next_seq, run_id)
    event_id = await run_in_threadpool(
        store.persist_event,
        run_id,
        seq=seq,
        type="run.feedback.received",
        stage="feedback",
        role="user",
        content={"round": round_idx, "user_input": payload.user_input},
    )
    input_id = await run_in_threadpool(
        store.persist_user_input,
        run_id,
        round_idx=round_idx,
        user_input=payload.user_input,
        triggered_event_id=event_id,
    )
    await stream.emit(
        run_id,
        {
            "seq": seq,
            "type": "run.feedback.received",
            "stage": "feedback",
            "role": "user",
            "run_id": run_id,
            "content": {
                "round": round_idx,
                "user_input": payload.user_input,
                "input_id": input_id,
            },
        },
    )
    return {"input_id": input_id, "round": round_idx}


@router.post("/runs/{run_id}/retro", response_model=StartRunResponse)
async def start_retro(run_id: str, background_tasks: BackgroundTasks) -> StartRunResponse:
    """Start a retro review run with parent_run_id = run_id."""
    _validate_uuid(run_id)
    parent = await run_in_threadpool(store.get_run_summary, run_id)
    if parent is None:
        raise HTTPException(status_code=404, detail=f"committee_run {run_id} not found")
    if parent["status"] not in {"complete", "approved"}:
        raise HTTPException(
            status_code=409,
            detail=f"parent run status='{parent['status']}'; retro requires complete or approved",
        )
    payload = StartRunRequest(symbol=parent["symbol"], parent_run_id=run_id)
    return await start_run(payload, background_tasks)


@router.post("/runs/{run_id}/pause")
async def pause_run(run_id: str) -> dict[str, Any]:
    _validate_uuid(run_id)
    return {"paused": stream.pause(run_id)}


@router.post("/runs/{run_id}/resume")
async def resume_run(run_id: str) -> dict[str, Any]:
    _validate_uuid(run_id)
    return {"resumed": stream.resume(run_id)}


@router.post("/runs/{run_id}/abort")
async def abort_run(run_id: str) -> dict[str, Any]:
    _validate_uuid(run_id)
    return {"aborted": stream.abort(run_id)}


# ---------- helpers ----------


def _resolve_household_id() -> str | None:
    """Resolve household_id from request context.

    The project ships a single-household model today; the existing
    /api/portfolio/* routes do not yet inject a household_id dep.
    Returning None scopes to the default household and is consistent
    with the rest of the codebase. When multi-household lands, swap
    this for the shared dependency and the committee runs auto-scope.
    """
    return None


def _validate_uuid(run_id: str) -> None:
    try:
        uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"invalid run_id: {exc}") from exc


async def _run_committee_safely(
    *,
    run_id: str,
    symbol: str,
    household_id: str | None,
    parent_run_id: str | None,
) -> None:
    """Wrap ``graph.run_committee`` so a runner crash never leaks to the BackgroundTasks executor."""
    try:
        await graph.run_committee(
            run_id=run_id,
            symbol=symbol.upper(),
            household_id=household_id,
            parent_run_id=parent_run_id,
        )
    except asyncio.CancelledError:
        # Already handled inside run_committee — re-raise quietly.
        raise
    except Exception:
        logger.exception("committee_background_task_crashed", run_id=run_id)
