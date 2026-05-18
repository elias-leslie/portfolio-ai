"""L2 quantitative scanner workflow.

Chained off the L1 macro gate: ``macro_gate_wf`` calls
``scanner_wf.aio_run_no_wait()`` after persisting the snapshot. This
keeps the L1→L2 sequencing explicit (events are dispatched by the parent
workflow rather than via a generic event bus), matching the existing
pattern used by ``workflows/events.py``.

When run directly (e.g. backfills), this workflow uses today's macro
snapshot from the DB to determine zone.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from ..scanner.service import run as run_scanner
from .models import EmptyInput


@hatchet.task(
    name="portfolio-scanner",
    input_validator=EmptyInput,
    execution_timeout="1200s",
    retries=1,
    backoff_factor=2.0,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-scanner'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def scanner_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    output = await asyncio.to_thread(run_scanner)
    if output is None:
        return {"status": "skipped", "reason": "no_macro_snapshot"}

    # Chain L3 committee fan-out. Imported lazily to avoid cyclic
    # registration at Hatchet boot, mirroring how macro_gate_wf chains
    # the scanner. ``aio_run_no_wait`` returns immediately so the
    # scanner task isn't held open while the committee runs complete.
    from .committee_fanout import committee_fanout_wf

    await committee_fanout_wf.aio_run_no_wait(EmptyInput())

    return {
        "status": "ok",
        "run_id": str(output.run_id),
        "run_date": output.run_date.isoformat(),
        "gate_zone": output.gate_zone,
        "universe_size": output.universe_size,
        "scored_count": output.scored_count,
        "skip_reason": output.skip_reason,
    }
