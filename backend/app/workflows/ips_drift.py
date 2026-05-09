"""IPS drift snapshot workflow.

Materializes ``DriftCalculator.compute_drift`` into ``ips_drift_history``
once per day so trend charts and the drift page can render in O(1).
The workflow scans every distinct ``(scope, scope_id)`` that has IPS
targets and writes one row per asset class. Re-runs on the same day are
idempotent thanks to the table's composite PK.
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from ..logging_config import get_logger
from .data_refresh_schedules import IPS_DRIFT_SNAPSHOT_CRONS
from .models import EmptyInput

logger = get_logger(__name__)


def run_drift_snapshot(snapshot_date: date | None = None) -> dict[str, Any]:
    """Run one drift-snapshot pass synchronously.

    Exposed at module level so tests can drive it without the Hatchet
    runtime, and so the Hatchet task body stays a thin async shim.
    """
    from importlib import import_module

    storage = import_module("app.storage").get_storage()
    ips_mod = import_module("app.portfolio.ips")
    ac_mod = import_module("app.portfolio.asset_classification")
    price_mod = import_module("app.portfolio.price_fetcher")

    ips_service = ips_mod.IPSService(storage)
    classifier = ac_mod.AssetClassifier(storage)
    price_fetcher = price_mod.PriceDataFetcher(storage)
    drift_calc = ips_mod.DriftCalculator(storage, classifier, ips_service, price_fetcher)

    today = snapshot_date or date.today()
    scopes = ips_service.list_scopes()
    rows_written = 0
    scopes_processed = 0

    with storage.connection() as conn:
        for scope_value, scope_id in scopes:
            try:
                report = drift_calc.compute_drift(scope_value, scope_id, snapshot_date=today)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(
                    "ips_drift_snapshot_scope_failed",
                    scope=scope_value,
                    scope_id=scope_id,
                    error=str(exc),
                )
                continue
            scopes_processed += 1
            for row in report.rows:
                conn.execute(
                    """
                    INSERT INTO ips_drift_history
                        (scope, scope_id, asset_class, snapshot_date,
                         target_pct, actual_pct, drift_pct, total_value)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (scope, scope_id, asset_class, snapshot_date) DO UPDATE SET
                        target_pct = EXCLUDED.target_pct,
                        actual_pct = EXCLUDED.actual_pct,
                        drift_pct = EXCLUDED.drift_pct,
                        total_value = EXCLUDED.total_value
                    """,
                    [
                        scope_value,
                        scope_id,
                        row.asset_class,
                        today,
                        row.target_pct,
                        row.actual_pct,
                        row.drift_pct,
                        report.total_value,
                    ],
                )
                rows_written += 1
        conn.commit()

    logger.info(
        "ips_drift_snapshot_completed",
        snapshot_date=today.isoformat(),
        scopes_processed=scopes_processed,
        rows_written=rows_written,
    )
    return {
        "snapshot_date": today.isoformat(),
        "scopes_processed": scopes_processed,
        "rows_written": rows_written,
    }


@hatchet.task(
    name="portfolio-drift-snapshot",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=2,
    backoff_factor=2.0,
    on_crons=IPS_DRIFT_SNAPSHOT_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-drift-snapshot'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def portfolio_drift_snapshot_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    del input, ctx
    return await asyncio.to_thread(run_drift_snapshot)
