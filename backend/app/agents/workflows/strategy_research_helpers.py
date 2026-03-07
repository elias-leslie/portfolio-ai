"""Helper functions for strategy_research_workflow."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

import psycopg2

from app.logging_config import get_logger
from app.strategies.optimizer import get_strategy_optimizer
from app.strategies.research_aggregator import get_research_aggregator
from app.strategies.storage import get_strategy_storage
from app.strategies.strategy_generator import get_strategy_generator
from app.utils.git_automation import commit_workflow_results

if TYPE_CHECKING:
    from app.strategies.models import StrategyDefinition

MIN_RESEARCH_CONFIDENCE = 0.5


class StorageProtocol(Protocol):
    """Minimal interface required by check_existing_strategy."""

    def get_active_strategy(self, symbol: str) -> StrategyDefinition | None: ...

logger = get_logger(__name__)


async def run_workflow_steps(
    symbol: str,
    workflow_id: str,
    force_regenerate: bool,
) -> dict[str, Any]:
    """Execute all workflow steps and return the result dict."""
    # Step 1: Check existing strategy
    storage = get_strategy_storage()
    skip_result = check_existing_strategy(storage, symbol, workflow_id, force_regenerate)
    if skip_result is not None:
        return skip_result

    # Step 2: Aggregate research
    aggregator = get_research_aggregator()
    research, block = await aggregate_and_validate_research(aggregator, symbol, workflow_id)
    if block is not None:
        return block

    # Step 3: Generate strategy via agent
    generator = get_strategy_generator()
    agent_result, block = await generate_and_validate_strategy(generator, research, workflow_id)
    if block is not None:
        return block

    # Step 4: Optimize parameters
    logger.info(
        "Optimizing strategy parameters",
        workflow_id=workflow_id,
        strategy_type=agent_result.strategy_type,
    )
    optimizer = get_strategy_optimizer()
    optimized = await optimizer.optimize_strategy_parameters(
        symbol=symbol,
        strategy_template=agent_result,
        research=research,
        lookback_days=365,
        max_combinations=50,
    )

    # Steps 5 & 5b: Store strategy and persist backtest
    strategy_id, _ = await asyncio.to_thread(
        lambda: store_strategy_and_backtest(
            storage, optimizer, symbol, workflow_id, agent_result, optimized, research
        )
    )

    # Step 6: Commit to git and return result
    return await asyncio.to_thread(
        lambda: commit_and_build_result(
            workflow_id, symbol, strategy_id, agent_result, optimized, research
        )
    )


def check_existing_strategy(
    storage: StorageProtocol,
    symbol: str,
    workflow_id: str,
    force_regenerate: bool,
) -> dict[str, Any] | None:
    """Check if an active strategy exists; return skip result dict or None."""
    existing = storage.get_active_strategy(symbol)
    if existing and not force_regenerate:
        logger.info(
            "Active strategy exists, skipping generation",
            workflow_id=workflow_id,
            strategy_id=existing.id,
            strategy_name=existing.name,
            version=existing.version,
        )
        return {
            "workflow_id": workflow_id,
            "status": "skipped",
            "strategy_id": existing.id,
            "message": f"Active strategy exists: {existing.name} (v{existing.version})",
        }
    return None


async def aggregate_and_validate_research(
    aggregator: Any,
    symbol: str,
    workflow_id: str,
) -> tuple[Any, dict[str, Any] | None]:
    """Aggregate market research; return (research, block_result_or_None)."""
    logger.info("Aggregating market research", workflow_id=workflow_id, symbol=symbol)
    research = await aggregator.aggregate_research(symbol, lookback_days=30)
    if research.overall_confidence < MIN_RESEARCH_CONFIDENCE:
        logger.warning(
            "Insufficient research quality",
            workflow_id=workflow_id,
            symbol=symbol,
            confidence=research.overall_confidence,
            quality=research.research_quality,
        )
        block = {
            "workflow_id": workflow_id,
            "status": "blocked",
            "message": f"Insufficient research quality (confidence={research.overall_confidence:.2f})",
        }
        return research, block
    return research, None


async def generate_and_validate_strategy(
    generator: Any,
    research: Any,
    workflow_id: str,
) -> tuple[Any, dict[str, Any] | None]:
    """Generate strategy via LLM; return (agent_result, block_result_or_None)."""
    logger.info("Generating strategy via LLM agent", workflow_id=workflow_id)
    agent_result = await generator.generate_strategy(research)
    if agent_result.strategy_type == "no_strategy":
        logger.warning(
            "Agent recommends no strategy",
            workflow_id=workflow_id,
            reasoning=agent_result.reasoning,
        )
        block = {
            "workflow_id": workflow_id,
            "status": "blocked",
            "message": f"Agent recommends no strategy: {agent_result.reasoning}",
        }
        return agent_result, block
    return agent_result, None


def store_strategy_and_backtest(
    storage: Any,
    optimizer: Any,
    symbol: str,
    workflow_id: str,
    agent_result: Any,
    optimized: Any,
    research: Any,
) -> tuple[str, str | None]:
    """Store strategy and persist backtest; return (strategy_id, backtest_run_id)."""
    logger.info("Storing strategy in database", workflow_id=workflow_id)
    strategy_id = storage.store_strategy(
        symbol=symbol,
        strategy_type=agent_result.strategy_type,
        parameters=optimized.parameters.model_dump(),
        research_summary=asdict(research),
        generation_reasoning=agent_result.reasoning,
        backtest_metrics=optimized.optimization_metrics,
        expected_sharpe=optimized.avg_sharpe,
        expected_win_rate=optimized.avg_win_rate,
        expected_max_drawdown=optimized.max_drawdown,
        created_by=f"workflow:{workflow_id}",
        status="testing",
    )

    logger.info("Persisting backtest run", workflow_id=workflow_id, strategy_id=strategy_id)
    try:
        backtest_run_id = optimizer.persist_backtest(
            symbol=symbol,
            strategy_name=f"{agent_result.strategy_type}_{symbol}",
            params=optimized.parameters,
            metrics={
                "avg_sharpe": optimized.avg_sharpe,
                "max_drawdown": optimized.max_drawdown,
                "avg_win_rate": optimized.avg_win_rate,
            },
            strategy_id=strategy_id,
        )
        logger.info("Backtest persisted", workflow_id=workflow_id, backtest_run_id=backtest_run_id)
    except (psycopg2.IntegrityError, psycopg2.OperationalError, TimeoutError) as e:
        logger.warning(
            "Failed to persist backtest run",
            workflow_id=workflow_id,
            error=str(e),
            exc_info=True,
        )
        backtest_run_id = None

    return strategy_id, backtest_run_id


def commit_and_build_result(
    workflow_id: str,
    symbol: str,
    strategy_id: str,
    agent_result: Any,
    optimized: Any,
    research: Any,
) -> dict[str, Any]:
    """Commit strategy to git and return completed result dict."""
    logger.info("Committing strategy to git", workflow_id=workflow_id, strategy_id=strategy_id)
    snapshot = {
        "workflow_id": workflow_id,
        "symbol": symbol,
        "strategy_id": strategy_id,
        "strategy_type": agent_result.strategy_type,
        "research_summary": asdict(research),
        "agent_reasoning": agent_result.reasoning,
        "backtest_metrics": optimized.optimization_metrics,
        "confidence": optimized.confidence,
        "expected_sharpe": optimized.avg_sharpe,
        "expected_win_rate": optimized.avg_win_rate,
        "expected_max_drawdown": optimized.max_drawdown,
    }
    result_summary = (
        f"Generated {agent_result.strategy_type} strategy for {symbol} "
        f"(confidence={optimized.confidence:.2f}, Sharpe={optimized.avg_sharpe:.2f})"
    )
    commit_workflow_results(
        workflow_type="strategy_research",
        date=datetime.now(UTC),
        result_summary=result_summary,
        snapshot_data=snapshot,
    )
    # commit_workflow_results returns bool (True = success, False = failure); no commit SHA is provided.
    commit_sha = ""
    logger.info(
        "Strategy research workflow complete",
        workflow_id=workflow_id,
        strategy_id=strategy_id,
        commit_sha=commit_sha,
    )
    return {
        "workflow_id": workflow_id,
        "status": "completed",
        "strategy_id": strategy_id,
        "commit_sha": commit_sha,
        "message": f"Strategy generated successfully (Sharpe={optimized.avg_sharpe:.2f})",
    }
