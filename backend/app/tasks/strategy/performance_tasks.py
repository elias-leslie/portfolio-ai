"""Strategy performance monitoring tasks.

Tasks for evaluating active strategies and archiving underperformers.
Runs daily to track live performance vs expected metrics.
"""

from __future__ import annotations

from typing import Any

from app.constants import ERROR_MESSAGE_TRUNCATE
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.storage import get_strategy_storage
from app.tasks.strategy._performance_helpers import (
    _days_since,
    _evaluate_single_strategy,
    _promotion_skip_reason,
)
from app.tasks.types import (
    StrategyMonitoringResultDict,
    build_strategy_failure,
    build_strategy_success,
)

logger = get_logger(__name__)

# Strategy performance thresholds (re-exported for external callers)
PERFORMANCE_RATIO_THRESHOLD = 0.7
MIN_SHARPE_FOR_PROMOTION = 1.0


def _process_active_strategy(
    strategy: Any,
    conn: Any,
    strategy_storage: Any,
    results: list[str],
) -> bool:
    """Process one active strategy; return True if it was archived."""
    try:
        result_msg, archived = _evaluate_single_strategy(strategy, conn, strategy_storage)
        if result_msg:
            results.append(result_msg)
        return archived
    except Exception as e:
        logger.exception(
            "Failed to evaluate strategy",
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            error=str(e),
        )
        results.append(f"Error evaluating {strategy.name}: {str(e)[:ERROR_MESSAGE_TRUNCATE]}")
        return False


def _evaluate_active_strategies(
    strategy_storage: Any, conn: Any
) -> tuple[int, int, list[str]]:
    """Evaluate all active strategies; return (total, archived_count, messages)."""
    active_strategies = strategy_storage.list_strategies(status="active")
    if not active_strategies:
        logger.info("No active strategies to evaluate")
        return 0, 0, []

    logger.info("Evaluating active strategies", count=len(active_strategies))
    results: list[str] = []
    archived_count = sum(
        1
        for s in active_strategies
        if _process_active_strategy(s, conn, strategy_storage, results)
    )
    return len(active_strategies), archived_count, results


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
            total, archived_count, results = _evaluate_active_strategies(
                strategy_storage, conn
            )

        logger.info(
            "Strategy performance evaluation complete",
            strategies_evaluated=total,
            strategies_archived=archived_count,
        )
        return build_strategy_success(
            strategies_evaluated=total,
            strategies_archived=archived_count,
            details=results,
        )

    except Exception as e:
        logger.exception("Strategy performance evaluation failed", error=str(e))
        return build_strategy_failure(e)


def _try_promote_strategy(
    strategy: Any,
    strategy_storage: Any,
    min_days: int,
    min_sharpe: float,
) -> str | None:
    """Attempt to promote a single testing strategy.

    Returns a result message if promoted, None if criteria not met.
    Raises on unexpected errors.
    """
    skip_reason = _promotion_skip_reason(strategy, min_days, min_sharpe)
    if skip_reason:
        logger.debug("Skipping strategy promotion", strategy_name=strategy.name, reason=skip_reason)
        return None

    strategy_storage.activate_strategy(strategy.id)
    days = _days_since(strategy.created_at)
    expected_sharpe = float(strategy.expected_sharpe or 0.0)
    logger.info(
        "Strategy auto-promoted",
        strategy_id=strategy.id,
        strategy_name=strategy.name,
        expected_sharpe=expected_sharpe,
        days_since_creation=days,
    )
    return f"Promoted {strategy.name} (Sharpe={expected_sharpe:.2f}, age={days}d)"


def _process_testing_strategies(
    strategy_storage: Any,
    testing_strategies: list[Any],
    min_days: int,
    min_sharpe: float,
) -> tuple[int, list[str]]:
    """Process all testing strategies; return (promoted_count, messages)."""
    results: list[str] = []
    promoted_count = 0
    for strategy in testing_strategies:
        try:
            msg = _try_promote_strategy(strategy, strategy_storage, min_days, min_sharpe)
            if msg:
                results.append(msg)
                promoted_count += 1
        except Exception as e:
            logger.exception(
                "Failed to evaluate strategy for promotion",
                strategy_id=strategy.id,
                error=str(e),
            )
    return promoted_count, results


def auto_promote_strategies(
    min_days: int = 3,
    min_sharpe: float = MIN_SHARPE_FOR_PROMOTION,
) -> StrategyMonitoringResultDict:
    """Auto-promote testing strategies that meet validation criteria.

    Schedule: Daily at 04:15 UTC (after performance evaluation).
    Promotes strategies in 'testing' for >= min_days with expected
    Sharpe >= min_sharpe and no blocking issues.

    Args:
        min_days: Minimum days in testing before promotion (default 3)
        min_sharpe: Minimum expected Sharpe to promote (default 1.0)

    Returns:
        Summary dict with promotion results
    """
    logger.info(
        "Starting auto-promotion of validated strategies",
        min_days=min_days,
        min_sharpe=min_sharpe,
    )

    try:
        strategy_storage = get_strategy_storage()
        testing_strategies = strategy_storage.list_strategies(status="testing")

        if not testing_strategies:
            logger.info("No testing strategies to evaluate")
            return build_strategy_success(details=[])

        logger.info("Evaluating testing strategies for promotion", count=len(testing_strategies))
        promoted_count, results = _process_testing_strategies(
            strategy_storage, testing_strategies, min_days, min_sharpe
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
