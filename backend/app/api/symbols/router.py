"""Symbol Intelligence API router."""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from importlib import import_module
from typing import TYPE_CHECKING

from fastapi import APIRouter
from fastapi.concurrency import run_in_threadpool

from app.logging_config import get_logger
from app.models.symbol_workflow import (
    SymbolWorkflow,
    SymbolWorkflowOutcomeRequest,
    SymbolWorkflowTransitionRequest,
)

from .models import SymbolIntelligenceResponse
from .service import build_symbol_intelligence

if TYPE_CHECKING:
    from app.services.symbol_workflow_service import SymbolWorkflowService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/symbols", tags=["symbols"])


@lru_cache(maxsize=1)
def _workflow_service() -> SymbolWorkflowService:
    return import_module("app.services.symbol_workflow_service").SymbolWorkflowService()


@router.get("/{symbol}/intelligence", response_model=SymbolIntelligenceResponse)
async def get_symbol_intelligence(
    symbol: str,
    include_market: bool = True,
    include_strategies: bool = True,
) -> SymbolIntelligenceResponse:
    """Get comprehensive intelligence for a symbol.

    Returns all relevant data in one call:
    - Watchlist scores and signals
    - Portfolio position (if held)
    - Paper trading history
    - Active strategies
    - News sentiment
    - Market context
    - Personalized recommendation
    """
    try:
        return await run_in_threadpool(build_symbol_intelligence, symbol, include_market, include_strategies)
    except Exception as e:
        logger.exception("symbol_intelligence_failed", symbol=symbol)
        return SymbolIntelligenceResponse(
            symbol=symbol.upper(), generated_at=datetime.now(UTC), error=str(e)
        )


@router.get("/{symbol}/workflow", response_model=SymbolWorkflow)
async def get_symbol_workflow(symbol: str) -> SymbolWorkflow:
    """Return the persisted operating workflow for a symbol."""
    payload = await run_in_threadpool(_workflow_service().get_workflow, symbol)
    return SymbolWorkflow.model_validate(payload)


@router.post("/{symbol}/workflow/transition", response_model=SymbolWorkflow)
async def transition_symbol_workflow(
    symbol: str,
    payload: SymbolWorkflowTransitionRequest,
) -> SymbolWorkflow:
    """Advance or reset a symbol inside the investing workflow loop."""
    workflow_service = _workflow_service()
    result = await run_in_threadpool(
        workflow_service.transition,
        symbol,
        payload.stage,
        payload.note,
    )
    return SymbolWorkflow.model_validate(result)


@router.post("/{symbol}/workflow/outcome", response_model=SymbolWorkflow)
async def record_symbol_workflow_outcome(
    symbol: str,
    payload: SymbolWorkflowOutcomeRequest,
) -> SymbolWorkflow:
    """Capture a live position decision with linked Jenny context."""
    workflow_service = _workflow_service()
    result = await run_in_threadpool(
        lambda: workflow_service.record_outcome(
            symbol,
            payload.action,
            payload.note,
            jenny_verdict=payload.jenny_verdict,
            management_action=payload.management_action,
        )
    )
    return SymbolWorkflow.model_validate(result)
