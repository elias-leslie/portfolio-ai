"""Data-services account sync workflow.

Recurring sync of the brokerage/account aggregators (SnapTrade, Plaid) so
holdings, positions, and transactions stay current without the user opening
the app and pressing sync. Thin async wrapper around the existing service
sync methods; gated on the scheduled_account_sync_enabled preference.
"""

from __future__ import annotations

import asyncio
from typing import Any

from hatchet_sdk import ConcurrencyExpression, ConcurrencyLimitStrategy, Context

from app.logging_config import get_logger
from app.services.preferences_service import get_automation_preferences

from ..hatchet_app import hatchet
from .data_refresh_schedules import ACCOUNT_SYNC_CRONS
from .models import EmptyInput

logger = get_logger(__name__)


@hatchet.task(
    name="portfolio-sync-accounts",
    input_validator=EmptyInput,
    execution_timeout="1800s",
    retries=2,
    backoff_factor=2.0,
    on_crons=ACCOUNT_SYNC_CRONS,
    concurrency=ConcurrencyExpression(
        expression="'portfolio-sync-accounts'",
        max_runs=1,
        limit_strategy=ConcurrencyLimitStrategy.CANCEL_IN_PROGRESS,
    ),
)
async def sync_accounts_wf(input: EmptyInput, ctx: Context) -> dict[str, Any]:
    automation = get_automation_preferences()
    if not bool(automation["scheduled_account_sync_enabled"]["enabled"]):
        logger.info("account_sync_skipped_disabled")
        return {"status": "skipped", "reason": "scheduled_account_sync_disabled"}

    from app.services.plaid_service import PlaidService
    from app.services.snaptrade_service import SnapTradeService

    results: dict[str, Any] = {}

    # Isolate vendors: a failure in one must not block the other, so the
    # healthy feed still refreshes (and its freshness badge clears).
    try:
        results["snaptrade"] = await asyncio.to_thread(SnapTradeService().sync)
    except Exception as exc:
        logger.warning("account_sync_snaptrade_failed", error=str(exc))
        results["snaptrade"] = {"status": "error", "error": str(exc)}

    try:
        results["plaid"] = await asyncio.to_thread(PlaidService().sync_items)
    except Exception as exc:
        logger.warning("account_sync_plaid_failed", error=str(exc))
        results["plaid"] = {"status": "error", "error": str(exc)}

    return results
