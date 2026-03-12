"""Strategy Evolution Agent - LLM-powered strategy improvement system.

This agent analyzes underperforming strategies and generates improved versions
using walk-forward backtesting validation. Evolution occurs when:
- Strategy underperforms parent by >10% (Sharpe ratio)
- New version must beat parent AND buy-and-hold benchmark

MAS (Minimum Acceptable Score):
- Must maintain >= 90% of parent strategy's Sharpe ratio
- OR must beat buy-and-hold benchmark Sharpe ratio
"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict

from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.models import StrategyParameters
from app.strategies.optimizer import StrategyOptimizer
from app.strategies.research_aggregator import get_research_aggregator
from app.strategies.storage import get_strategy_storage

from .backtest import run_walk_forward_validation
from .llm_prompts import propose_mutations
from .models import BacktestMetrics, EvolutionResult, StrategyMutation
from .performance import analyze_strategy_performance
from .result_builder import build_failure_result, build_success_result

logger = get_logger(__name__)


class StrategyEvolutionAgent:
    """LLM-powered agent that evolves underperforming strategies."""

    def __init__(self) -> None:
        """Initialize evolution agent."""
        self.optimizer = StrategyOptimizer()
        self.research_aggregator = get_research_aggregator()
        self.strategy_storage = get_strategy_storage()

    async def evolve_strategy(
        self,
        strategy_id: str,
        reason: str = "underperforming",
    ) -> EvolutionResult:
        """Evolve strategy through LLM-guided mutation and backtesting.

        Evolution cycle:
        1. Analyze current performance with LLM
        2. Propose mutations
        3. Test each mutation via walk-forward backtest
        4. Select best mutation if it meets MAS (Minimum Acceptable Score)
        5. Save evolved strategy with lineage tracking

        MAS Criteria:
        - Child Sharpe >= 90% of parent Sharpe
        - OR Child Sharpe > Buy & Hold Sharpe

        Args:
            strategy_id: Strategy UUID to evolve
            reason: Reason for evolution (default: "underperforming")

        Returns:
            EvolutionResult with success status and new strategy ID
        """
        logger.info("strategy_evolution_started", strategy_id=strategy_id, reason=reason)

        # Get strategy
        strategy = self.strategy_storage.get_strategy_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_id}")

        # 1. Analyze performance
        analysis = await analyze_strategy_performance(strategy, days=30)

        if not analysis.underperforming:
            return build_failure_result(
                strategy_id=strategy_id,
                reason=reason,
                message=f"Strategy not underperforming ({analysis.performance_ratio:.1%} of expected)",
                parent_sharpe=analysis.expected_sharpe,
                buy_hold_sharpe=analysis.buy_hold_sharpe,
            )

        # 2. Propose mutations
        mutations = await propose_mutations(strategy, analysis)

        if not mutations:
            return build_failure_result(
                strategy_id=strategy_id,
                reason=reason,
                message="LLM failed to propose mutations",
                parent_sharpe=analysis.expected_sharpe,
                buy_hold_sharpe=analysis.buy_hold_sharpe,
            )

        logger.info("testing_mutations", count=len(mutations))

        # 3. Test each mutation
        best_mutation: StrategyMutation | None = None
        best_sharpe = analysis.actual_sharpe
        best_metrics: BacktestMetrics | None = None

        for i, mutation in enumerate(mutations, 1):
            logger.info("testing_mutation", index=i, total=len(mutations), mutation_type=mutation.mutation_type)

            # Apply mutation to parameters
            mutated_params = strategy.parameters.copy()
            mutated_params.update(mutation.parameter_changes)

            # Validate mutated parameters
            try:
                StrategyParameters(**mutated_params)
            except Exception as e:
                logger.warning("invalid_mutation_params", error=str(e))
                continue

            # Run walk-forward backtest (3 windows, 180/60 days each)
            try:
                metrics = await run_walk_forward_validation(
                    symbol=strategy.symbol,
                    parameters=mutated_params,
                    lookback_days=365,
                    training_days=180,
                    validation_days=60,
                )

                avg_sharpe = metrics.sharpe_ratio
                logger.info(
                    f"Mutation {i} results: Sharpe={avg_sharpe:.2f}, "
                    f"WinRate={metrics.win_rate:.1%}, Drawdown={metrics.max_drawdown:.1%}"
                )

                # Check if better than current best
                if avg_sharpe > best_sharpe:
                    best_sharpe = avg_sharpe
                    best_mutation = mutation
                    best_metrics = metrics

            except Exception as e:
                logger.exception(f"Walk-forward backtest failed for mutation {i}: {e}")
                continue

        # 4. Check MAS (Minimum Acceptable Score)
        if not best_mutation or not best_metrics:
            return build_failure_result(
                strategy_id=strategy_id,
                reason=reason,
                message="No mutations improved performance",
                parent_sharpe=analysis.expected_sharpe,
                buy_hold_sharpe=analysis.buy_hold_sharpe,
                mutations_tested=len(mutations),
            )

        # MAS check
        mas_threshold = max(
            analysis.expected_sharpe * 0.9,  # 90% of parent
            analysis.buy_hold_sharpe,  # OR beat benchmark
        )

        if best_sharpe < mas_threshold:
            return build_failure_result(
                strategy_id=strategy_id,
                reason=reason,
                message=f"Best mutation ({best_sharpe:.2f}) below MAS threshold ({mas_threshold:.2f})",
                parent_sharpe=analysis.expected_sharpe,
                buy_hold_sharpe=analysis.buy_hold_sharpe,
                mutations_tested=len(mutations),
                child_sharpe=best_sharpe,
                best_mutation=best_mutation,
            )

        # 5. Save evolved strategy
        logger.info(
            f"Evolution successful! Best Sharpe: {best_sharpe:.2f} "
            f"(improvement: {(best_sharpe - analysis.actual_sharpe):.2f})"
        )

        # Apply best mutation
        evolved_params = strategy.parameters.copy()
        evolved_params.update(best_mutation.parameter_changes)

        # Get fresh research for the new strategy
        research = await self.research_aggregator.aggregate_research(
            symbol=strategy.symbol,
            lookback_days=30,
        )

        # Store new strategy
        new_strategy_id = self.strategy_storage.store_strategy(
            symbol=strategy.symbol,
            strategy_type=strategy.strategy_type,
            parameters=evolved_params,
            research_summary=asdict(research),
            generation_reasoning=f"Evolved from {strategy.name} v{strategy.version}: {best_mutation.reasoning}",
            backtest_metrics=[asdict(best_metrics)],
            expected_sharpe=best_sharpe,
            expected_win_rate=best_metrics.win_rate,
            expected_max_drawdown=best_metrics.max_drawdown,
            created_by=f"evolution_agent:{uuid.uuid4()}",
            status="testing",  # Start in testing, will auto-promote if validates
        )

        # Track lineage
        self._save_lineage(
            child_strategy_id=new_strategy_id,
            parent_strategy_id=strategy_id,
            changes_description=best_mutation.reasoning,
            evolution_reason=reason,
            metrics_before={
                "sharpe": analysis.actual_sharpe,
                "win_rate": analysis.win_rate,
                "max_drawdown": analysis.max_drawdown,
            },
            metrics_after={
                "sharpe": best_sharpe,
                "win_rate": best_metrics.win_rate,
                "max_drawdown": best_metrics.max_drawdown,
            },
        )

        # Archive parent strategy
        self.strategy_storage.archive_strategy(
            strategy_id=strategy_id,
            reason=f"Superseded by evolved version (v{strategy.version + 1})",
        )

        logger.info("evolution_complete", parent_id=strategy_id, child_id=new_strategy_id)

        return build_success_result(
            original_strategy_id=strategy_id,
            new_strategy_id=new_strategy_id,
            parent_sharpe=analysis.actual_sharpe,
            child_sharpe=best_sharpe,
            buy_hold_sharpe=analysis.buy_hold_sharpe,
            best_mutation=best_mutation,
            mutations_tested=len(mutations),
            reason=reason,
        )

    def _save_lineage(
        self,
        child_strategy_id: str,
        parent_strategy_id: str,
        changes_description: str,
        evolution_reason: str,
        metrics_before: dict[str, float],
        metrics_after: dict[str, float],
    ) -> None:
        """Save strategy lineage to database.

        Args:
            child_strategy_id: New strategy UUID
            parent_strategy_id: Original strategy UUID
            changes_description: What changed
            evolution_reason: Why evolution was triggered
            metrics_before: Parent metrics
            metrics_after: Child metrics
        """
        with get_connection_manager().connection() as conn:
            conn.execute(
                """
                INSERT INTO strategy_lineage (
                    child_strategy_id,
                    parent_strategy_id,
                    changes_description,
                    evolution_reason,
                    metrics_before,
                    metrics_after
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    child_strategy_id,
                    parent_strategy_id,
                    changes_description,
                    evolution_reason,
                    json.dumps(metrics_before),
                    json.dumps(metrics_after),
                ),
            )
            conn.commit()

        logger.info("lineage_saved", parent_id=parent_strategy_id, child_id=child_strategy_id)


# Singleton instance
_evolution_agent: StrategyEvolutionAgent | None = None


def get_strategy_evolution_agent() -> StrategyEvolutionAgent:
    """Get singleton instance of strategy evolution agent."""
    global _evolution_agent  # noqa: PLW0603
    if _evolution_agent is None:
        _evolution_agent = StrategyEvolutionAgent()
    return _evolution_agent
