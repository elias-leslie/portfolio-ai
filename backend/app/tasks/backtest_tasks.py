"""
Celery tasks for backtesting.

Async task execution for running backtests without blocking HTTP requests.

Tasks:
- run_backtest_task: Execute backtest replay and store results
"""

import logging
from datetime import date
from decimal import Decimal
from typing import Any

from app.backtest import metrics, replay, storage, strategies
from app.backtest.additional_strategies import (
    MeanReversionStrategy,
    MomentumStrategy,
    TrendFollowingStrategy,
)
from app.backtest.benchmark import BenchmarkComparisonEngine
from app.backtest.enhanced_strategy import EnhancedSignalStrategy
from app.backtest.replay import InsufficientDataError
from app.celery_app import celery_app
from app.storage.facade import get_storage

logger = logging.getLogger(__name__)

# How many days of data to fetch when backfilling (covers 5 years of trading days)
# 252 trading days/year * 5 years ≈ 1260 trading days, using 1300 to be safe
BACKFILL_DAYS = 1300


def _initialize_strategy(
    strategy_name: str,
    stop_loss_atr_multiplier: float = 2.0,
    max_holding_days: int = 30,
    target_profit_pct: float = 15.0,
    min_confirmations: int = 5,
) -> Any:
    """Initialize backtest strategy from name and parameters.

    Args:
        strategy_name: Strategy identifier (signal_classifier, enhanced, momentum, etc.)
        stop_loss_atr_multiplier: Stop loss in ATR multiples
        max_holding_days: Maximum holding period
        target_profit_pct: Target profit percentage
        min_confirmations: Minimum confirmations for entry

    Returns:
        Initialized strategy instance

    Raises:
        ValueError: If strategy_name is unknown
    """
    storage = get_storage()

    if strategy_name == "signal_classifier":
        return strategies.SignalStrategy(
            min_signal_strength=min_confirmations + 2,  # Map to 7 default
            max_holding_days=max_holding_days,
            stop_loss_atr_multiplier=Decimal(str(stop_loss_atr_multiplier)),
        )
    if strategy_name == "enhanced":
        return EnhancedSignalStrategy(
            min_confirmations=min_confirmations,
            max_holding_days=max_holding_days,
            stop_loss_atr_multiplier=Decimal(str(stop_loss_atr_multiplier)),
            target_profit_pct=Decimal(str(target_profit_pct)),
        )
    if strategy_name == "momentum":
        return MomentumStrategy(
            storage=storage,
            max_holding_days=max_holding_days,
            target_profit_pct=Decimal(str(target_profit_pct)),
            stop_loss_pct=Decimal(str(stop_loss_atr_multiplier * 3)),  # Convert ATR to %
        )
    if strategy_name == "mean_reversion":
        return MeanReversionStrategy(
            max_holding_days=min(max_holding_days, 15),  # Mean reversion = shorter holds
            target_profit_pct=Decimal(str(min(target_profit_pct, 8))),  # Lower targets
            stop_loss_pct=Decimal(str(min(stop_loss_atr_multiplier * 2, 5))),
        )
    if strategy_name == "trend_following":
        return TrendFollowingStrategy(
            max_holding_days=max(max_holding_days, 60),  # Trend = longer holds
            trailing_stop_atr_multiplier=Decimal(str(stop_loss_atr_multiplier)),
        )
    raise ValueError(f"Unknown strategy: {strategy_name}")


def _calculate_performance_metrics(
    state: replay.BacktestState, initial_capital: Decimal
) -> dict[str, Any]:
    """Calculate all performance metrics from backtest state.

    Args:
        state: BacktestState object containing trades and equity curve
        initial_capital: Starting capital amount

    Returns:
        Dict containing metrics:
        - final_equity: Final account equity
        - total_return_pct: Total return percentage
        - sharpe_ratio: Sharpe ratio
        - max_drawdown_pct: Maximum drawdown percentage
        - win_rate: Win rate (0.0-100.0)
        - profit_factor: Profit factor
        - num_trades: Number of trades executed
    """
    final_equity = state.equity_curve[-1].equity if state.equity_curve else initial_capital
    return {
        "final_equity": final_equity,
        "total_return_pct": metrics.calculate_total_return(initial_capital, final_equity),
        "sharpe_ratio": metrics.calculate_sharpe_ratio(state.equity_curve),
        "max_drawdown_pct": metrics.calculate_max_drawdown(state.equity_curve),
        "win_rate": metrics.calculate_win_rate(state.trades),
        "profit_factor": metrics.calculate_profit_factor(state.trades),
        "num_trades": len(state.trades),
    }


