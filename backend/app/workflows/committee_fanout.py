"""L3 committee fan-out workflow.

Chained off the L2 scanner. Reads the latest scanner run, drops the
DEFENSIVE case, applies the cross-run cache, enforces a per-day rate
cap, and spawns up to N committee runs against the top-ranked tickers.

Each spawned ``committee_runs`` row carries ``source='scanner_fanout'``
+ ``scanner_rank`` so the unified ``/api/signals/*`` views can show
provenance and the cost ledger can attribute spend to the fan-out
versus user-triggered runs.

The actual committee orchestration runs as in-process asyncio tasks
attached to the worker's event loop — same pattern the
``/api/portfolio/committee/runs`` route uses. We do not block the fan-out
task on completion; the fan-out's job is to *kick off* the runs and
return.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from app.agents.committee import GRAPH_VERSION, cache, graph
from app.agents.committee import store as committee_store
from app.agents.committee import stream as committee_stream
from app.hatchet_app import hatchet
from app.logging_config import get_logger
from app.scanner import repository as scanner_repo
from app.storage.connection import get_connection_manager

from .models import EmptyInput

logger = get_logger(__name__)

DEFAULT_TOP_N = 25
DEFAULT_MAX_DAILY = 25  # belt-and-braces in addition to top-N

# Worker-process registry of spawned tasks; mirrors
# ``app.api.committee_runs._RUNNER_TASKS`` so the loop holds a strong
# reference until each run completes.
_FANOUT_TASKS: set[asyncio.Task[None]] = set()


@dataclass(frozen=True, slots=True)
class FanoutOutput:
    run_date: date
    gate_zone: str
    scanner_run_id: str | None
    spawned: list[dict[str, Any]]
    skipped: list[dict[str, Any]]
    skip_reason: str | None


@hatchet.task(
    name="portfolio-committee-fanout",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=1,
    backoff_factor=2.0,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-committee-fanout'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def committee_fanout_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    output = await asyncio.to_thread(run_fanout, loop=loop)
    payload: dict[str, Any] = {
        "status": "ok" if output.skip_reason is None else "skipped",
        "gate_zone": output.gate_zone,
        "run_date": output.run_date.isoformat(),
        "scanner_run_id": output.scanner_run_id,
        "spawned_count": len(output.spawned),
        "skipped_count": len(output.skipped),
        "spawned": output.spawned,
        "skipped": output.skipped,
    }
    if output.skip_reason:
        payload["skip_reason"] = output.skip_reason
    return payload


def run_fanout(
    *,
    top_n: int | None = None,
    max_daily: int | None = None,
    now: datetime | None = None,
    loop: asyncio.AbstractEventLoop | None = None,
) -> FanoutOutput:
    """Synchronous fan-out kernel; safe to call from a worker thread.

    Spawns the committee tasks on ``loop`` when supplied (the Hatchet
    worker passes its own running loop); otherwise — e.g. when called
    from a backfill script with no loop attached — records the planned
    spawns but does not start them. That guard keeps the function
    testable without a live worker.
    """
    top_n = top_n if top_n is not None else _int_env("COMMITTEE_FANOUT_TOP_N", DEFAULT_TOP_N)
    max_daily = (
        max_daily
        if max_daily is not None
        else _int_env("COMMITTEE_FANOUT_MAX_DAILY", DEFAULT_MAX_DAILY)
    )
    current = (now or datetime.now(tz=UTC)).astimezone(UTC)

    latest = scanner_repo.get_latest_run()
    if latest is None:
        logger.warning("committee_fanout_no_scanner_run")
        return FanoutOutput(
            run_date=current.date(),
            gate_zone="UNKNOWN",
            scanner_run_id=None,
            spawned=[],
            skipped=[],
            skip_reason="no_scanner_run",
        )

    gate_zone = str(latest["gate_zone"])
    scanner_run_id = str(latest["run_id"])
    run_date = _parse_date(latest.get("run_date")) or current.date()

    if gate_zone == "DEFENSIVE":
        logger.info(
            "committee_fanout_skipped_defensive",
            scanner_run_id=scanner_run_id,
            run_date=run_date.isoformat(),
        )
        return FanoutOutput(
            run_date=run_date,
            gate_zone=gate_zone,
            scanner_run_id=scanner_run_id,
            spawned=[],
            skipped=[],
            skip_reason="gate_defensive",
        )

    scores = scanner_repo.get_scores_for_run(UUID(scanner_run_id), limit=top_n)
    if not scores:
        return FanoutOutput(
            run_date=run_date,
            gate_zone=gate_zone,
            scanner_run_id=scanner_run_id,
            spawned=[],
            skipped=[],
            skip_reason="no_scores",
        )

    already_today = _count_fanout_today(run_date=run_date)
    remaining_budget = max(0, max_daily - already_today)
    if remaining_budget <= 0:
        logger.info(
            "committee_fanout_rate_capped",
            run_date=run_date.isoformat(),
            already_today=already_today,
            max_daily=max_daily,
        )
        return FanoutOutput(
            run_date=run_date,
            gate_zone=gate_zone,
            scanner_run_id=scanner_run_id,
            spawned=[],
            skipped=[
                {"symbol": str(row["symbol"]).upper(),
                 "scanner_rank": int(row["rank"]),
                 "reason": "max_daily_reached"}
                for row in scores
            ],
            skip_reason="max_daily_reached",
        )

    spawned: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    spawn_loop = loop

    for row in scores:
        if len(spawned) >= remaining_budget:
            skipped.append(
                {
                    "symbol": str(row["symbol"]).upper(),
                    "scanner_rank": int(row["rank"]),
                    "reason": "max_daily_reached",
                }
            )
            continue

        symbol = str(row["symbol"]).upper()
        scanner_rank = int(row["rank"])

        decision = cache.should_run(symbol, current_zone=gate_zone, now=current)
        if not decision.should_run:
            skipped.append(
                {
                    "symbol": symbol,
                    "scanner_rank": scanner_rank,
                    "reason": decision.reason,
                    "last_run_id": decision.last_run_id,
                }
            )
            continue

        run_id = committee_store.create_run(
            symbol=symbol,
            household_id=None,
            parent_run_id=None,
            graph_version=GRAPH_VERSION,
            source="scanner_fanout",
            scanner_rank=scanner_rank,
        )
        if spawn_loop is not None:
            asyncio.run_coroutine_threadsafe(
                _register_and_run(run_id=run_id, symbol=symbol), spawn_loop
            )
        spawned.append(
            {
                "symbol": symbol,
                "scanner_rank": scanner_rank,
                "run_id": run_id,
            }
        )

    logger.info(
        "committee_fanout_completed",
        scanner_run_id=scanner_run_id,
        gate_zone=gate_zone,
        spawned=len(spawned),
        skipped=len(skipped),
    )
    return FanoutOutput(
        run_date=run_date,
        gate_zone=gate_zone,
        scanner_run_id=scanner_run_id,
        spawned=spawned,
        skipped=skipped,
        skip_reason=None,
    )


async def _register_and_run(*, run_id: str, symbol: str) -> None:
    """Attach a stream queue and run the committee orchestrator.

    Mirrors ``app.api.committee_runs._schedule_run`` + ``_run_committee_safely``.
    """
    if committee_stream.get(run_id) is None:
        await committee_stream.register(run_id)
    task = asyncio.create_task(_run_committee_safely(run_id=run_id, symbol=symbol))
    _FANOUT_TASKS.add(task)
    task.add_done_callback(_FANOUT_TASKS.discard)


async def _run_committee_safely(*, run_id: str, symbol: str) -> None:
    try:
        await graph.run_committee(
            run_id=run_id,
            symbol=symbol,
            household_id=None,
            parent_run_id=None,
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("committee_fanout_runner_crashed", run_id=run_id, symbol=symbol)


def _count_fanout_today(*, run_date: date) -> int:
    """Count fan-out runs already initiated on ``run_date`` (any status)."""
    cm = get_connection_manager()
    with cm.connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) FROM committee_runs
            WHERE source = 'scanner_fanout'
              AND started_at::date = %s::date
            """,
            (run_date,),
        ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def _parse_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default
