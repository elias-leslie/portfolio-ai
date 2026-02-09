"""
Core backtest CRUD endpoints.

Handles backtest lifecycle: create, list, get details, get equity curve, delete.
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.backtest.models import (
    BacktestRunListItem,
    StartBacktestRequest,
    StartBacktestResponse,
    StrategyParametersRequest,
)
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
from app.middleware.cache import cache_response, invalidate_endpoint_cache
from app.storage.connection import get_connection_manager
from app.tasks.backtest_tasks import run_backtest_task

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backtest"])


@router.post("/run", response_model=StartBacktestResponse)
async def start_backtest(request: StartBacktestRequest) -> StartBacktestResponse:
    """Start a new backtest.

    Creates backtest_run record and launches task for async execution.

    Args:
        request: Backtest configuration including optional strategy parameters

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
            strategy_name=request.strategy,
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
        )

        # Update status to "running"
        update_backtest_status(storage_mgr, run_id, "running")

        # Extract parameters with defaults
        params = request.parameters or StrategyParametersRequest()

        # Launch backtest task (async execution)
        task = run_backtest_task(
            run_id=run_id,
            symbol=request.symbol,
            start_date=request.start_date.isoformat(),
            end_date=request.end_date.isoformat(),
            initial_capital=float(request.initial_capital),
            strategy_name=request.strategy,
            stop_loss_atr_multiplier=float(params.stop_loss_atr_multiplier),
            max_holding_days=params.max_holding_days,
            target_profit_pct=float(params.target_profit_pct),
            min_confirmations=params.min_confirmations,
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
@cache_response(ttl=30)  # 30 seconds cache for runs list
async def get_backtest_runs_list(
    request: Request,
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

        # Invalidate the cached runs list so next GET returns fresh data
        invalidate_endpoint_cache("/api/backtest/runs")

        return {"message": f"Backtest {run_id} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete backtest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete backtest: {e!s}") from e