def _save_backtest_results(
    storage_mgr: Any,
    state: replay.BacktestState,
    metrics_dict: dict[str, Any],
    run_id: str,
    benchmark_metrics: dict[str, Any] | None = None,
) -> None:
    """Save trades, equity curve, and update backtest_run with final metrics.

    Args:
        storage_mgr: Storage connection manager
        state: BacktestState object with trades and equity curve
        metrics_dict: Performance metrics dict from _calculate_performance_metrics
        run_id: Backtest run ID
        benchmark_metrics: Optional benchmark comparison metrics from BenchmarkComparisonEngine
    """
    # Save trades to database
    for trade in state.trades:
        storage.save_backtest_trade(storage_mgr, trade)

    # Save equity curve to database
    for snapshot in state.equity_curve:
        storage.save_equity_snapshot(storage_mgr, snapshot)

    # Update backtest_run with final results (including benchmark if available)
    storage.update_backtest_result(
        storage=storage_mgr,
        run_id=run_id,
        final_equity=metrics_dict["final_equity"],
        total_return_pct=metrics_dict["total_return_pct"],
        sharpe_ratio=metrics_dict["sharpe_ratio"],
        max_drawdown_pct=metrics_dict["max_drawdown_pct"],
        win_rate=metrics_dict["win_rate"],
        num_trades=metrics_dict["num_trades"],
        profit_factor=metrics_dict["profit_factor"],
        # Benchmark fields (Section 0.1)
        buy_hold_return=benchmark_metrics.get("buy_hold_return") if benchmark_metrics else None,
        excess_return=benchmark_metrics.get("excess_return") if benchmark_metrics else None,
        beats_buy_hold=benchmark_metrics.get("beats_buy_hold") if benchmark_metrics else None,
        alpha=benchmark_metrics.get("alpha") if benchmark_metrics else None,
        information_ratio=benchmark_metrics.get("information_ratio") if benchmark_metrics else None,
        beta=benchmark_metrics.get("beta") if benchmark_metrics else None,
        benchmark_symbol=benchmark_metrics.get("benchmark_symbol", "SPY") if benchmark_metrics else "SPY",
    )


