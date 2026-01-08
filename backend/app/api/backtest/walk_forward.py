"""
Walk-forward validation endpoint.

Provides out-of-sample testing with statistical significance testing.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.backtest.models import (
    FoldMetricsResponse,
    WalkForwardRequest,
    WalkForwardResponse,
)
from app.backtest.walk_forward import WalkForwardEngine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["backtest"])


@router.post("/walk-forward", response_model=WalkForwardResponse)
async def run_walk_forward_validation(request: WalkForwardRequest) -> WalkForwardResponse:
    """Run walk-forward validation with statistical significance testing.

    Walk-forward validation uses rolling out-of-sample testing to evaluate
    strategy robustness:

    1. Splits data into multiple overlapping windows
    2. Each window has: TRAIN → GAP → VALIDATE → GAP → TEST periods
    3. Tests strategy on TEST period only (true out-of-sample)
    4. Aggregates metrics across all folds with sample-size weighting
    5. Performs Wilcoxon signed-rank test vs buy-and-hold benchmark

    **Why Use Walk-Forward?**
    - Avoids overfitting to single time period
    - Measures strategy consistency across market regimes
    - Statistical significance confirms skill vs luck
    - Per-fold B&H comparison reveals when strategy adds value

    **Interpreting Results:**
    - `pct_folds_beat_bh > 0.6`: Strategy adds value more often than not
    - `statistically_significant: true`: Outperformance unlikely due to chance
    - `significance_level`: "strong" (p<0.01), "moderate" (p<0.05), "weak" (p<0.10)
    - Large `std_sharpe`: Strategy inconsistent across time periods

    Args:
        request: Walk-forward configuration

    Returns:
        WalkForwardResponse with per-fold and aggregated metrics

    Raises:
        HTTPException 400: Invalid date range or insufficient data
        HTTPException 500: Validation error
    """
    # Validate date range
    if request.end_date < request.start_date:
        raise HTTPException(
            status_code=400,
            detail=f"end_date ({request.end_date}) must be >= start_date ({request.start_date})",
        )

    # Check minimum date range for at least 1 fold
    min_days = (
        request.train_days
        + request.gap_days
        + request.val_days
        + request.gap_days
        + request.test_days
    )
    date_range = (request.end_date - request.start_date).days
    if date_range < min_days:
        raise HTTPException(
            status_code=400,
            detail=f"Date range ({date_range} days) too short for walk-forward. "
            f"Need at least {min_days} days for 1 fold.",
        )

    try:
        # Create engine with requested window configuration
        engine = WalkForwardEngine(
            storage=None,  # Will create internal storage
            train_days=request.train_days,
            val_days=request.val_days,
            test_days=request.test_days,
            gap_days=request.gap_days,
            step_days=request.step_days,
        )

        # Run walk-forward validation
        result = engine.run_walk_forward(
            symbol=request.symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            strategy_type=request.strategy,
            initial_capital=request.initial_capital,
            benchmark_symbol=request.benchmark_symbol,
            min_confirmations=request.min_confirmations,
            stop_loss_atr_multiplier=request.stop_loss_atr_multiplier,
            max_holding_days=request.max_holding_days,
        )

        # Check if any folds succeeded
        if result.num_folds == 0:
            raise HTTPException(
                status_code=400,
                detail=f"Walk-forward validation produced no valid folds for {request.symbol}. "
                "Check that sufficient OHLCV data exists for the date range.",
            )

        # Convert to response
        folds_response = [
            FoldMetricsResponse(
                fold_number=f.fold_number,
                total_return_pct=f.total_return_pct,
                sharpe_ratio=f.sharpe_ratio,
                win_rate=f.win_rate,
                max_drawdown_pct=f.max_drawdown_pct,
                num_trades=f.num_trades,
                profit_factor=f.profit_factor,
                buy_hold_return_pct=f.buy_hold_return_pct,
                excess_return_pct=f.excess_return_pct,
                beats_buy_hold=f.beats_buy_hold,
                alpha=f.alpha,
                beta=f.beta,
                test_start=f.test_start,
                test_end=f.test_end,
            )
            for f in result.folds
        ]

        logger.info(
            f"Walk-forward complete: {request.symbol} | "
            f"{result.num_folds} folds | "
            f"Mean Sharpe: {result.mean_sharpe:.2f} | "
            f"Beat B&H: {result.pct_folds_beat_bh * 100:.0f}% | "
            f"Significant: {result.statistically_significant}"
        )

        return WalkForwardResponse(
            folds=folds_response,
            num_folds=result.num_folds,
            mean_return_pct=result.mean_return_pct,
            std_return_pct=result.std_return_pct,
            mean_sharpe=result.mean_sharpe,
            std_sharpe=result.std_sharpe,
            mean_win_rate=result.mean_win_rate,
            max_drawdown_pct=result.max_drawdown_pct,
            total_trades=result.total_trades,
            mean_excess_vs_bh=result.mean_excess_vs_bh,
            pct_folds_beat_bh=result.pct_folds_beat_bh,
            wilcoxon_p_value=result.wilcoxon_p_value,
            statistically_significant=result.statistically_significant,
            significance_level=result.significance_level,
            symbol=request.symbol,
            strategy=request.strategy,
            benchmark_symbol=request.benchmark_symbol,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Walk-forward validation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Walk-forward validation failed: {e!s}") from e
