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
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any

from app.agents.llm_client import AgentHubAPIClient
from app.backtest.walk_forward import WalkForwardEngine
from app.constants import GEMINI_FLASH
from app.logging_config import get_logger
from app.storage.connection import get_connection_manager
from app.strategies.models import StrategyDefinition, StrategyParameters
from app.strategies.optimizer import StrategyOptimizer
from app.strategies.research_aggregator import get_research_aggregator
from app.strategies.storage import get_strategy_storage

logger = get_logger(__name__)


@dataclass
class BacktestMetrics:
    """Simplified backtest metrics for evolution."""

    sharpe_ratio: float
    win_rate: float
    max_drawdown: float
    total_return: float
    num_trades: int


async def run_walk_forward_validation(
    symbol: str,
    parameters: dict[str, Any],
    lookback_days: int = 365,
    training_days: int = 180,
    validation_days: int = 60,
) -> BacktestMetrics:
    """Run walk-forward validation for strategy parameters.

    Args:
        symbol: Stock symbol
        parameters: Strategy parameters dict
        lookback_days: Total lookback period (default 365 days)
        training_days: Training window size (default 180 days)
        validation_days: Validation window size (default 60 days)

    Returns:
        BacktestMetrics with aggregated results
    """
    from datetime import date, timedelta

    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    # Create walk-forward engine
    engine = WalkForwardEngine(
        train_days=training_days,
        val_days=validation_days,
        test_days=validation_days,  # Use same size for test
        gap_days=10,
        step_days=60,
    )

    # Extract parameters
    min_confirmations = parameters.get("min_confirmations", 6)
    stop_loss_atr = parameters.get("stop_loss_atr_multiplier", 2.0)
    max_holding_days = parameters.get("max_holding_days", 60)

    # Run walk-forward
    result = engine.run_walk_forward(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        strategy_type="enhanced",
        min_confirmations=min_confirmations,
        stop_loss_atr_multiplier=float(stop_loss_atr),
        max_holding_days=max_holding_days,
    )

    # Return simplified metrics
    return BacktestMetrics(
        sharpe_ratio=result.mean_sharpe,
        win_rate=result.mean_win_rate,
        max_drawdown=result.max_drawdown_pct / 100.0,  # Convert to 0-1
        total_return=result.mean_return_pct,
        num_trades=result.total_trades,
    )


@dataclass
class StrategyAnalysis:
    """Analysis of strategy performance over recent period."""

    strategy_id: str
    symbol: str
    days_analyzed: int

    # Performance metrics
    actual_sharpe: float
    expected_sharpe: float
    performance_ratio: float  # actual / expected

    # Trade statistics
    trades_count: int
    win_rate: float
    avg_pnl: float
    max_drawdown: float

    # Diagnosis
    underperforming: bool
    diagnosis: str  # LLM-generated analysis

    # Buy & Hold comparison
    buy_hold_sharpe: float
    beats_benchmark: bool


@dataclass
class StrategyMutation:
    """Proposed change to strategy parameters."""

    mutation_type: str  # "weight_adjustment", "threshold_change", "risk_tightening"
    parameter_changes: dict[str, Any]  # {param_name: new_value}
    reasoning: str  # Why this mutation should help
    confidence: float  # 0-1, LLM's confidence in this mutation


@dataclass
class EvolutionResult:
    """Result of strategy evolution attempt."""

    success: bool
    original_strategy_id: str
    new_strategy_id: str | None

    # Metrics comparison
    parent_sharpe: float
    child_sharpe: float | None
    buy_hold_sharpe: float

    # Lineage tracking
    changes_description: str
    evolution_reason: str

    # Metadata
    mutations_tested: int
    best_mutation: StrategyMutation | None
    message: str


