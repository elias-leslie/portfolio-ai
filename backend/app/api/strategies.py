"""API endpoints for strategy management.

Provides REST API for:
- Listing strategies with filtering
- Getting strategy details
- Triggering strategy generation
- Updating strategy status (activate/archive)
- Viewing performance comparison
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.agents.workflows.strategy_research_workflow import strategy_research_workflow
from app.logging_config import get_logger
from app.strategies.storage import get_strategy_storage

logger = get_logger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])


# ============================================================================
# Request/Response Models
# ============================================================================


class StrategyListItem(BaseModel):
    """Strategy list item (summary view)."""

    id: str
    name: str
    symbol: str
    strategy_type: str
    status: Literal["testing", "active", "archived"]
    version: int
    expected_sharpe: float | None
    live_sharpe_ratio: float | None
    live_win_rate: float | None
    trades_count: int
    created_at: str
    activation_date: str | None


class StrategyDetail(BaseModel):
    """Strategy detail view (full data)."""

    id: str
    name: str
    symbol: str
    strategy_type: str
    parameters: dict[str, Any]
    research_summary: dict[str, Any]
    generation_reasoning: str
    backtest_metrics: list[dict[str, Any]]
    expected_sharpe: float | None
    expected_win_rate: float | None
    expected_max_drawdown: float | None
    live_trades_count: int
    live_win_rate: float | None
    live_sharpe_ratio: float | None
    status: Literal["testing", "active", "archived"]
    version: int
    created_at: str
    activation_date: str | None
    archive_date: str | None
    archive_reason: str | None
    performance_history: list[dict[str, Any]]


class GenerateStrategyRequest(BaseModel):
    """Request to generate new strategy."""

    symbol: str = Field(min_length=1, max_length=10)
    force_regenerate: bool = False


class UpdateStrategyStatusRequest(BaseModel):
    """Request to update strategy status."""

    status: Literal["active", "archived"]


# ============================================================================
# API Endpoints
# ============================================================================


@router.get("/", response_model=dict[str, Any])
async def list_strategies(
    symbol: str | None = Query(None, description="Filter by symbol"),
    status: Literal["testing", "active", "archived"] | None = Query(
        None, description="Filter by status"
    ),
    strategy_type: str | None = Query(None, description="Filter by strategy type"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> dict[str, Any]:
    """List strategies with filtering.

    Args:
        symbol: Filter by symbol (optional)
        status: Filter by status (optional)
        strategy_type: Filter by strategy type (optional)
        limit: Maximum results (default 50)

    Returns:
        Dict with strategies list and total count
    """
    try:
        storage = get_strategy_storage()
        strategies = storage.list_strategies(
            symbol=symbol,
            status=status,
            strategy_type=strategy_type,
            limit=limit,
        )

        # Convert to list items (summary view)
        items = [
            StrategyListItem(
                id=s.id,
                name=s.name,
                symbol=s.symbol,
                strategy_type=s.strategy_type,
                status=s.status,
                version=s.version,
                expected_sharpe=float(s.expected_sharpe) if s.expected_sharpe else None,
                live_sharpe_ratio=float(s.live_sharpe_ratio) if s.live_sharpe_ratio else None,
                live_win_rate=float(s.live_win_rate) if s.live_win_rate else None,
                trades_count=s.live_trades_count,
                created_at=s.created_at.isoformat(),
                activation_date=s.activation_date.isoformat() if s.activation_date else None,
            ).model_dump()
            for s in strategies
        ]

        return {
            "strategies": items,
            "total": len(items),
        }

    except Exception as e:
        logger.exception("Failed to list strategies", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list strategies: {e!s}")


@router.get("/{strategy_id}", response_model=StrategyDetail)
async def get_strategy(strategy_id: str) -> StrategyDetail:
    """Get strategy details with full configuration.

    Args:
        strategy_id: Strategy UUID

    Returns:
        Complete strategy details including parameters and performance history
    """
    try:
        storage = get_strategy_storage()
        strategy = storage.get_strategy_by_id(strategy_id)

        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Get performance history (last 30 days)
        conn_mgr = storage.conn
        with conn_mgr.connection() as conn:
            perf_rows = conn.execute(
                """
                SELECT date, trades_30d, win_rate_30d, sharpe_ratio_30d, max_drawdown_30d, status
                FROM strategy_performance
                WHERE strategy_id = %s
                ORDER BY date DESC
                LIMIT 30
                """,
                (strategy_id,),
            ).fetchall()

        # Convert tuples to dicts for easy access
        # Database returns tuples, map them to column names
        performance_history = []
        for row in perf_rows:
            # row is a tuple: (date, trades_30d, win_rate_30d, sharpe_ratio_30d, max_drawdown_30d, status)
            date_val = row[0]
            if isinstance(date_val, datetime):
                date_iso = date_val.isoformat()
            else:
                date_iso = str(date_val)

            performance_history.append(
                {
                    "date": date_iso,
                    "trades_30d": row[1],
                    "win_rate_30d": float(row[2]) if row[2] is not None else None,
                    "sharpe_ratio_30d": float(row[3]) if row[3] is not None else None,
                    "max_drawdown_30d": float(row[4]) if row[4] is not None else None,
                    "status": row[5],
                }
            )

        # Ensure backtest_metrics is a list (stored as JSON, might be dict)
        backtest_metrics: dict[str, Any] | list[dict[str, Any]] = strategy.backtest_metrics
        if isinstance(backtest_metrics, dict):
            # If stored as dict, convert to list for API response
            backtest_metrics_list: list[dict[str, Any]] = [backtest_metrics]
        else:
            backtest_metrics_list = backtest_metrics

        return StrategyDetail(
            id=strategy.id,
            name=strategy.name,
            symbol=strategy.symbol,
            strategy_type=strategy.strategy_type,
            parameters=strategy.parameters,
            research_summary=strategy.research_summary,
            generation_reasoning=strategy.generation_reasoning,
            backtest_metrics=backtest_metrics_list,
            expected_sharpe=float(strategy.expected_sharpe) if strategy.expected_sharpe else None,
            expected_win_rate=float(strategy.expected_win_rate)
            if strategy.expected_win_rate
            else None,
            expected_max_drawdown=float(strategy.expected_max_drawdown)
            if strategy.expected_max_drawdown
            else None,
            live_trades_count=strategy.live_trades_count,
            live_win_rate=float(strategy.live_win_rate) if strategy.live_win_rate else None,
            live_sharpe_ratio=float(strategy.live_sharpe_ratio)
            if strategy.live_sharpe_ratio
            else None,
            status=strategy.status,
            version=strategy.version,
            created_at=strategy.created_at.isoformat(),
            activation_date=strategy.activation_date.isoformat()
            if strategy.activation_date
            else None,
            archive_date=strategy.archive_date.isoformat() if strategy.archive_date else None,
            archive_reason=strategy.archive_reason,
            performance_history=performance_history,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to get strategy", strategy_id=strategy_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get strategy: {e!s}")


@router.post("/generate", response_model=dict[str, Any])
async def generate_strategy(request: GenerateStrategyRequest) -> dict[str, Any]:
    """Trigger strategy generation for symbol.

    Args:
        request: Generation request with symbol and force flag

    Returns:
        Workflow result with status and strategy_id (if successful)
    """
    try:
        logger.info(
            "Triggering strategy generation",
            symbol=request.symbol,
            force=request.force_regenerate,
        )

        # Trigger workflow (synchronous for now, can be async Celery task later)
        result = await strategy_research_workflow(
            symbol=request.symbol,
            force_regenerate=request.force_regenerate,
        )

        return result

    except Exception as e:
        logger.exception(
            "Strategy generation failed",
            symbol=request.symbol,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail=f"Strategy generation failed: {e!s}")


@router.patch("/{strategy_id}", response_model=dict[str, Any])
async def update_strategy_status(
    strategy_id: str,
    request: UpdateStrategyStatusRequest,
) -> dict[str, Any]:
    """Update strategy status (activate or archive).

    Args:
        strategy_id: Strategy UUID
        request: Status update request

    Returns:
        Updated strategy summary
    """
    try:
        storage = get_strategy_storage()
        strategy = storage.get_strategy_by_id(strategy_id)

        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        if request.status == "active":
            storage.activate_strategy(strategy_id)
            logger.info("Strategy activated", strategy_id=strategy_id)
            message = f"Strategy {strategy.name} activated"
        else:  # archived
            reason = "Manual archival via API"
            storage.archive_strategy(strategy_id, reason)
            logger.info("Strategy archived", strategy_id=strategy_id, reason=reason)
            message = f"Strategy {strategy.name} archived"

        # Get updated strategy
        updated = storage.get_strategy_by_id(strategy_id)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated strategy")

        return {
            "strategy": {
                "id": updated.id,
                "name": updated.name,
                "symbol": updated.symbol,
                "status": updated.status,
                "version": updated.version,
            },
            "message": message,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Failed to update strategy status", strategy_id=strategy_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to update strategy status: {e!s}")


@router.get("/{strategy_id}/performance", response_model=dict[str, Any])
async def get_strategy_performance(strategy_id: str) -> dict[str, Any]:
    """Get performance comparison (backtest vs live).

    Args:
        strategy_id: Strategy UUID

    Returns:
        Performance comparison with expected vs actual metrics
    """
    try:
        storage = get_strategy_storage()
        strategy = storage.get_strategy_by_id(strategy_id)

        if not strategy:
            raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

        # Calculate performance ratio
        expected_sharpe = float(strategy.expected_sharpe or 0.0)
        actual_sharpe = float(strategy.live_sharpe_ratio or 0.0)
        performance_ratio = actual_sharpe / expected_sharpe if expected_sharpe > 0 else 0.0

        # Determine status
        if strategy.live_trades_count == 0:
            status = "no_live_data"
        elif performance_ratio >= 0.9:
            status = "exceeding_expectations"
        elif performance_ratio >= 0.7:
            status = "meeting_expectations"
        else:
            status = "underperforming"

        return {
            "expected": {
                "sharpe": expected_sharpe,
                "win_rate": float(strategy.expected_win_rate)
                if strategy.expected_win_rate
                else None,
                "max_drawdown": float(strategy.expected_max_drawdown)
                if strategy.expected_max_drawdown
                else None,
            },
            "actual_30d": {
                "sharpe": actual_sharpe,
                "win_rate": float(strategy.live_win_rate) if strategy.live_win_rate else None,
                "trades_count": strategy.live_trades_count,
            },
            "performance_ratio": performance_ratio,
            "status": status,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            "Failed to get strategy performance", strategy_id=strategy_id, error=str(e)
        )
        raise HTTPException(status_code=500, detail=f"Failed to get strategy performance: {e!s}")
