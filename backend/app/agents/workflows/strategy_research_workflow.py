"""Strategy research workflow - orchestrates research-driven strategy generation.

This workflow:
1. Aggregates market research from all sources
2. Generates strategy via LLM agent
3. Optimizes parameters via backtesting
4. Stores strategy in database
5. Commits results to git
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from app.logging_config import get_logger
from app.strategies.optimizer import get_strategy_optimizer
from app.strategies.research_aggregator import get_research_aggregator
from app.strategies.storage import get_strategy_storage
from app.strategies.strategy_generator import get_strategy_generator
from app.utils.git_automation import commit_workflow_results

logger = get_logger(__name__)


async def strategy_research_workflow(
    symbol: str,
    force_regenerate: bool = False,
) -> dict[str, Any]:
    """Generate new strategy from market research.

    Steps:
    1. Check if active strategy exists (skip if exists unless force=True)
    2. Aggregate market research
    3. Generate strategy via LLM agent
    4. Optimize parameters via backtesting
    5. Store strategy in database
    6. Commit to git with research summary

    Args:
        symbol: Stock symbol
        force_regenerate: Regenerate even if active strategy exists

    Returns:
        Dict with workflow results:
        - workflow_id: Workflow UUID
        - status: "completed", "skipped", "blocked", or "failed"
        - strategy_id: Strategy UUID (if completed)
        - commit_sha: Git commit SHA (if completed)
        - message: Status message
        - error_message: Error details (if failed)
    """
    workflow_id = str(uuid.uuid4())

    logger.info(
        "Starting strategy research workflow",
        workflow_id=workflow_id,
        symbol=symbol,
        force_regenerate=force_regenerate,
    )

    try:
        # Step 1: Check existing strategy
        storage = get_strategy_storage()
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

        # Step 2: Aggregate research
        logger.info("Aggregating market research", workflow_id=workflow_id, symbol=symbol)
        aggregator = get_research_aggregator()
        research = await aggregator.aggregate_research(symbol, lookback_days=30)

        if research.overall_confidence < 0.5:
            logger.warning(
                "Insufficient research quality",
                workflow_id=workflow_id,
                symbol=symbol,
                confidence=research.overall_confidence,
                quality=research.research_quality,
            )
            return {
                "workflow_id": workflow_id,
                "status": "blocked",
                "message": f"Insufficient research quality (confidence={research.overall_confidence:.2f})",
            }

        # Step 3: Generate strategy via agent
        logger.info("Generating strategy via LLM agent", workflow_id=workflow_id)
        generator = get_strategy_generator()
        agent_result = await generator.generate_strategy(research)

        if agent_result.strategy_type == "no_strategy":
            logger.warning(
                "Agent recommends no strategy",
                workflow_id=workflow_id,
                reasoning=agent_result.reasoning,
            )
            return {
                "workflow_id": workflow_id,
                "status": "blocked",
                "message": f"Agent recommends no strategy: {agent_result.reasoning}",
            }

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
            research=research,  # Pass real fundamental data for signal classification
            lookback_days=365,
            max_combinations=50,
        )

        # Step 5: Store in database
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
            status="testing",  # Start in testing mode
        )

        # Step 5b: Persist final backtest run to backtest_runs table
        logger.info("Persisting backtest run", workflow_id=workflow_id, strategy_id=strategy_id)
        try:
            backtest_run_id = optimizer.persist_best_backtest(
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
            logger.info(
                "Backtest persisted",
                workflow_id=workflow_id,
                backtest_run_id=backtest_run_id,
            )
        except Exception as e:
            # Non-fatal - strategy still created
            logger.warning(
                "Failed to persist backtest run",
                workflow_id=workflow_id,
                error=str(e),
            )
            backtest_run_id = None

        # Step 6: Commit to git
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

        result_summary = f"Generated {agent_result.strategy_type} strategy for {symbol} (confidence={optimized.confidence:.2f}, Sharpe={optimized.avg_sharpe:.2f})"
        commit_result = commit_workflow_results(
            workflow_type="strategy_research",
            date=datetime.now(UTC),
            result_summary=result_summary,
            snapshot_data=snapshot,
        )

        commit_sha = commit_result.get("commit_sha", "") if isinstance(commit_result, dict) else ""
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

    except Exception as e:
        logger.exception(
            "Strategy research workflow failed",
            workflow_id=workflow_id,
            symbol=symbol,
            error=str(e),
        )
        return {
            "workflow_id": workflow_id,
            "status": "failed",
            "error_message": str(e),
            "message": f"Workflow failed: {str(e)[:100]}",
        }