class StrategyEvolutionAgent:
    """LLM-powered agent that evolves underperforming strategies."""

    def __init__(self) -> None:
        """Initialize evolution agent."""
        self.optimizer = StrategyOptimizer()
        self.research_aggregator = get_research_aggregator()
        self.strategy_storage = get_strategy_storage()

    async def analyze_strategy_performance(
        self,
        strategy_id: str,
        days: int = 30,
    ) -> StrategyAnalysis:
        """Analyze strategy performance using LLM diagnosis.

        Args:
            strategy_id: Strategy UUID
            days: Days of history to analyze (default 30)

        Returns:
            StrategyAnalysis with LLM-generated diagnosis
        """
        logger.info(f"Analyzing strategy performance: {strategy_id} ({days} days)")

        strategy = self.strategy_storage.get_strategy_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_id}")

        # Get performance metrics from strategy_performance table
        cutoff_date = date.today() - timedelta(days=days)

        with get_connection_manager().connection() as conn:
            result = conn.execute(
                """
                SELECT
                    COUNT(*) as trades,
                    AVG(CASE WHEN pnl_today > 0 THEN 1.0 ELSE 0.0 END) as win_rate,
                    AVG(pnl_today) as avg_pnl,
                    AVG(sharpe_ratio_30d) as actual_sharpe,
                    MAX(max_drawdown_30d) as max_drawdown
                FROM strategy_performance
                WHERE strategy_id = %s AND date >= %s
                """,
                [strategy_id, cutoff_date.isoformat()],
            ).fetchone()

        if not result:
            # No trades in period
            raise ValueError(f"No performance data for strategy {strategy_id} in last {days} days")

        # Type narrowing for result[0] - COUNT(*) returns int, never None
        trade_count_raw = result[0]
        if trade_count_raw is None or (
            isinstance(trade_count_raw, (int, float, str)) and int(trade_count_raw) == 0
        ):
            raise ValueError(f"No performance data for strategy {strategy_id} in last {days} days")

        trades_count = int(trade_count_raw)
        win_rate = float(result[1] or 0.0)
        avg_pnl = float(result[2] or 0.0)
        actual_sharpe = float(result[3] or 0.0)
        max_drawdown = float(result[4] or 0.0)

        expected_sharpe = float(strategy.expected_sharpe or 0.0)
        performance_ratio = actual_sharpe / expected_sharpe if expected_sharpe > 0 else 0.0

        # Calculate buy-and-hold benchmark (SPY)
        buy_hold_sharpe = await self._calculate_buy_hold_sharpe(strategy.symbol, days)
        beats_benchmark = actual_sharpe > buy_hold_sharpe

        # Determine if underperforming
        underperforming = performance_ratio < 0.9  # <90% of expected

        # LLM diagnosis
        diagnosis = await self._llm_diagnose_performance(
            strategy=strategy,
            actual_sharpe=actual_sharpe,
            expected_sharpe=expected_sharpe,
            trades_count=trades_count,
            win_rate=win_rate,
            avg_pnl=avg_pnl,
            max_drawdown=max_drawdown,
            buy_hold_sharpe=buy_hold_sharpe,
        )

        return StrategyAnalysis(
            strategy_id=strategy_id,
            symbol=strategy.symbol,
            days_analyzed=days,
            actual_sharpe=actual_sharpe,
            expected_sharpe=expected_sharpe,
            performance_ratio=performance_ratio,
            trades_count=trades_count,
            win_rate=win_rate,
            avg_pnl=avg_pnl,
            max_drawdown=max_drawdown,
            underperforming=underperforming,
            diagnosis=diagnosis,
            buy_hold_sharpe=buy_hold_sharpe,
            beats_benchmark=beats_benchmark,
        )

    async def propose_mutations(
        self,
        strategy: StrategyDefinition,
        analysis: StrategyAnalysis,
    ) -> list[StrategyMutation]:
        """Generate strategy mutations using LLM.

        Args:
            strategy: Current strategy definition
            analysis: Performance analysis

        Returns:
            List of proposed mutations (max 5)
        """
        logger.info(
            f"Proposing mutations for {strategy.symbol} (Sharpe: {analysis.actual_sharpe:.2f})"
        )

        # Build LLM prompt
        prompt = f"""You are a quantitative trading strategist analyzing an underperforming strategy.

**Current Strategy:**
- Symbol: {strategy.symbol}
- Type: {strategy.strategy_type}
- Parameters: {json.dumps(strategy.parameters, indent=2)}

**Performance Analysis:**
- Actual Sharpe: {analysis.actual_sharpe:.2f}
- Expected Sharpe: {analysis.expected_sharpe:.2f}
- Performance Ratio: {analysis.performance_ratio:.1%}
- Win Rate: {analysis.win_rate:.1%}
- Trades: {analysis.trades_count}
- Max Drawdown: {analysis.max_drawdown:.1%}
- Buy & Hold Sharpe: {analysis.buy_hold_sharpe:.2f}
- Beats Benchmark: {analysis.beats_benchmark}

**Diagnosis:**
{analysis.diagnosis}

**Your Task:**
Propose 3-5 specific parameter mutations that could improve performance. Each mutation should:
1. Target a specific weakness identified in the diagnosis
2. Make conservative changes (10-20% adjustments, not radical shifts)
3. Explain why the change should help

Return JSON array with this schema:
[
  {{
    "mutation_type": "weight_adjustment|threshold_change|risk_tightening|entry_timing",
    "parameter_changes": {{"param_name": new_value}},
    "reasoning": "Why this should improve performance",
    "confidence": 0.75
  }}
]

**Critical Rules:**
- If adjusting weights, ensure they still sum to 1.0
- Keep thresholds within valid ranges (RSI 0-100, sentiment -1 to +1)
- Don't change more than 3 parameters per mutation
- Focus on the most impactful changes first
"""

        # Call LLM
        # TODO: Replace with MCP-based agent coordination (see tasks/tasks-0100-multi-agent-mcp-architecture.md)
        client = AgentHubAPIClient(model=GEMINI_FLASH)
        response = client.generate(
            prompt=prompt,
            system="You are a quantitative trading strategy optimizer. Analyze underperforming strategies and propose concrete parameter improvements.",
            temperature=0.7,  # Allow some creativity
            purpose="strategy_evolution",
        )

        # Parse mutations
        try:
            mutations_data = json.loads(response.content)
            mutations = [
                StrategyMutation(
                    mutation_type=m["mutation_type"],
                    parameter_changes=m["parameter_changes"],
                    reasoning=m["reasoning"],
                    confidence=m["confidence"],
                )
                for m in mutations_data
            ]
            logger.info(f"LLM proposed {len(mutations)} mutations")
            return mutations[:5]  # Limit to 5
        except Exception as e:
            logger.exception(f"Failed to parse LLM mutations: {e}")
            return []

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
        logger.info(f"Starting strategy evolution: {strategy_id} (reason: {reason})")

        # 1. Analyze performance
        analysis = await self.analyze_strategy_performance(strategy_id, days=30)

        if not analysis.underperforming:
            return EvolutionResult(
                success=False,
                original_strategy_id=strategy_id,
                new_strategy_id=None,
                parent_sharpe=analysis.expected_sharpe,
                child_sharpe=None,
                buy_hold_sharpe=analysis.buy_hold_sharpe,
                changes_description="",
                evolution_reason=reason,
                mutations_tested=0,
                best_mutation=None,
                message=f"Strategy not underperforming ({analysis.performance_ratio:.1%} of expected)",
            )

        strategy = self.strategy_storage.get_strategy_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_id}")

        # 2. Propose mutations
        mutations = await self.propose_mutations(strategy, analysis)

        if not mutations:
            return EvolutionResult(
                success=False,
                original_strategy_id=strategy_id,
                new_strategy_id=None,
                parent_sharpe=analysis.expected_sharpe,
                child_sharpe=None,
                buy_hold_sharpe=analysis.buy_hold_sharpe,
                changes_description="",
                evolution_reason=reason,
                mutations_tested=0,
                best_mutation=None,
                message="LLM failed to propose mutations",
            )

        logger.info(f"Testing {len(mutations)} mutations via walk-forward backtest")

        # 3. Test each mutation
        best_mutation: StrategyMutation | None = None
        best_sharpe = analysis.actual_sharpe
        best_metrics: BacktestMetrics | None = None

        for i, mutation in enumerate(mutations, 1):
            logger.info(f"Testing mutation {i}/{len(mutations)}: {mutation.mutation_type}")

            # Apply mutation to parameters
            mutated_params = strategy.parameters.copy()
            mutated_params.update(mutation.parameter_changes)

            # Validate mutated parameters
            try:
                StrategyParameters(**mutated_params)
            except Exception as e:
                logger.warning(f"Invalid mutation parameters: {e}")
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
            return EvolutionResult(
                success=False,
                original_strategy_id=strategy_id,
                new_strategy_id=None,
                parent_sharpe=analysis.expected_sharpe,
                child_sharpe=None,
                buy_hold_sharpe=analysis.buy_hold_sharpe,
                changes_description="",
                evolution_reason=reason,
                mutations_tested=len(mutations),
                best_mutation=None,
                message="No mutations improved performance",
            )

        # MAS check
        mas_threshold = max(
            analysis.expected_sharpe * 0.9,  # 90% of parent
            analysis.buy_hold_sharpe,  # OR beat benchmark
        )

        if best_sharpe < mas_threshold:
            return EvolutionResult(
                success=False,
                original_strategy_id=strategy_id,
                new_strategy_id=None,
                parent_sharpe=analysis.expected_sharpe,
                child_sharpe=best_sharpe,
                buy_hold_sharpe=analysis.buy_hold_sharpe,
                changes_description=best_mutation.reasoning,
                evolution_reason=reason,
                mutations_tested=len(mutations),
                best_mutation=best_mutation,
                message=f"Best mutation ({best_sharpe:.2f}) below MAS threshold ({mas_threshold:.2f})",
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

        logger.info(f"Evolution complete: {strategy_id} → {new_strategy_id}")

        return EvolutionResult(
            success=True,
            original_strategy_id=strategy_id,
            new_strategy_id=new_strategy_id,
            parent_sharpe=analysis.actual_sharpe,
            child_sharpe=best_sharpe,
            buy_hold_sharpe=analysis.buy_hold_sharpe,
            changes_description=best_mutation.reasoning,
            evolution_reason=reason,
            mutations_tested=len(mutations),
            best_mutation=best_mutation,
            message=f"Evolution successful: Sharpe {analysis.actual_sharpe:.2f} → {best_sharpe:.2f}",
        )

    async def _llm_diagnose_performance(
        self,
        strategy: StrategyDefinition,
        actual_sharpe: float,
        expected_sharpe: float,
        trades_count: int,
        win_rate: float,
        avg_pnl: float,
        max_drawdown: float,
        buy_hold_sharpe: float,
    ) -> str:
        """Use LLM to diagnose why strategy is underperforming.

        Args:
            strategy: Strategy definition
            actual_sharpe: Actual Sharpe ratio
            expected_sharpe: Expected Sharpe ratio
            trades_count: Number of trades
            win_rate: Win rate (0-1)
            avg_pnl: Average P&L per trade
            max_drawdown: Maximum drawdown (0-1)
            buy_hold_sharpe: Buy & hold benchmark Sharpe

        Returns:
            LLM-generated diagnosis (2-3 sentences)
        """
        prompt = f"""Analyze this underperforming trading strategy and diagnose the likely root cause.

**Strategy:**
- Symbol: {strategy.symbol}
- Type: {strategy.strategy_type}
- Parameters: {json.dumps(strategy.parameters, indent=2)}

**Performance:**
- Expected Sharpe: {expected_sharpe:.2f}
- Actual Sharpe: {actual_sharpe:.2f}
- Shortfall: {(expected_sharpe - actual_sharpe):.2f}
- Win Rate: {win_rate:.1%}
- Avg P&L: ${avg_pnl:.2f}
- Max Drawdown: {max_drawdown:.1%}
- Trades: {trades_count}
- Buy & Hold Sharpe: {buy_hold_sharpe:.2f}

Provide a 2-3 sentence diagnosis identifying the most likely cause of underperformance.
Focus on actionable insights (e.g., "too aggressive entries", "holding too long", "ignoring volatility").
"""

        # TODO: Replace with MCP-based agent coordination (see tasks/tasks-0100-multi-agent-mcp-architecture.md)
        client = AgentHubAPIClient(model=GEMINI_FLASH)
        response = client.generate(
            prompt=prompt,
            system="You are a quantitative trading analyst. Diagnose strategy underperformance concisely.",
            temperature=0.3,
            purpose="underperformance_diagnosis",
        )

        return response.content

    async def _calculate_buy_hold_sharpe(self, symbol: str, days: int) -> float:
        """Calculate buy-and-hold Sharpe ratio for benchmark.

        Args:
            symbol: Stock symbol
            days: Number of days to calculate over

        Returns:
            Buy & hold Sharpe ratio
        """
        # Use SPY as benchmark for all stocks
        benchmark_symbol = "SPY"

        with get_connection_manager().connection() as conn:
            result = conn.execute(
                """
                SELECT close
                FROM day_bars
                WHERE symbol = %s
                  AND date >= CURRENT_DATE - INTERVAL '%s days'
                ORDER BY date
                """,
                (benchmark_symbol, days),
            ).fetchall()

        if len(result) < 2:
            logger.warning(f"Insufficient data for buy-hold calculation ({len(result)} days)")
            return 0.0

        # Calculate daily returns - type narrowing for row[0]
        prices: list[float] = []
        for row in result:
            price_val = row[0]
            if price_val is not None:
                prices.append(float(price_val))

        if len(prices) < 2:
            logger.warning(
                f"Insufficient non-null prices for buy-hold calculation ({len(prices)} prices)"
            )
            return 0.0
        returns = [(prices[i] - prices[i - 1]) / prices[i - 1] for i in range(1, len(prices))]

        # Calculate Sharpe ratio using mean return divided by standard deviation, then annualized
        if len(returns) < 2:
            return 0.0

        mean_return = sum(returns) / len(returns)
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance**0.5

        if std_dev == 0:
            return 0.0

        # Annualize (252 trading days)
        sharpe = (mean_return / std_dev) * (252**0.5)
        return float(sharpe)

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

        logger.info(f"Lineage saved: {parent_strategy_id} → {child_strategy_id}")


# Singleton instance
_evolution_agent: StrategyEvolutionAgent | None = None


def get_strategy_evolution_agent() -> StrategyEvolutionAgent:
    """Get singleton instance of strategy evolution agent."""
    global _evolution_agent  # noqa: PLW0603
    if _evolution_agent is None:
        _evolution_agent = StrategyEvolutionAgent()
    return _evolution_agent
