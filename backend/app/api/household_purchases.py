"""Item-level purchase tracking endpoints."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

if TYPE_CHECKING:
    from app.services.household_finance_service import HouseholdFinanceService

router = APIRouter(prefix="/api/household", tags=["household-purchases"])


@lru_cache(maxsize=1)
def _service() -> HouseholdFinanceService:
    return import_module("app.services.household_finance_service").HouseholdFinanceService()


@router.post("/purchase-items/backfill")
async def backfill_purchase_items() -> dict[str, int]:
    """Promote eligible import rows to purchase items and link pending groups."""
    return await run_in_threadpool(_service().purchase_item_service.backfill)


@router.post("/purchase-items/link")
async def link_purchase_groups() -> dict[str, int]:
    """Link pending purchase groups to ledger charges and allocate splits."""
    return await run_in_threadpool(_service().purchase_item_service.link_purchase_groups)
