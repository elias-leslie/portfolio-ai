"""Strategy evolution tasks.

Tasks for evolving underperforming strategies using LLM-based
parameter mutation and walk-forward backtesting.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from app.constants import ERROR_MESSAGE_TRUNCATE
from app.logging_config import get_logger
from app.services.preferences_service import get_automation_preferences
from app.strategies.storage import StrategyStorage, get_strategy_storage

if TYPE_CHECKING:
    from app.agents.strategy_evolution import StrategyEvolutionAgent

logger = get_logger(__name__)

# Strategy limits
MAX_EVOLUTION_STRATEGIES = 5  # Maximum strategies to evolve per week


def _parse_strategy_row(row: tuple) -> tuple[str, str, str, float, float, float]:
    """Parse a strategy row from the database query result."""
    strategy_id = str(row[0])
    symbol = str(row[1])
    name = str(row[2])
    expected_sharpe = float(row[3] or 0.0)
    actual_sharpe = float(row[4] or 0.0)
    performance_ratio = float(row[5] or 0.0)
    return strategy_id, symbol, name, expected_sharpe, actual_sharpe, performance_ratio


def _evolve_single_strategy(
    evolution_agent: StrategyEvolutionAgent,
    strategy_id: str,
    symbol: str,
    name: str,
    expected_sharpe: float,
    actual_sharpe: float,
    performance_ratio: float,
) -> tuple[bool, str]:
    """Attempt to evolve a single underperforming strategy.

    Returns:
        Tuple of (evolved: bool, detail_message: str)
    """
    logger.info(
        "Attempting strategy evolution",
        symbol=symbol,
        strategy_name=name,
        actual_sharpe=actual_sharpe,
        expected_sharpe=expected_sharpe,
        performance_ratio=performance_ratio,
    )

    try:
        result = asyncio.run(
            evolution_agent.evolve_strategy(
                strategy_id=strategy_id,
                reason=f"underperforming_{performance_ratio:.0%}",
            )
        )
    except Exception as e:
        logger.exception("Strategy evolution error", symbol=symbol, error=str(e))
        return False, f"Error for {symbol}: {str(e)[:ERROR_MESSAGE_TRUNCATE]}"

    if not result.success:
        logger.info(
            "Strategy evolution failed",
            symbol=symbol,
            strategy_id=strategy_id,
            reason=result.message,
        )
        return False, f"Evolution failed for {symbol}: {result.message}"

    sharpe_improvement = (result.child_sharpe - result.parent_sharpe) if result.child_sharpe else 0
    logger.info(
        "Strategy evolved successfully",
        symbol=symbol,
        original_id=strategy_id,
        new_id=result.new_strategy_id,
        sharpe_improvement=sharpe_improvement,
    )
    detail = (
        f"Evolved {symbol}: {result.parent_sharpe:.2f} → {result.child_sharpe:.2f} "
        f"({result.mutations_tested} mutations tested)"
    )
    return True, detail


def weekly_strategy_evolution() -> dict[str, object]:
    """Weekly strategy evolution - evolve underperforming strategies via LLM.

    Schedule: Weekly on Sunday at 06:00 UTC (after weekly strategy generation)

    Evolution Logic:
    1. Find active strategies underperforming by >10% (Sharpe ratio)
    2. For each strategy:
       - Analyze performance with LLM diagnosis
       - Propose parameter mutations
       - Test mutations via walk-forward backtest
       - Save best mutation if it meets MAS (Minimum Acceptable Score)
    3. Archive parent strategy, activate evolved child

    MAS Criteria:
    - Child Sharpe >= 90% of parent Sharpe
    - OR Child Sharpe > Buy & Hold Benchmark

    Returns:
        Summary dict with evolution results
    """
    automation = get_automation_preferences()
    if not bool(automation["scheduled_strategy_research_enabled"]["enabled"]):
        logger.info("weekly_strategy_evolution_skipped", reason="scheduled_strategy_research_disabled")
        return {"status": "skipped", "reason": "scheduled_strategy_research_disabled"}

    logger.info("Starting weekly strategy evolution")

    from app.agents.strategy_evolution import get_strategy_evolution_agent

    try:
        return _run_evolution(get_strategy_evolution_agent(), get_strategy_storage())
    except Exception as e:
        logger.exception("Weekly strategy evolution failed", error=str(e))
        return {"status": "failed", "error": str(e)}


def _run_evolution(
    evolution_agent: StrategyEvolutionAgent,
    strategy_storage: StrategyStorage,
) -> dict[str, object]:
    """Core evolution logic: fetch underperforming strategies and evolve each."""
    underperforming_strategies = strategy_storage.get_underperforming_strategies(
        performance_threshold=StrategyStorage.DEFAULT_PERFORMANCE_THRESHOLD,
        limit=MAX_EVOLUTION_STRATEGIES,
    )

    if not underperforming_strategies:
        logger.info("No underperforming strategies found")
        return {
            "status": "completed",
            "strategies_evaluated": 0,
            "strategies_evolved": 0,
            "details": [],
        }

    logger.info("Found underperforming strategies", count=len(underperforming_strategies))

    results: list[str] = []
    evolved_count = 0

    for row in underperforming_strategies:
        strategy_id, symbol, name, expected_sharpe, actual_sharpe, performance_ratio = (
            _parse_strategy_row(row)
        )
        evolved, detail = _evolve_single_strategy(
            evolution_agent,
            strategy_id,
            symbol,
            name,
            expected_sharpe,
            actual_sharpe,
            performance_ratio,
        )
        results.append(detail)
        if evolved:
            evolved_count += 1

    logger.info(
        "Weekly strategy evolution complete",
        strategies_evaluated=len(underperforming_strategies),
        strategies_evolved=evolved_count,
    )

    return {
        "status": "completed",
        "strategies_evaluated": len(underperforming_strategies),
        "strategies_evolved": evolved_count,
        "details": results,
    }
