"""TLH daily scan workflow.

Materializes the canonical ``TLHAnalyzer.find_loss_candidates`` output
into ``tlh_scan_results`` once per trading day so CLI/API reads are
O(1). The workflow truncates the day's rows up-front and reinserts in
a single transaction, so re-runs on the same day are safely idempotent
(matching the partial-unique index on ``(scan_date, account_id,
symbol)``).
"""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from ..hatchet_app import hatchet
from ..logging_config import get_logger
from .data_refresh_schedules import TLH_SCAN_CRONS
from .models import EmptyInput

logger = get_logger(__name__)

# Workflow scans up to this many candidates per day. Far above the
# typical token-efficient ``limit=20`` API default; the snapshot is
# meant to be the universe, not the agent-friendly view.
_SCAN_DEPTH = 200


def run_tlh_scan(scan_date: date | None = None) -> dict[str, Any]:
    """Run one TLH scan + snapshot pass synchronously.

    Exposed at module level so tests can drive it without the Hatchet
    runtime, and so the Hatchet task body stays a thin async shim.
    """
    from importlib import import_module

    storage = import_module("app.storage").get_storage()
    ledger_mod = import_module("app.portfolio.transactions")
    price_mod = import_module("app.portfolio.price_fetcher")
    tlh_mod = import_module("app.portfolio.tlh")

    ledger = ledger_mod.TransactionLedger(storage)
    price_fetcher = price_mod.PriceDataFetcher(storage)
    analyzer = tlh_mod.TLHAnalyzer(storage, ledger, price_fetcher)

    today = scan_date or date.today()
    candidates = analyzer.find_loss_candidates(
        min_loss_pct=0.0,
        min_loss_amount=0.0,
        limit=_SCAN_DEPTH,
        detail=True,
    )

    blocked = sum(1 for c in candidates if c.wash_sale_blocked)

    with storage.connection() as conn:
        # Idempotency: any prior rows for the day are removed before
        # reinsert. The partial-unique index would otherwise make a
        # naive INSERT collide on retry.
        conn.execute(
            "DELETE FROM tlh_scan_results WHERE scan_date = %s",
            [today],
        )
        for c in candidates:
            conn.execute(
                """
                INSERT INTO tlh_scan_results
                    (scan_date, symbol, account_id,
                     unrealized_loss, unrealized_loss_pct,
                     blocked_by_wash_sale, wash_sale_reason,
                     replacement_symbol, holding_period_days)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    today,
                    c.symbol,
                    c.account_id,
                    c.unrealized_loss,
                    c.unrealized_loss_pct,
                    c.wash_sale_blocked,
                    c.wash_sale_reason,
                    c.replacement.to_symbol if c.replacement else None,
                    c.holding_period_days,
                ],
            )
        conn.commit()

    logger.info(
        "tlh_scan_completed",
        scan_date=today.isoformat(),
        candidates_found=len(candidates),
        wash_sale_blocked=blocked,
    )
    return {
        "scan_date": today.isoformat(),
        "candidates_found": len(candidates),
        "wash_sale_blocked": blocked,
    }


@hatchet.task(
    name="portfolio-tlh-scan",
    input_validator=EmptyInput,
    execution_timeout="600s",
    retries=2,
    backoff_factor=2.0,
    on_crons=TLH_SCAN_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-tlh-scan'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def portfolio_tlh_scan_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    del input, ctx
    return await asyncio.to_thread(run_tlh_scan)
