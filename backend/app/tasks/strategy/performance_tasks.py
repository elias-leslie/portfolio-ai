"""Strategy performance monitoring tasks.

Tasks for evaluating active strategies and archiving underperformers.
Runs daily to track live performance vs expected metrics.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from app.backtest.metrics import calculate_simple_max_drawdown, calculate_simple_sharpe
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.storage import (
    StrategyStorage,
    get_strategy_storage,
)
from app.tasks.types import (
    StrategyMonitoringResultDict,
    build_strategy_failure,
    build_strategy_success,
)

logger = get_logger(__name__)

# Strategy performance thresholds
PERFORMANCE_RATIO_THRESHOLD = 0.7  # Archive if performance < 70% of expected
ERROR_MESSAGE_TRUNCATE = 100  # Truncate error messages to prevent log bloat

# Strategy thresholds
MIN_SHARPE_FOR_PROMOTION = 1.0  # Minimum expected Sharpe to auto-promote from testing


def _should_archive_strategy(performance_ratio: float, days_since_activation: int) -> bool:
    """Determine if a strategy should be archived based on performance.

    Args:
        performance_ratio: Actual/expected performance ratio
        days_since_activation: Days since strategy was activated

    Returns:
        True if strategy should be archived
    """
    return (
        performance_ratio < PERFORMANCE_RATIO_THRESHOLD
        and days_since_activation > StrategyStorage.PERFORMANCE_WINDOW_DAYS
    )


def _compute_performance_ratio(
    strategy: Any,
    metrics: dict[str, Any],
) -> tuple[float, float, float]:
    """Compute performance metrics for strategy evaluation.

    Args:
        strategy: Strategy object
        metrics: Calculated rolling metrics

    Returns:
        Tuple of (expected_sharpe, actual_sharpe, performance_ratio)
    """
    expected_sharpe = float(strategy.expected_sharpe or 0.0)
    actual_sharpe = metrics["sharpe_ratio_30d"]
    performance_ratio = actual_sharpe / expected_sharpe if expected_sharpe > 0 else 0
    return expected_sharpe, actual_sharpe, performance_ratio


def _determine_archive_decision(
    strategy: Any,
    metrics: dict[str, Any],
    strategy_storage: Any,
) -> tuple[bool, str | None]:
    """Determine if strategy should be archived and perform archival if needed.

    Args:
        strategy: Strategy object to evaluate
        metrics: Calculated rolling metrics
        strategy_storage: Strategy storage instance

    Returns:
        Tuple of (was_archived, result_message_or_none)
    """
    expected_sharpe, actual_sharpe, performance_ratio = _compute_performance_ratio(
        strategy, metrics
    )

    days_since_activation = (
        (datetime.now(UTC) - strategy.activation_date).days if strategy.activation_date else 0
    )

    if not _should_archive_strategy(performance_ratio, days_since_activation):
        return False, None

    reason = (
        f"Underperforming: {actual_sharpe:.2f} Sharpe vs "
        f"{expected_sharpe:.2f} expected ({performance_ratio:.1%})"
    )
    strategy_storage.archive_strategy(strategy.id, reason)
    logger.warning(
        "Strategy archived due to underperformance",
        strategy_id=strategy.id,
        strategy_name=strategy.name,
        performance_ratio=performance_ratio,
    )
    return True, f"Archived {strategy.name}: {performance_ratio:.1%} of expected performance"


def _update_live_metrics_if_active(
    strategy: Any,
    metrics: dict[str, Any],
    strategy_storage: Any,
    archived: bool,
) -> None:
    """Update live performance metrics if strategy is not archived.

    Args:
        strategy: Strategy object
        metrics: Calculated rolling metrics
        strategy_storage: Strategy storage instance
        archived: Whether strategy was archived
    """
    if archived:
        return

    strategy_storage.update_live_performance(
        strategy_id=strategy.id,
        trades_count=metrics["trades_30d"],
        win_rate=metrics["win_rate_30d"],
        sharpe_ratio=metrics["sharpe_ratio_30d"],
    )


def _record_and_emit_performance(
    strategy: Any,
    metrics: dict[str, Any],
    strategy_storage: Any,
) -> None:
    """Record daily performance and emit event for downstream triggers.

    Args:
        strategy: Strategy object
        metrics: Calculated rolling metrics
        strategy_storage: Strategy storage instance
    """
    _, actual_sharpe, performance_ratio = _compute_performance_ratio(strategy, metrics)

    status: Literal["active", "underperforming"] = (
        "underperforming" if performance_ratio < PERFORMANCE_RATIO_THRESHOLD else "active"
    )

    strategy_storage.record_daily_performance(
        strategy_id=strategy.id,
        date=datetime.now(UTC).date(),
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

    from app.tasks.triggers import emit_event

    emit_event(
        "strategy_performance_updated",
        {
            "strategy_id": strategy.id,
            "symbol": strategy.symbol,
            "sharpe_30d": actual_sharpe,
            "performance_ratio": performance_ratio,
            "status": status,
        },
    )


def _calculate_today_metrics(trades: list[dict[str, Any]], today: date) -> dict[str, Any]:
    """Calculate metrics for trades made today.

    Args:
        trades: List of trade dicts with 'date' and 'pnl' keys
        today: Today's date

    Returns:
        Dict with trades_today, wins_today, losses_today, pnl_today
    """
    today_trades = [t for t in trades if t["date"] == today]
    trades_today = len(today_trades)
    wins_today = sum(1 for t in today_trades if t["pnl"] > 0)
    losses_today = trades_today - wins_today
    pnl_today = sum(t["pnl"] for t in today_trades)
    return {
        "trades_today": trades_today,
        "wins_today": wins_today,
        "losses_today": losses_today,
        "pnl_today": pnl_today,
    }


def _calculate_rolling_metrics(
    strategy_storage: Any,
    strategy_id: str,
    window_days: int = StrategyStorage.PERFORMANCE_WINDOW_DAYS,
) -> dict[str, Any]:
    """Calculate rolling performance metrics for a strategy.

    Args:
        strategy_storage: Strategy storage instance
        strategy_id: Strategy UUID
        window_days: Rolling window size (default: StrategyStorage.PERFORMANCE_WINDOW_DAYS)

    Returns:
        Dict with calculated metrics
    """
    cutoff_date = datetime.now(UTC).date() - timedelta(days=window_days)

    try:
        rows = strategy_storage.get_strategy_trades(strategy_id, cutoff_date)
    except Exception as e:
        logger.warning("Could not query trades for strategy", strategy_id=strategy_id, error=str(e))
        rows = []

    # Default return for no trades
    empty_metrics = {
        "trades_today": 0,
        "wins_today": 0,
        "losses_today": 0,
        "pnl_today": 0.0,
        "trades_30d": 0,
        "win_rate_30d": 0.0,
        "sharpe_ratio_30d": 0.0,
        "max_drawdown_30d": 0.0,
    }

    if not rows:
        # No trades in window
        return empty_metrics

    # Convert rows to list of dicts for easier access
    # Rows are tuples: (trade_date, pnl)
    trades = []
    for row in rows:
        if isinstance(row, tuple):
            trade_date, pnl = row[0], row[1]
        else:
            trade_date = row.get("trade_date", row.get("date"))
            pnl = row.get("pnl", 0.0)

        if pnl is None:
            continue

        trades.append({"date": trade_date, "pnl": float(pnl)})

    if not trades:
        return empty_metrics

    # Calculate metrics using helpers
    today = datetime.now(UTC).date()
    today_metrics = _calculate_today_metrics(trades, today)

    # 30-day metrics
    trades_30d = len(trades)
    wins_30d = sum(1 for t in trades if t["pnl"] > 0)
    win_rate_30d = wins_30d / trades_30d if trades_30d > 0 else 0.0

    # Sharpe ratio and max drawdown
    daily_returns = [t["pnl"] for t in trades]
    sharpe_ratio_30d = calculate_simple_sharpe(daily_returns)
    max_drawdown = calculate_simple_max_drawdown(daily_returns)

    return {
        **today_metrics,
        "trades_30d": trades_30d,
        "win_rate_30d": win_rate_30d,
        "sharpe_ratio_30d": sharpe_ratio_30d,
        "max_drawdown_30d": max_drawdown,
    }


def _evaluate_single_strategy(
    strategy: Any,
    conn: Any,
    strategy_storage: Any,
) -> tuple[str | None, bool]:
    """Evaluate a single strategy and update its metrics.

    Orchestrates the evaluation workflow:
    1. Calculate rolling metrics from paper_trade_transactions
    2. Determine if strategy should be archived
    3. Update live metrics if still active
    4. Record daily performance and emit events

    Args:
        strategy: Strategy object to evaluate
        conn: Database connection
        strategy_storage: Strategy storage instance

    Returns:
        Tuple of (result_message_or_none, was_archived)
    """
    # Calculate rolling metrics from paper_trade_transactions
    metrics = _calculate_rolling_metrics(strategy_storage, strategy.id)

    # Determine if strategy should be archived
    archived, result_msg = _determine_archive_decision(strategy, metrics, strategy_storage)

    # Update live metrics if strategy wasn't archived
    _update_live_metrics_if_active(strategy, metrics, strategy_storage, archived)

    # Record daily performance and emit event
    _record_and_emit_performance(strategy, metrics, strategy_storage)

    return result_msg, archived


def evaluate_strategy_performance() -> StrategyMonitoringResultDict:
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
                return build_strategy_success(details=[])

            logger.info("Evaluating active strategies", count=len(active_strategies))

            results: list[str] = []
            archived_count = 0

            for strategy in active_strategies:
                try:
                    result_msg, archived = _evaluate_single_strategy(
                        strategy, conn, strategy_storage
                    )
                    if result_msg:
                        results.append(result_msg)
                    if archived:
                        archived_count += 1

                except Exception as e:
                    logger.exception(
                        "Failed to evaluate strategy",
                        strategy_id=strategy.id,
                        strategy_name=strategy.name,
                        error=str(e),
                    )
                    results.append(
                        f"Error evaluating {strategy.name}: {str(e)[:ERROR_MESSAGE_TRUNCATE]}"
                    )

            logger.info(
                "Strategy performance evaluation complete",
                strategies_evaluated=len(active_strategies),
                strategies_archived=archived_count,
            )

            return build_strategy_success(
                strategies_evaluated=len(active_strategies),
                strategies_archived=archived_count,
                details=results,
            )

    except Exception as e:
        logger.exception("Strategy performance evaluation failed", error=str(e))
        return build_strategy_failure(e)


def auto_promote_strategies(
    min_days: int = 3,
    min_sharpe: float = MIN_SHARPE_FOR_PROMOTION,
) -> StrategyMonitoringResultDict:
    """Auto-promote testing strategies that meet validation criteria.

    Schedule: Daily at 04:15 UTC (after performance evaluation)

    Criteria for promotion:
    1. Strategy in 'testing' status for >= min_days
    2. Expected Sharpe ratio >= min_sharpe
    3. No blocking issues (negative Sharpe, etc.)

    Args:
        min_days: Minimum days in testing before promotion (default 3)
        min_sharpe: Minimum expected Sharpe to promote (default 1.0)

    Returns:
        Summary dict with promotion results
    """
    logger.info(
        "Starting auto-promotion of validated strategies", min_days=min_days, min_sharpe=min_sharpe
    )

    try:
        strategy_storage = get_strategy_storage()
        testing_strategies = strategy_storage.list_strategies(status="testing")

        if not testing_strategies:
            logger.info("No testing strategies to evaluate")
            return build_strategy_success(details=[])

        logger.info("Evaluating testing strategies for promotion", count=len(testing_strategies))

        results: list[str] = []
        promoted_count = 0

        for strategy in testing_strategies:
            try:
                # Check age (handle timezone-aware datetimes)
                now = datetime.now(UTC)
                created = strategy.created_at
                if created and created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                days_since_creation = (now - created).days if created else 0

                if days_since_creation < min_days:
                    logger.debug(
                        "Skipping strategy - insufficient age",
                        strategy_name=strategy.name,
                        days_since_creation=days_since_creation,
                        min_days=min_days,
                    )
                    continue

                # Check expected Sharpe
                expected_sharpe = float(strategy.expected_sharpe or 0.0)

                if expected_sharpe < min_sharpe:
                    logger.debug(
                        "Skipping strategy - Sharpe below minimum",
                        strategy_name=strategy.name,
                        expected_sharpe=expected_sharpe,
                        min_sharpe=min_sharpe,
                    )
                    continue

                # Check for blocking issues (negative Sharpe = likely bad strategy)
                if expected_sharpe < 0:
                    logger.debug(
                        "Skipping strategy - negative expected Sharpe",
                        strategy_name=strategy.name,
                    )
                    continue

                # All criteria met - promote!
                strategy_storage.activate_strategy(strategy.id)
                promoted_count += 1
                results.append(
                    f"Promoted {strategy.name} (Sharpe={expected_sharpe:.2f}, age={days_since_creation}d)"
                )

                logger.info(
                    "Strategy auto-promoted",
                    strategy_id=strategy.id,
                    strategy_name=strategy.name,
                    expected_sharpe=expected_sharpe,
                    days_since_creation=days_since_creation,
                )

            except Exception as e:
                logger.exception(
                    "Failed to evaluate strategy for promotion",
                    strategy_id=strategy.id,
                    error=str(e),
                )

        logger.info(
            "Auto-promotion complete",
            strategies_evaluated=len(testing_strategies),
            strategies_promoted=promoted_count,
        )

        return build_strategy_success(
            strategies_evaluated=len(testing_strategies),
            strategies_promoted=promoted_count,
            details=results,
        )

    except Exception as e:
        logger.exception("Auto-promotion failed", error=str(e))
        return build_strategy_failure(e)
