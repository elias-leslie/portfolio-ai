"""Strategy performance monitoring tasks.

Celery tasks for evaluating active strategies and archiving underperformers.
Runs daily to track live performance vs expected metrics.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.storage import get_strategy_storage

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.strategy_monitoring_tasks.evaluate_strategy_performance")  # type: ignore[misc]
def evaluate_strategy_performance() -> dict[str, Any]:
    """Evaluate all active strategies and archive underperformers.

    Schedule: Daily at 04:00 UTC (after market data updated)

    Logic:
    1. For each active strategy:
       - Calculate 30-day rolling metrics (Sharpe, win rate, max drawdown)
       - Compare to expected metrics from backtest
       - Archive if performance < 70% of expected for >30 days
    2. Update strategy_performance table with daily metrics
    3. Return summary of strategies evaluated and actions taken

    Returns:
        Summary dict with evaluation results
    """
    logger.info("Starting strategy performance evaluation")

    try:
        strategy_storage = get_strategy_storage()
        with get_connection_manager().connection() as conn:
            # Get all active strategies
            active_strategies = strategy_storage.list_strategies(status="active")

            if not active_strategies:
                logger.info("No active strategies to evaluate")
                return {
                    "status": "completed",
                    "strategies_evaluated": 0,
                    "strategies_archived": 0,
                    "details": [],
                }

            logger.info(f"Evaluating {len(active_strategies)} active strategies")

            results = []
            archived_count = 0

            for strategy in active_strategies:
                try:
                    # Calculate 30-day metrics from paper_trade_transactions
                    metrics = _calculate_rolling_metrics(conn, strategy.id, window_days=30)

                    # Compare to expected metrics
                    expected_sharpe = float(strategy.expected_sharpe or 0.0)
                    actual_sharpe = metrics["sharpe_ratio_30d"]

                    performance_ratio = (
                        actual_sharpe / expected_sharpe if expected_sharpe > 0 else 0
                    )

                    # Determine status
                    days_since_activation = (
                        (datetime.now() - strategy.activation_date).days
                        if strategy.activation_date
                        else 0
                    )

                    # Decision logic: Archive if underperforming for >30 days
                    if performance_ratio < 0.7 and days_since_activation > 30:
                        # Underperforming for >30 days → Archive
                        reason = f"Underperforming: {actual_sharpe:.2f} Sharpe vs {expected_sharpe:.2f} expected ({performance_ratio:.1%})"
                        strategy_storage.archive_strategy(strategy.id, reason)
                        archived_count += 1
                        results.append(
                            f"Archived {strategy.name}: {performance_ratio:.1%} of expected performance"
                        )
                        logger.warning(
                            "Strategy archived due to underperformance",
                            strategy_id=strategy.id,
                            strategy_name=strategy.name,
                            performance_ratio=performance_ratio,
                        )
                    else:
                        # Update live performance metrics
                        strategy_storage.update_live_performance(
                            strategy_id=strategy.id,
                            trades_count=metrics["trades_30d"],
                            win_rate=metrics["win_rate_30d"],
                            sharpe_ratio=actual_sharpe,
                        )

                    # Record daily performance
                    status: Literal["active", "underperforming"] = (
                        "underperforming" if performance_ratio < 0.7 else "active"
                    )
                    strategy_storage.record_daily_performance(
                        strategy_id=strategy.id,
                        date=date.today(),
                        trades_today=metrics["trades_today"],
                        wins_today=metrics["wins_today"],
                        losses_today=metrics["losses_today"],
                        pnl_today=Decimal(str(metrics["pnl_today"])),
                        trades_30d=metrics["trades_30d"],
                        win_rate_30d=metrics["win_rate_30d"],
                        sharpe_ratio_30d=actual_sharpe,
                        max_drawdown_30d=metrics["max_drawdown_30d"],
                        status=status,
                        notes=f"Performance ratio: {performance_ratio:.2f}"
                        if status == "underperforming"
                        else None,
                    )

                    logger.info(
                        "Strategy evaluated",
                        strategy_id=strategy.id,
                        strategy_name=strategy.name,
                        trades_30d=metrics["trades_30d"],
                        sharpe_30d=actual_sharpe,
                        performance_ratio=performance_ratio,
                        status=status,
                    )

                except Exception as e:
                    logger.exception(
                        "Failed to evaluate strategy",
                        strategy_id=strategy.id,
                        strategy_name=strategy.name,
                        error=str(e),
                    )
                    results.append(f"Error evaluating {strategy.name}: {str(e)[:100]}")

            logger.info(
                "Strategy performance evaluation complete",
                strategies_evaluated=len(active_strategies),
                strategies_archived=archived_count,
            )

            return {
                "status": "completed",
                "strategies_evaluated": len(active_strategies),
                "strategies_archived": archived_count,
                "details": results,
            }

    except Exception as e:
        logger.exception("Strategy performance evaluation failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
        }


def _calculate_rolling_metrics(
    conn: Any, strategy_id: str, window_days: int = 30
) -> dict[str, Any]:
    """Calculate rolling performance metrics for a strategy.

    Args:
        conn: Database connection
        strategy_id: Strategy UUID
        window_days: Rolling window size (default 30 days)

    Returns:
        Dict with calculated metrics
    """
    cutoff_date = date.today() - timedelta(days=window_days)

    # Query paper trade transactions for this strategy
    rows = conn.execute_query(
        """
        SELECT
            t.date,
            t.pnl,
            CASE WHEN t.pnl > 0 THEN 1 ELSE 0 END as is_win
        FROM paper_trade_transactions t
        JOIN paper_trades pt ON t.paper_trade_id = pt.id
        WHERE pt.agent_run_id LIKE %s
          AND t.date >= %s
        ORDER BY t.date
        """,
        (f"%{strategy_id}%", cutoff_date),
    )

    if not rows or len(rows) == 0:
        # No trades in window
        return {
            "trades_today": 0,
            "wins_today": 0,
            "losses_today": 0,
            "pnl_today": 0.0,
            "trades_30d": 0,
            "win_rate_30d": 0.0,
            "sharpe_ratio_30d": 0.0,
            "max_drawdown_30d": 0.0,
        }

    # Calculate metrics
    today = date.today()
    today_trades = [r for r in rows if r["date"] == today]

    trades_today = len(today_trades)
    wins_today = sum(1 for r in today_trades if r["pnl"] > 0)
    losses_today = trades_today - wins_today
    pnl_today = sum(float(r["pnl"]) for r in today_trades)

    trades_30d = len(rows)
    wins_30d = sum(1 for r in rows if r["pnl"] > 0)
    win_rate_30d = wins_30d / trades_30d if trades_30d > 0 else 0.0

    # Calculate Sharpe ratio (simplified: mean/std of daily returns)
    daily_returns = [float(r["pnl"]) for r in rows]
    if len(daily_returns) > 1:
        mean_return = sum(daily_returns) / len(daily_returns)
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / len(daily_returns)
        std_dev = variance**0.5
        sharpe_ratio_30d = mean_return / std_dev if std_dev > 0 else 0.0
    else:
        sharpe_ratio_30d = 0.0

    # Calculate max drawdown
    cumulative_pnl = 0.0
    peak_pnl = 0.0
    max_drawdown = 0.0

    for r in rows:
        cumulative_pnl += float(r["pnl"])
        peak_pnl = max(peak_pnl, cumulative_pnl)
        drawdown = (peak_pnl - cumulative_pnl) / peak_pnl if peak_pnl > 0 else 0.0
        max_drawdown = max(max_drawdown, drawdown)

    return {
        "trades_today": trades_today,
        "wins_today": wins_today,
        "losses_today": losses_today,
        "pnl_today": pnl_today,
        "trades_30d": trades_30d,
        "win_rate_30d": win_rate_30d,
        "sharpe_ratio_30d": sharpe_ratio_30d,
        "max_drawdown_30d": max_drawdown,
    }


@celery_app.task(name="app.tasks.strategy_monitoring_tasks.weekly_strategy_generation")  # type: ignore[misc]
def weekly_strategy_generation() -> dict[str, Any]:
    """Generate new strategies for top watchlist symbols.

    Schedule: Weekly on Sunday at 05:00 UTC

    Logic:
    1. Get top 20 symbols from watchlist (by priority score)
    2. For each symbol without active strategy:
       - Trigger strategy_research_workflow
    3. Return summary of generation attempts

    Returns:
        Summary dict with generation results
    """
    logger.info("Starting weekly strategy generation")

    # Import here to avoid circular dependency
    from app.agents.workflows.strategy_research_workflow import strategy_research_workflow

    try:
        with get_connection_manager().connection() as conn:
            strategy_storage = get_strategy_storage()

            # Get top 20 watchlist symbols
            top_symbols = conn.execute(
                """
                SELECT symbol
                FROM watchlist_items
                ORDER BY priority DESC
                LIMIT 20
                """
            ).fetchall()

            if not top_symbols:
                logger.info("No watchlist symbols found")
                return {
                    "status": "completed",
                    "symbols_evaluated": 0,
                    "strategies_generated": 0,
                    "details": [],
                }

            logger.info(f"Evaluating {len(top_symbols)} top watchlist symbols")

            results = []
            generated_count = 0

            for row in top_symbols:
                # Convert tuple to dict-like access
                symbol_value = row[0] if isinstance(row, tuple) else row["symbol"]
                symbol = str(symbol_value)

                # Check if active strategy already exists
                existing = strategy_storage.get_active_strategy(symbol)
                if existing:
                    logger.info(f"Skipping {symbol}: active strategy exists ({existing.name})")
                    continue

                # Generate new strategy
                try:
                    logger.info(f"Generating strategy for {symbol}")
                    result = asyncio.run(
                        strategy_research_workflow(symbol=symbol, force_regenerate=False)
                    )

                    if result["status"] == "completed":
                        generated_count += 1
                        results.append(
                            f"Generated strategy for {symbol}: {result.get('strategy_id', 'unknown')}"
                        )
                        logger.info(
                            "Strategy generated successfully",
                            symbol=symbol,
                            strategy_id=result.get("strategy_id"),
                        )
                    else:
                        results.append(
                            f"Skipped {symbol}: {result.get('message', 'unknown reason')}"
                        )
                        logger.info(
                            "Strategy generation skipped/blocked",
                            symbol=symbol,
                            status=result["status"],
                            message=result.get("message"),
                        )

                except Exception as e:
                    logger.exception("Strategy generation failed", symbol=symbol, error=str(e))
                    results.append(f"Error for {symbol}: {str(e)[:100]}")

            logger.info(
                "Weekly strategy generation complete",
                symbols_evaluated=len(top_symbols),
                strategies_generated=generated_count,
            )

            return {
                "status": "completed",
                "symbols_evaluated": len(top_symbols),
                "strategies_generated": generated_count,
                "details": results,
            }

    except Exception as e:
        logger.exception("Weekly strategy generation failed", error=str(e))
        return {
            "status": "failed",
            "error": str(e),
        }
