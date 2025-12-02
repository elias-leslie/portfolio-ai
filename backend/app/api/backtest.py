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

from app.backtest.comparison import (
    compare_backtests as do_compare_backtests,
)
from app.backtest.models import BacktestEquity, BacktestResult
from app.backtest.monte_carlo import run_monte_carlo
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


class StrategyParametersRequest(BaseModel):
    """Optional strategy parameters for backtest customization."""

    stop_loss_atr_multiplier: Decimal = Field(
        default=Decimal("2.0"), gt=0, le=5, description="Stop loss in ATR multiples (1.0-5.0)"
    )
    max_holding_days: int = Field(
        default=30, gt=0, le=365, description="Maximum holding period in days"
    )
    target_profit_pct: Decimal = Field(
        default=Decimal("15.0"), gt=0, le=100, description="Target profit percentage"
    )
    min_confirmations: int = Field(
        default=5, ge=3, le=8, description="Minimum confirmations for entry (3-8)"
    )


class StartBacktestRequest(BaseModel):
    """Request model for starting a backtest."""

    symbol: str = Field(..., min_length=1, max_length=20, description="Stock symbol (e.g., AAPL)")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    initial_capital: Decimal = Field(
        default=Decimal("100000.00"), gt=0, description="Starting capital in dollars"
    )
    strategy: Literal[
        "signal_classifier", "enhanced", "momentum", "mean_reversion", "trend_following"
    ] = Field(default="enhanced", description="Strategy to use")
    parameters: StrategyParametersRequest | None = Field(
        default=None, description="Optional strategy parameters"
    )
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


class NormalizedEquityPointResponse(BaseModel):
    """Normalized equity point for comparison charts."""

    date: date
    cumulative_return_pct: Decimal


class RunMetricsResponse(BaseModel):
    """Metrics summary for a single backtest run with rankings."""

    run_id: str
    symbol: str
    strategy_name: str
    start_date: date
    end_date: date
    total_return_pct: Decimal | None
    sharpe_ratio: Decimal | None
    max_drawdown_pct: Decimal | None
    win_rate: Decimal | None
    num_trades: int | None
    profit_factor: Decimal | None
    return_rank: int | None
    sharpe_rank: int | None
    drawdown_rank: int | None


class ComparisonResponse(BaseModel):
    """Complete comparison response for multiple backtest runs."""

    equity_curves: dict[str, list[NormalizedEquityPointResponse]]
    metrics: list[RunMetricsResponse]
    correlation_matrix: dict[str, dict[str, float]] | None


class MonteCarloStatisticsResponse(BaseModel):
    """Statistics from Monte Carlo simulation."""

    num_simulations: int
    percentile_5: float
    percentile_25: float
    percentile_50: float
    percentile_75: float
    percentile_95: float
    probability_of_loss: float
    value_at_risk_95: float
    expected_shortfall: float
    mean_return: float
    std_dev: float
    skewness: float
    kurtosis: float
    original_return: float


class HistogramBin(BaseModel):
    """Single histogram bin."""

    bin_start: float
    bin_end: float
    frequency: float


class EquityBand(BaseModel):
    """Single equity band data point."""

    step: int
    p5: float
    p50: float
    p95: float


class MonteCarloRequest(BaseModel):
    """Request model for Monte Carlo simulation."""

    num_simulations: int = Field(
        default=1000, ge=100, le=10000, description="Number of simulations"
    )
    seed: int | None = Field(default=None, description="Random seed for reproducibility")


