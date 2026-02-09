"""Strategy evolution tasks.

Celery tasks for evolving underperforming strategies using LLM-based
parameter mutation and walk-forward backtesting.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.logging_config import get_logger
from app.strategies.storage import StrategyStorage, get_strategy_storage

logger = get_logger(__name__)

# Strategy limits
MAX_EVOLUTION_STRATEGIES = 5  # Maximum strategies to evolve per week

# Error handling
ERROR_MESSAGE_TRUNCATE = 100  # Truncate error messages to prevent log bloat


def weekly_strategy_evolution() -> dict[str, Any]:
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
    logger.info("Starting weekly strategy evolution")

    from app.agents.strategy_evolution_agent import get_strategy_evolution_agent

    try:
        evolution_agent = get_strategy_evolution_agent()
        strategy_storage = get_strategy_storage()

        # Find underperforming active strategies (performance < 90% of expected)
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

        results = []
        evolved_count = 0

        for row in underperforming_strategies:
            strategy_id = str(row[0])
            symbol = row[1]
            name = row[2]
            expected_sharpe = float(row[3] or 0.0)
            actual_sharpe = float(row[4] or 0.0)
            performance_ratio = float(row[5] or 0.0)

            logger.info(
                "Attempting strategy evolution",
                symbol=symbol,
                strategy_name=name,
                actual_sharpe=actual_sharpe,
                expected_sharpe=expected_sharpe,
                performance_ratio=performance_ratio,
            )

            try:
                # Evolve strategy
                result = asyncio.run(
                    evolution_agent.evolve_strategy(
                        strategy_id=strategy_id,
                        reason=f"underperforming_{performance_ratio:.0%}",
                    )
                )

                if result.success:
                    evolved_count += 1
                    results.append(
                        f"Evolved {symbol}: {result.parent_sharpe:.2f} → {result.child_sharpe:.2f} "
                        f"({result.mutations_tested} mutations tested)"
                    )
                    logger.info(
                        "Strategy evolved successfully",
                        symbol=symbol,
                        original_id=strategy_id,
                        new_id=result.new_strategy_id,
                        sharpe_improvement=result.child_sharpe - result.parent_sharpe
                        if result.child_sharpe
                        else 0,
                    )
                else:
                    results.append(f"Evolution failed for {symbol}: {result.message}")
                    logger.info(
                        "Strategy evolution failed",
                        symbol=symbol,
                        strategy_id=strategy_id,
                        reason=result.message,
                    )

            except Exception as e:
                logger.exception("Strategy evolution error", symbol=symbol, error=str(e))
                results.append(f"Error for {symbol}: {str(e)[:ERROR_MESSAGE_TRUNCATE]}")

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

    except Exception as e:
        logger.exception("Weekly strategy evolution failed", error=str(e))
        return {"status": "failed", "error": str(e)}
