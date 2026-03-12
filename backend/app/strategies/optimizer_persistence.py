"""Backtest persistence for strategy optimization.

This module handles saving backtest results to the database.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.backtest.replay import replay_backtest
from app.backtest.storage import (
    create_backtest_run,
    save_backtest_trade,
    save_equity_snapshot,
    update_backtest_result,
)
from app.backtest.strategies import SignalStrategy
from app.logging_config import get_logger
from app.storage import PortfolioStorage

from .models import ResearchInsights, StrategyParameters
from .optimizer_metrics import calculate_metrics_from_state

logger = get_logger(__name__)


def persist_best_backtest(
    storage: PortfolioStorage,
    symbol: str,
    strategy_name: str,
    params: StrategyParameters,
    metrics: dict[str, float],
    fundamental_data: dict[str, object],
    strategy_id: str | None = None,
) -> str:
    """Persist the best backtest run to database.

    Runs a final backtest with the optimized parameters and stores
    the results in backtest_runs, backtest_trades, and backtest_equity.

    Args:
        storage: Portfolio storage instance
        symbol: Stock symbol
        strategy_name: Strategy name
        params: Optimized parameters
        metrics: Aggregated metrics from optimization
        fundamental_data: Fundamental data for signal classifier
        strategy_id: Optional strategy ID to link

    Returns:
        Backtest run ID
    """
    # Run a final backtest with best params over last 2 years (730 calendar days)
    # This provides meaningful validation across multiple market cycles
    end_date = date.today()
    start_date = end_date - timedelta(days=730)

    strategy = SignalStrategy(
        min_signal_strength=params.min_confirmations,
        max_holding_days=params.max_holding_days,
        stop_loss_atr_multiplier=params.stop_loss_atr_multiplier,
        fundamental_data=fundamental_data,
    )

    # Create the backtest run record FIRST
    run_id = create_backtest_run(
        storage=storage,
        strategy_name=strategy_name,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        initial_capital=Decimal("100000.00"),
    )

    try:
        # Run backtest
        state = replay_backtest(
            storage=storage,
            run_id=run_id,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            strategy=strategy,
            initial_capital=Decimal("100000.00"),
        )

        # Persist trades
        for trade in state.trades:
            save_backtest_trade(storage.connection_mgr, trade)

        # Persist equity curve
        for snapshot in state.equity_curve:
            save_equity_snapshot(storage.connection_mgr, snapshot)

        # Calculate final metrics
        final_metrics = calculate_metrics_from_state(state)

        # Update run with results
        final_equity = state.equity_curve[-1].equity if state.equity_curve else Decimal("100000.00")
        update_backtest_result(
            storage=storage.connection_mgr,
            run_id=run_id,
            final_equity=final_equity,
            total_return_pct=Decimal(str(final_metrics.total_return * 100)),
            sharpe_ratio=Decimal(str(final_metrics.sharpe_ratio)),
            max_drawdown_pct=Decimal(str(final_metrics.max_drawdown)),
            win_rate=Decimal(str(final_metrics.win_rate * 100)),
            num_trades=final_metrics.num_trades,
            profit_factor=Decimal(str(final_metrics.profit_factor)),
        )

        # Link to strategy if provided
        if strategy_id:
            with storage.connection() as conn:
                conn.execute(
                    "UPDATE backtest_runs SET strategy_definition_id = %s WHERE id = %s",
                    (strategy_id, run_id),
                )
                conn.commit()

        logger.info(
            f"Persisted backtest run {run_id}: {len(state.trades)} trades, "
            f"Sharpe={final_metrics.sharpe_ratio:.2f}"
        )

        return run_id

    except Exception as e:
        logger.error("backtest_persist_failed", run_id=run_id, error=str(e), exc_info=True)
        # Mark as failed
        with storage.connection() as conn:
            conn.execute(
                "UPDATE backtest_runs SET status = 'failed', error_message = %s WHERE id = %s",
                (str(e), run_id),
            )
            conn.commit()
        raise


def extract_fundamental_data(research: ResearchInsights | None) -> dict[str, object]:
    """Extract fundamental data from ResearchInsights for signal classifier.

    Args:
        research: Research data from aggregator (ResearchInsights or None)

    Returns:
        Dict with fundamental fields for classify_signal
    """
    if not research:
        return {}

    return {
        "company_health": research.company_health,
        "news_sentiment": research.news_sentiment_score,
        # Map profitability_tier to numeric profit_margin estimate
        "profit_margin": {
            "excellent": 0.25,
            "good": 0.15,
            "weak": 0.05,
        }.get(research.profitability_tier, 0.10),
        # Map growth_tier to numeric revenue_growth estimate
        "revenue_growth": {
            "accelerating": 0.20,
            "stable": 0.10,
            "slowing": 0.02,
        }.get(research.growth_tier, 0.05),
        # Map debt_tier to numeric debt_to_equity
        "debt_to_equity": {
            "low": 0.3,
            "moderate": 0.6,
            "high": 1.2,
        }.get(research.debt_tier, 0.5),
        "recommendation_mean": research.analyst_consensus,
        # Estimate analyst_buy_pct from consensus (1=strong buy, 5=sell)
        "analyst_buy_pct": max(0.0, min(1.0, (5.0 - research.analyst_consensus) / 4.0)),
    }
