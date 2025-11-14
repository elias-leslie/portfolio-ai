"""
Backtesting API endpoints.

Provides REST API for running backtests, retrieving results, and managing backtest runs.

Endpoints:
- POST /api/backtest/run - Start backtest (async via Celery)
- GET /api/backtest/runs - List backtest runs
- GET /api/backtest/runs/{run_id} - Get backtest details
- GET /api/backtest/runs/{run_id}/equity - Get equity curve
- DELETE /api/backtest/runs/{run_id} - Delete backtest

Phase A MVP: Single-symbol backtests with signal_classifier strategy
Phase B: Multi-symbol portfolios, custom strategies, optimization
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.backtest.models import BacktestEquity, BacktestResult
from app.backtest.storage import (
    create_backtest_run,
    delete_backtest_run,
    get_backtest_equity_curve,
    get_backtest_run,
    get_backtest_trades,
    list_backtest_runs,
    update_backtest_status,
)
from app.storage.connection import get_connection_manager
from app.tasks.backtest_tasks import run_backtest_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


# ============================================================================
# Request/Response Models
# ============================================================================


class StartBacktestRequest(BaseModel):
    """Request model for starting a backtest."""

    symbol: str = Field(..., min_length=1, max_length=20, description="Stock symbol (e.g., AAPL)")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    initial_capital: Decimal = Field(
        default=Decimal("100000.00"), gt=0, description="Starting capital in dollars"
    )
    strategy_name: Literal["signal_classifier"] = Field(
        default="signal_classifier", description="Strategy to use"
    )
    min_signal_strength: int = Field(
        default=7, ge=1, le=10, description="Minimum signal strength for entry"
    )
    max_holding_days: int = Field(default=60, gt=0, description="Maximum holding period in days")
    position_sizing_method: Literal["fixed_dollars", "fixed_shares"] = Field(
        default="fixed_dollars"
    )
    position_size_value: Decimal = Field(
        default=Decimal("10000.00"), gt=0, description="Position size (dollars or shares)"
    )


class StartBacktestResponse(BaseModel):
    """Response model for starting a backtest."""

    run_id: str
    task_id: str
    status: str
    message: str


class BacktestRunListItem(BaseModel):
    """Summary model for backtest run in list view."""

    id: str
    symbol: str
    strategy_name: str
    start_date: date
    end_date: date
    total_return_pct: Decimal | None
    sharpe_ratio: Decimal | None
    win_rate: Decimal | None
    num_trades: int | None
    status: str
    created_at: str


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/run", response_model=StartBacktestResponse)
async def start_backtest(request: StartBacktestRequest) -> StartBacktestResponse:
    """Start a new backtest.

    Creates backtest_run record and launches Celery task for async execution.

    Args:
        request: Backtest configuration

    Returns:
        Run ID, task ID, and status

    Raises:
        HTTPException 400: Invalid parameters (e.g., end_date < start_date)
        HTTPException 500: Database error
    """
    # Validate date range
    if request.end_date < request.start_date:
        raise HTTPException(
            status_code=400,
            detail=f"end_date ({request.end_date}) must be >= start_date ({request.start_date})",
        )

    try:
        storage_mgr = get_connection_manager()

        # Create backtest run record
        run_id = create_backtest_run(
            storage=storage_mgr,
            strategy_name=request.strategy_name,
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
        )

        # Update status to "running"
        update_backtest_status(storage_mgr, run_id, "running")

        # Launch Celery task (async execution)
        task = run_backtest_task.delay(
            run_id=run_id,
            symbol=request.symbol,
            start_date=request.start_date.isoformat(),
            end_date=request.end_date.isoformat(),
            initial_capital=float(request.initial_capital),
            strategy_name=request.strategy_name,
            min_signal_strength=request.min_signal_strength,
            max_holding_days=request.max_holding_days,
            position_sizing_method=request.position_sizing_method,
            position_size_value=float(request.position_size_value),
        )

        logger.info(f"Started backtest: {run_id} | Task: {task.id} | Symbol: {request.symbol}")

        return StartBacktestResponse(
            run_id=run_id,
            task_id=task.id,
            status="running",
            message=f"Backtest started for {request.symbol} ({request.start_date} to {request.end_date})",
        )

    except Exception as e:
        logger.error(f"Failed to start backtest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start backtest: {e!s}") from e


@router.get("/runs", response_model=list[BacktestRunListItem])
async def get_backtest_runs_list(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of runs to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
    symbol: str | None = Query(default=None, description="Filter by symbol"),
    status: str | None = Query(default=None, description="Filter by status"),
) -> list[BacktestRunListItem]:
    """List backtest runs with optional filtering.

    Args:
        limit: Maximum number of runs to return
        offset: Pagination offset
        symbol: Filter by symbol (optional)
        status: Filter by status (optional)

    Returns:
        List of backtest runs (ordered by created_at DESC)

    Raises:
        HTTPException 500: Database error
    """
    try:
        storage_mgr = get_connection_manager()

        runs = list_backtest_runs(
            storage=storage_mgr,
            limit=limit,
            offset=offset,
            symbol=symbol,
            status=status,
        )

        return [
            BacktestRunListItem(
                id=run.id,
                symbol=run.symbol,
                strategy_name=run.strategy_name,
                start_date=run.start_date,
                end_date=run.end_date,
                total_return_pct=run.total_return_pct,
                sharpe_ratio=run.sharpe_ratio,
                win_rate=run.win_rate,
                num_trades=run.num_trades,
                status=run.status,
                created_at=run.created_at.isoformat(),
            )
            for run in runs
        ]

    except Exception as e:
        logger.error(f"Failed to list backtest runs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list backtest runs: {e!s}") from e


@router.get("/runs/{run_id}", response_model=BacktestResult)
async def get_backtest_details(run_id: str) -> BacktestResult:
    """Get complete backtest details including trades and equity curve.

    Args:
        run_id: Backtest run ID (UUID)

    Returns:
        Complete backtest result with run metadata, trades, and equity curve

    Raises:
        HTTPException 404: Backtest not found
        HTTPException 500: Database error
    """
    try:
        storage_mgr = get_connection_manager()

        # Fetch run
        run = get_backtest_run(storage_mgr, run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Backtest {run_id} not found")

        # Fetch trades and equity curve
        trades = get_backtest_trades(storage_mgr, run_id)
        equity_curve = get_backtest_equity_curve(storage_mgr, run_id)

        # Calculate additional metrics
        winning_trades = [t for t in trades if t.pnl and t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl and t.pnl < 0]

        avg_win = (
            Decimal(str(sum(t.pnl for t in winning_trades) / len(winning_trades)))  # type: ignore[misc]
            if winning_trades
            else Decimal("0.0")
        )
        avg_loss = (
            Decimal(str(abs(sum(t.pnl for t in losing_trades) / len(losing_trades))))  # type: ignore[misc]
            if losing_trades
            else Decimal("0.0")
        )
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else Decimal("0.0")

        total_days = len(equity_curve)

        return BacktestResult(
            run=run,
            trades=trades,
            equity_curve=equity_curve,
            avg_win=avg_win,
            avg_loss=avg_loss,
            win_loss_ratio=win_loss_ratio,
            num_wins=len(winning_trades),
            num_losses=len(losing_trades),
            total_days=total_days,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get backtest details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get backtest details: {e!s}") from e


@router.get("/runs/{run_id}/equity", response_model=list[BacktestEquity])
async def get_equity_curve(run_id: str) -> list[BacktestEquity]:
    """Get equity curve for backtest (for charting).

    Args:
        run_id: Backtest run ID (UUID)

    Returns:
        List of daily equity snapshots (ordered by date)

    Raises:
        HTTPException 404: Backtest not found
        HTTPException 500: Database error
    """
    try:
        storage_mgr = get_connection_manager()

        # Verify run exists
        run = get_backtest_run(storage_mgr, run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Backtest {run_id} not found")

        # Fetch equity curve
        equity_curve = get_backtest_equity_curve(storage_mgr, run_id)

        return equity_curve

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get equity curve: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get equity curve: {e!s}") from e


@router.delete("/runs/{run_id}")
async def delete_backtest(run_id: str) -> dict[str, str]:
    """Delete backtest run and all associated data.

    Cascade deletes trades and equity snapshots automatically.

    Args:
        run_id: Backtest run ID (UUID)

    Returns:
        Success message

    Raises:
        HTTPException 404: Backtest not found
        HTTPException 500: Database error
    """
    try:
        storage_mgr = get_connection_manager()

        deleted = delete_backtest_run(storage_mgr, run_id)

        if not deleted:
            raise HTTPException(status_code=404, detail=f"Backtest {run_id} not found")

        return {"message": f"Backtest {run_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete backtest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete backtest: {e!s}") from e
