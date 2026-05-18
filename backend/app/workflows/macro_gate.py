"""L1 macro deployment gate workflow.

Daily at 17:30 ET (22:30 UTC) — after the fear/greed inputs job and the
daily OHLCV refresh have both settled. Persists the snapshot and emits
``macro.gate.completed`` so the L2 scanner can chain off it.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from ..macro_gate.service import run as run_macro_gate
from .models import EmptyInput

MACRO_GATE_CRONS = ["30 22 * * 1-5"]  # Mon-Fri 17:30 ET (22:30 UTC, DST-conservative)


@hatchet.task(
    name="portfolio-macro-gate",
    input_validator=EmptyInput,
    execution_timeout="900s",
    retries=2,
    backoff_factor=2.0,
    on_crons=MACRO_GATE_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-macro-gate'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def macro_gate_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    output = await asyncio.to_thread(run_macro_gate)
    if output is None:
        return {"status": "skipped", "reason": "no_inputs"}

    # Chain L2 scanner. Imported lazily to avoid cyclic registration at
    # Hatchet boot. ``aio_run_no_wait`` returns immediately so the gate
    # task isn't held open while the scanner runs.
    from .scanner import scanner_wf

    await scanner_wf.aio_run_no_wait(EmptyInput())

    return {
        "status": "ok",
        "snapshot_date": output.snapshot_date.isoformat(),
        "deployment_score": output.deployment_score,
        "zone": output.zone,
        "coverage": output.coverage,
    }
