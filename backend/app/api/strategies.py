"""API endpoints for strategy management."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query

from app.logging_config import get_logger
from app.strategies.storage import get_strategy_storage

from .strategies_generation import handle_generate_batch, handle_generate_strategy
from .strategies_handlers import (
    build_list_item,
    compute_summary_flags,
    get_strategy_or_404,
    handle_get_strategy,
    handle_get_strategy_performance,
    handle_update_strategy_status,
)
from .strategies_models import (
    GenerateBatchRequest,
    GenerateStrategyRequest,
    StrategyDetail,
    StrategySummary,
    UpdateStrategyStatusRequest,
)
from .strategies_signals import (
    handle_generate_strategy_signal,
    handle_get_strategy_evolution,
    handle_get_strategy_signal,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


@router.get("", response_model=dict[str, Any])
async def list_strategies(
    symbol: str | None = Query(None, description="Filter by symbol"),
    status: Literal["testing", "active", "archived"] | None = Query(
        None, description="Filter by status"
    ),
    strategy_type: str | None = Query(None, description="Filter by strategy type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> dict[str, Any]:
    """List strategies with filtering."""
    try:
        storage = get_strategy_storage()
        strategies = storage.list_strategies(
            symbol=symbol, status=status, strategy_type=strategy_type, limit=limit
        )
        items = [build_list_item(s) for s in strategies]
        return {"strategies": items, "total": len(items)}
    except Exception as e:
        logger.exception("Failed to list strategies", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list strategies: {e!s}") from e


@router.get("/summary", response_model=StrategySummary)
async def get_strategy_summary() -> StrategySummary:
    """Get strategy summary statistics."""
    try:
        storage = get_strategy_storage()
        strategies = storage.list_strategies(limit=500)
        expected_sharpes = [float(s.expected_sharpe) for s in strategies if s.expected_sharpe]
        live_sharpes = [float(s.live_sharpe_ratio) for s in strategies if s.live_sharpe_ratio]
        avg_expected = sum(expected_sharpes) / len(expected_sharpes) if expected_sharpes else None
        avg_live = sum(live_sharpes) / len(live_sharpes) if live_sharpes else None
        exceeding, meeting, underperforming = compute_summary_flags(strategies)
        return StrategySummary(
            total=len(strategies),
            active=sum(1 for s in strategies if s.status == "active"),
            testing=sum(1 for s in strategies if s.status == "testing"),
            archived=sum(1 for s in strategies if s.status == "archived"),
            avg_expected_sharpe=round(avg_expected, 2) if avg_expected else None,
            avg_live_sharpe=round(avg_live, 2) if avg_live else None,
            total_trades=sum(s.live_trades_count for s in strategies),
            exceeding_count=exceeding,
            meeting_count=meeting,
            underperforming_count=underperforming,
        )
    except Exception as e:
        logger.exception("Failed to get strategy summary", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get strategy summary: {e!s}") from e


@router.get("/{strategy_id}", response_model=StrategyDetail)
async def get_strategy(strategy_id: str) -> StrategyDetail:
    """Get strategy details with full configuration."""
    strategy = get_strategy_or_404(strategy_id)
    return await handle_get_strategy(strategy_id, strategy)


@router.post("/generate", response_model=dict[str, Any])
async def generate_strategy(request: GenerateStrategyRequest) -> dict[str, Any]:
    """Trigger strategy generation for symbol."""
    return await handle_generate_strategy(request)


@router.post("/generate-batch", response_model=dict[str, Any])
async def generate_batch(request: GenerateBatchRequest) -> dict[str, Any]:
    """Trigger batch strategy generation for multiple symbols."""
    return await handle_generate_batch(request)


@router.patch("/{strategy_id}", response_model=dict[str, Any])
async def update_strategy_status(
    strategy_id: str, request: UpdateStrategyStatusRequest
) -> dict[str, Any]:
    """Update strategy status (activate or archive)."""
    strategy = get_strategy_or_404(strategy_id)
    return await handle_update_strategy_status(
        strategy_id, strategy, request.status, request.archive_reason
    )


@router.get("/{strategy_id}/performance", response_model=dict[str, Any])
async def get_strategy_performance(strategy_id: str) -> dict[str, Any]:
    """Get performance comparison (backtest vs live)."""
    strategy = get_strategy_or_404(strategy_id)
    return handle_get_strategy_performance(strategy_id, strategy)


@router.get("/{strategy_id}/signal", response_model=dict[str, Any])
async def get_strategy_signal(strategy_id: str) -> dict[str, Any]:
    """Get current trading signal for a strategy."""
    strategy = get_strategy_or_404(strategy_id)
    return await handle_get_strategy_signal(strategy_id, strategy)


@router.post("/{strategy_id}/signal/generate", response_model=dict[str, Any])
async def generate_strategy_signal(strategy_id: str) -> dict[str, Any]:
    """Force generate a new signal for a strategy (ignores stored signals)."""
    strategy = get_strategy_or_404(strategy_id)
    return await handle_generate_strategy_signal(strategy_id, strategy)


@router.get("/{strategy_id}/evolution", response_model=dict[str, Any])
async def get_strategy_evolution(strategy_id: str) -> dict[str, Any]:
    """Get the full evolution timeline for a strategy.

    Shows: Seed -> Backtest -> Strategy -> Signals -> Trades -> Performance
    """
    strategy = get_strategy_or_404(strategy_id)
    return await handle_get_strategy_evolution(strategy_id, strategy)