class MonteCarloResponse(BaseModel):
    """Complete Monte Carlo simulation response."""

    statistics: MonteCarloStatisticsResponse
    histogram_data: list[HistogramBin]
    equity_bands: list[EquityBand]
    created_at: str


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/run", response_model=StartBacktestResponse)
async def start_backtest(request: StartBacktestRequest) -> StartBacktestResponse:
    """Start a new backtest.

    Creates backtest_run record and launches Celery task for async execution.

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

        # Launch Celery task (async execution)
        task = run_backtest_task.delay(
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


class StrategyDetailsResponse(BaseModel):
    """Detailed strategy information for UI and AI agent consumption."""

    id: str
    name: str
    short_description: str
    when_to_use: str
    market_conditions: str
    holding_period: str
    risk_level: Literal["Low", "Medium", "High"]
    best_for: str
    avoid_when: str


# Strategy details - matching frontend STRATEGIES constant
STRATEGY_DETAILS = {
    "enhanced": StrategyDetailsResponse(
        id="enhanced",
        name="Enhanced Signal",
        short_description="Multi-confirmation technical strategy with configurable parameters",
        when_to_use="Default choice for most backtests. Use when you want balanced risk/reward with tunable parameters.",
        market_conditions="Works in trending and range-bound markets. Requires 5+ of 8 technical confirmations (price > EMA, healthy RSI, positive MACD, volume, momentum alignment).",
        holding_period="5-30 days typical, configurable up to 120 days",
        risk_level="Medium",
        best_for="Stocks with clear technical patterns, moderate volatility (ATR 2-4%), good liquidity (>1M daily volume)",
        avoid_when="Choppy sideways markets, low-volume stocks, earnings week, extreme VIX (>30)",
    ),
    "signal_classifier": StrategyDetailsResponse(
        id="signal_classifier",
        name="Signal Classifier",
        short_description="Original rule-based classifier requiring 10+ confirmations including fundamentals",
        when_to_use="Use when you have fundamental data available and want stricter entry criteria.",
        market_conditions="Requires fundamental/analyst data for full scoring. Technical-only mode generates fewer signals. Best in stable uptrends.",
        holding_period="30-60 days typical",
        risk_level="Low",
        best_for="Blue-chip stocks with analyst coverage, stocks with recent earnings beats, sectors showing institutional accumulation",
        avoid_when="Small-caps without analyst coverage, pre-earnings periods, sectors under regulatory scrutiny",
    ),
    "momentum": StrategyDetailsResponse(
        id="momentum",
        name="Momentum",
        short_description="Rides intermediate-term momentum with multi-horizon confirmation",
        when_to_use="Use in strong bull markets or when a stock is breaking out of consolidation with volume.",
        market_conditions="Best when: SPY > 200 SMA, sector showing relative strength, stock RSI 50-70 (bullish but not overbought). Uses 20/60/252-day momentum scoring.",
        holding_period="30-60 days, exits on momentum fade (RSI < 40)",
        risk_level="High",
        best_for="Growth stocks in uptrends, sector leaders, stocks with institutional buying, post-earnings momentum plays",
        avoid_when="Bear markets, mean-reverting sectors (utilities), stocks with declining volume, late-cycle rallies",
    ),
    "mean_reversion": StrategyDetailsResponse(
        id="mean_reversion",
        name="Mean Reversion",
        short_description="Catches oversold bounces in fundamentally strong stocks",
        when_to_use="Use when quality stocks are temporarily oversold (RSI < 30) but still in long-term uptrend (price > 200 SMA).",
        market_conditions="Best in: range-bound markets, after sector pullbacks, when VIX spikes then reverses. Requires uptrend context to avoid catching falling knives.",
        holding_period="3-10 days (quick trades), tight stops",
        risk_level="Medium",
        best_for="Large-caps with temporary weakness, dividend stocks after ex-date drops, quality names hit by sector rotation",
        avoid_when="Downtrending stocks (price < 200 SMA), fundamental deterioration, high-beta names in bear markets",
    ),
    "trend_following": StrategyDetailsResponse(
        id="trend_following",
        name="Trend Following",
        short_description="Follows strong trends with trailing ATR stops, lets winners run",
        when_to_use="Use for long-term trend capture when all moving averages are aligned (price > 20 SMA > 50 SMA > 200 SMA).",
        market_conditions="Best in: strong bull markets, sector rotations with clear leaders, breakouts from long bases. Requires perfect SMA alignment for entry.",
        holding_period="60-120+ days, no fixed profit target",
        risk_level="Medium",
        best_for="Trending sectors (tech in bull markets), stocks making new highs, ETFs with clear directional bias",
        avoid_when="Choppy/sideways markets, stocks in trading ranges, high-volatility periods (earnings, FOMC), mean-reverting assets",
    ),
}


@router.get("/strategies", response_model=list[StrategyDetailsResponse])
async def get_available_strategies() -> list[StrategyDetailsResponse]:
    """Get list of available backtest strategies with detailed information.

    Returns detailed information about each strategy including:
    - When to use the strategy
    - Ideal market conditions
    - Typical holding period
    - Risk level
    - Best use cases and situations to avoid

    This endpoint is designed for both UI display and AI agent consumption.
    AI agents can use this data to recommend appropriate strategies based on
    current market conditions and user goals.

    Returns:
        List of strategy details
    """
    return list(STRATEGY_DETAILS.values())


@router.get("/strategies/{strategy_id}", response_model=StrategyDetailsResponse)
async def get_strategy_details(strategy_id: str) -> StrategyDetailsResponse:
    """Get detailed information about a specific strategy.

    Args:
        strategy_id: Strategy identifier (enhanced, signal_classifier, momentum, etc.)

    Returns:
        Strategy details

    Raises:
        HTTPException 404: Strategy not found
    """
    if strategy_id not in STRATEGY_DETAILS:
        raise HTTPException(
            status_code=404,
            detail=f"Strategy '{strategy_id}' not found. Available: {list(STRATEGY_DETAILS.keys())}",
        )
    return STRATEGY_DETAILS[strategy_id]


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


@router.post("/compare", response_model=ComparisonResponse)
async def compare_backtests(
    run_ids: list[str] = Query(..., description="List of run IDs to compare (2-5 runs)"),
) -> ComparisonResponse:
    """Compare multiple backtest runs with normalized equity curves and metrics.

    Query Parameters:
        run_ids: List of 2-5 backtest run IDs to compare

    Returns:
        ComparisonResponse with:
        - equity_curves: Normalized equity curves (starting at 0% return)
        - metrics: Side-by-side metrics with rankings
        - correlation_matrix: Strategy correlation (if overlapping dates exist)

    Raises:
        HTTPException 400: Invalid number of run_ids (must be 2-5)
        HTTPException 404: One or more runs not found
        HTTPException 500: Database error
    """
    try:
        if len(run_ids) < 2:
            raise HTTPException(
                status_code=400, detail="Must provide at least 2 run IDs to compare"
            )

        if len(run_ids) > 5:
            raise HTTPException(status_code=400, detail="Cannot compare more than 5 runs at once")

        storage_mgr = get_connection_manager()

        # Fetch runs and equity curves for all runs
        runs = []
        equity_curves: dict[str, list[BacktestEquity]] = {}

        for run_id in run_ids:
            run = get_backtest_run(storage_mgr, run_id)
            if not run:
                raise HTTPException(status_code=404, detail=f"Backtest {run_id} not found")
            runs.append(run)

            equity_data = get_backtest_equity_curve(storage_mgr, run_id)
            if not equity_data:
                raise HTTPException(
                    status_code=404,
                    detail=f"Backtest {run_id} has no equity data",
                )
            equity_curves[run_id] = equity_data

        # Use comparison module for analysis
        comparison = do_compare_backtests(runs, equity_curves)

        # Convert to response format
        equity_response: dict[str, list[NormalizedEquityPointResponse]] = {}
        for run_id, points in comparison.equity_curves.items():
            equity_response[run_id] = [
                NormalizedEquityPointResponse(
                    date=p.date,
                    cumulative_return_pct=p.cumulative_return_pct,
                )
                for p in points
            ]

        metrics_response = [
            RunMetricsResponse(
                run_id=m.run_id,
                symbol=m.symbol,
                strategy_name=m.strategy_name,
                start_date=m.start_date,
                end_date=m.end_date,
                total_return_pct=m.total_return_pct,
                sharpe_ratio=m.sharpe_ratio,
                max_drawdown_pct=m.max_drawdown_pct,
                win_rate=m.win_rate,
                num_trades=m.num_trades,
                profit_factor=m.profit_factor,
                return_rank=m.return_rank,
                sharpe_rank=m.sharpe_rank,
                drawdown_rank=m.drawdown_rank,
            )
            for m in comparison.metrics
        ]

        logger.info(f"Compared {len(run_ids)} backtest runs with metrics and correlation")

        return ComparisonResponse(
            equity_curves=equity_response,
            metrics=metrics_response,
            correlation_matrix=comparison.correlation_matrix,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to compare backtests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to compare backtests: {e!s}") from e


@router.post("/runs/{run_id}/monte-carlo", response_model=MonteCarloResponse)
async def run_monte_carlo_simulation(
    run_id: str,
    request: MonteCarloRequest,
) -> MonteCarloResponse:
    """Run Monte Carlo simulation on a completed backtest.

    Uses bootstrap resampling of trade returns to estimate the distribution
    of possible outcomes and risk metrics.

    Args:
        run_id: Backtest run ID (UUID)
        request: Simulation parameters (num_simulations, seed)

    Returns:
        MonteCarloResponse with:
        - statistics: Percentiles, VaR, probability of loss, etc.
        - histogram_data: Return distribution for visualization
        - equity_bands: Confidence bands at each trade step

    Raises:
        HTTPException 400: Backtest not completed or has no trades
        HTTPException 404: Backtest not found
        HTTPException 500: Simulation error
    """
    try:
        storage_mgr = get_connection_manager()

        # Verify run exists and is completed
        run = get_backtest_run(storage_mgr, run_id)
        if not run:
            raise HTTPException(status_code=404, detail=f"Backtest {run_id} not found")

        if run.status != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Backtest must be completed to run Monte Carlo (status: {run.status})",
            )

        # Get trades
        trades = get_backtest_trades(storage_mgr, run_id)
        if not trades:
            raise HTTPException(
                status_code=400,
                detail="Backtest has no trades - cannot run Monte Carlo simulation",
            )

        # Run simulation
        result = run_monte_carlo(
            trades=trades,
            num_simulations=request.num_simulations,
            seed=request.seed,
        )

        # Convert to response format
        stats = result.statistics
        response = MonteCarloResponse(
            statistics=MonteCarloStatisticsResponse(
                num_simulations=stats.num_simulations,
                percentile_5=stats.percentile_5,
                percentile_25=stats.percentile_25,
                percentile_50=stats.percentile_50,
                percentile_75=stats.percentile_75,
                percentile_95=stats.percentile_95,
                probability_of_loss=stats.probability_of_loss,
                value_at_risk_95=stats.value_at_risk_95,
                expected_shortfall=stats.expected_shortfall,
                mean_return=stats.mean_return,
                std_dev=stats.std_dev,
                skewness=stats.skewness,
                kurtosis=stats.kurtosis,
                original_return=stats.original_return,
            ),
            histogram_data=[
                HistogramBin(
                    bin_start=h["bin_start"],
                    bin_end=h["bin_end"],
                    frequency=h["frequency"],
                )
                for h in result.histogram_data
            ],
            equity_bands=[
                EquityBand(
                    step=int(e["step"]),
                    p5=e["p5"],
                    p50=e["p50"],
                    p95=e["p95"],
                )
                for e in result.equity_bands
            ],
            created_at=result.created_at.isoformat(),
        )

        logger.info(f"Monte Carlo simulation complete: {run_id} | {request.num_simulations} sims")

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run Monte Carlo simulation: {e}")
        raise HTTPException(status_code=500, detail=f"Monte Carlo simulation failed: {e!s}") from e