@celery_app.task(  # type: ignore[misc]
    bind=True,
    max_retries=2,  # Retry after data backfill
    default_retry_delay=120,  # Wait 2 minutes for data to be fetched
    time_limit=600,  # 10 minute timeout (prevent infinite loops)
)
def run_backtest_task(  # type: ignore[no-untyped-def]
    self,
    run_id: str,
    symbol: str,
    start_date: str,  # ISO format (YYYY-MM-DD)
    end_date: str,  # ISO format (YYYY-MM-DD)
    initial_capital: float,
    strategy_name: str,
    stop_loss_atr_multiplier: float = 2.0,
    max_holding_days: int = 30,
    target_profit_pct: float = 15.0,
    min_confirmations: int = 5,
    position_sizing_method: str = "fixed_dollars",
    position_size_value: float = 10000.00,
) -> dict[str, str | int | float]:
    """Execute backtest and store results.

    This task:
    1. Checks if sufficient historical data exists
    2. If not, triggers data backfill and retries after delay
    3. Runs the backtest replay loop
    4. Calculates performance metrics
    5. Saves trades and equity curve to database
    6. Updates backtest_run with final results

    Args:
        run_id: Backtest run ID (UUID)
        symbol: Stock symbol
        start_date: Backtest start date (ISO format)
        end_date: Backtest end date (ISO format)
        initial_capital: Starting capital
        strategy_name: Strategy identifier (signal_classifier, enhanced, momentum, etc.)
        stop_loss_atr_multiplier: Stop loss in ATR multiples (1.0-5.0)
        max_holding_days: Maximum holding period
        target_profit_pct: Target profit percentage
        min_confirmations: Minimum confirmations for entry (3-8)
        position_sizing_method: "fixed_dollars" or "fixed_shares"
        position_size_value: Position size (dollars or shares)

    Returns:
        Dict with final metrics

    Raises:
        Exception: If backtest fails (saved to error_message field)
    """
    logger.info(
        f"Starting backtest task: {run_id} | {symbol} | {start_date} to {end_date} | "
        f"Strategy: {strategy_name} | Stop: {stop_loss_atr_multiplier}x ATR | "
        f"Max Hold: {max_holding_days}d | Target: {target_profit_pct}% | Retry: {self.request.retries}"
    )

    storage_mgr = get_storage()

    try:
        # Parse dates
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)

        # Initialize strategy with all parameters
        strategy = _initialize_strategy(
            strategy_name=strategy_name,
            stop_loss_atr_multiplier=stop_loss_atr_multiplier,
            max_holding_days=max_holding_days,
            target_profit_pct=target_profit_pct,
            min_confirmations=min_confirmations,
        )

        # Run backtest replay
        state = replay.replay_backtest(
            storage=storage_mgr,
            run_id=run_id,
            symbol=symbol,
            start_date=start,
            end_date=end,
            initial_capital=Decimal(str(initial_capital)),
            strategy=strategy,
            sizing_method=position_sizing_method,
            size_value=Decimal(str(position_size_value)),
        )

        # Calculate metrics
        metrics_dict = _calculate_performance_metrics(state, Decimal(str(initial_capital)))

        # Calculate benchmark comparison (Section 0.1)
        benchmark_metrics: dict[str, Any] | None = None
        if state.equity_curve:
            try:
                benchmark_engine = BenchmarkComparisonEngine(storage_mgr)
                comparison = benchmark_engine.compare_to_benchmark(
                    strategy_equity_curve=state.equity_curve,
                    benchmark_symbol="SPY",
                    start_date=start,
                    end_date=end,
                )
                benchmark_metrics = {
                    "buy_hold_return": comparison.metrics.benchmark_return_pct,
                    "excess_return": comparison.metrics.outperformance_pct,
                    "beats_buy_hold": comparison.metrics.outperformance_pct > 0,
                    "alpha": comparison.metrics.alpha,
                    "information_ratio": comparison.metrics.information_ratio,
                    "beta": comparison.metrics.beta,
                    "benchmark_symbol": "SPY",
                }
                logger.info(
                    f"Benchmark comparison: B&H={comparison.metrics.benchmark_return_pct:.2f}% | "
                    f"Excess={comparison.metrics.outperformance_pct:.2f}% | "
                    f"Alpha={comparison.metrics.alpha:.4f}" if comparison.metrics.alpha else ""
                )
            except Exception as bench_err:
                logger.warning(f"Benchmark comparison failed (non-fatal): {bench_err}")
                benchmark_metrics = None

        # Save results
        _save_backtest_results(storage_mgr, state, metrics_dict, run_id, benchmark_metrics)

        logger.info(
            f"Backtest complete: {run_id} | Return: {metrics_dict['total_return_pct']:.2f}% | "
            f"Sharpe: {metrics_dict['sharpe_ratio']:.2f} | Trades: {metrics_dict['num_trades']} | "
            f"Win Rate: {metrics_dict['win_rate']:.1f}%"
        )

        # Build response with benchmark fields
        result: dict[str, str | int | float] = {
            "run_id": run_id,
            "status": "completed",
            "final_equity": float(metrics_dict["final_equity"]),
            "total_return_pct": float(metrics_dict["total_return_pct"]),
            "sharpe_ratio": float(metrics_dict["sharpe_ratio"]),
            "max_drawdown_pct": float(metrics_dict["max_drawdown_pct"]),
            "win_rate": float(metrics_dict["win_rate"]),
            "num_trades": metrics_dict["num_trades"],
            "profit_factor": float(metrics_dict["profit_factor"]),
        }
        if benchmark_metrics:
            result["buy_hold_return"] = float(benchmark_metrics["buy_hold_return"])
            result["excess_return"] = float(benchmark_metrics["excess_return"])
            result["beats_buy_hold"] = benchmark_metrics["beats_buy_hold"]
        return result

    except InsufficientDataError as e:
        logger.warning(
            f"Backtest needs more data: {run_id} | {symbol} | "
            f"Available: {e.available_start} to {e.available_end} | "
            f"Requested: {e.requested_start} to {e.requested_end}"
        )

        # Trigger historical data backfill
        from app.tasks.ingestion.price_ingestion import (  # noqa: PLC0415
            ingest_historical_ohlcv,
        )

        logger.info(f"Triggering historical data backfill for {symbol} ({BACKFILL_DAYS} days)")
        ingest_historical_ohlcv.delay([symbol], days=BACKFILL_DAYS)

        # Update status to show we're waiting for data
        storage.update_backtest_status(
            storage=storage_mgr,
            run_id=run_id,
            status="running",
            error_message=f"Fetching historical data... (retry {self.request.retries + 1}/2)",
        )

        # Retry after delay to allow data to be fetched
        raise self.retry(exc=e, countdown=120) from e  # Retry in 2 minutes

    except Exception as e:
        logger.error(f"Backtest failed: {run_id} | Error: {e}", exc_info=True)

        # Update status to failed with error message
        storage.update_backtest_status(
            storage=storage_mgr,
            run_id=run_id,
            status="failed",
            error_message=str(e),
        )

        # Re-raise so Celery marks task as failed
        raise
