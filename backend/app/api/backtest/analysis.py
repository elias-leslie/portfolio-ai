"""
Backtest analysis endpoints.

Handles comparison of multiple backtests and Monte Carlo simulation.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.api.backtest.models import (
    ComparisonResponse,
    EquityBand,
    HistogramBin,
    MonteCarloRequest,
    MonteCarloResponse,
    MonteCarloStatisticsResponse,
    NormalizedEquityPointResponse,
    RunMetricsResponse,
)
from app.backtest.comparison import compare_backtests as do_compare_backtests
from app.backtest.models import BacktestEquity
from app.backtest.monte_carlo import run_monte_carlo
from app.backtest.storage import (
    get_backtest_equity_curve,
    get_backtest_run,
    get_backtest_trades,
)
from app.storage.connection import get_connection_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backtest"])


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
