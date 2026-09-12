"""Approved household card strategy operations."""
from functools import lru_cache
from importlib import import_module
from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from app.models.card_strategy import (
    BillDecision,
    ProposeStrategy,
    SavedStrategy,
    StrategyDecision,
    StrategySettings,
    StrategyView,
)
from app.services.card_strategy_service import CardStrategyService

router = APIRouter(prefix="/strategy")


@lru_cache(maxsize=1)
def _service() -> CardStrategyService:
    return CardStrategyService()


def _invalidate() -> None:
    import_module("app.api.household")._invalidate_household_cache()


@router.get("", response_model=StrategyView)
async def strategy_view():
    return await run_in_threadpool(_service().view)


@router.put("/settings", response_model=StrategySettings)
async def strategy_settings(body: StrategySettings):
    result = await run_in_threadpool(_service().save_settings, body)
    _invalidate()
    return result


@router.post("/plans", response_model=SavedStrategy)
async def strategy_proposal(body: ProposeStrategy):
    try:
        result = await run_in_threadpool(_service().propose, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _invalidate()
    return result


@router.post("/plans/{plan_id}", response_model=SavedStrategy)
async def strategy_decision(plan_id: UUID, body: StrategyDecision):
    try:
        result = await run_in_threadpool(_service().decide, str(plan_id), body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _invalidate()
    return result


@router.put("/plans/{plan_id}/bills/{merchant_key}", status_code=204)
async def strategy_bill_decision(plan_id: UUID, merchant_key: str, body: BillDecision):
    try:
        await run_in_threadpool(_service().bill_decision, str(plan_id), merchant_key, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _invalidate()
