"""Paper trade validation workflow logic."""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.llm_client import DualProviderClient
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.logging_config import get_logger
from app.storage.facade import PortfolioStorage
from app.tasks.workflow_tasks_helpers import (
    ConsensusResult,
    _build_trade_summary,
    _commit_workflow_to_git,
    _setup_agent_tools,
)
from app.tasks.workflow_tasks_trade_agents import _run_agent_consensus
from app.tasks.workflow_tasks_trade_backtest import (
    _apply_backtest_gating,
    _prepare_backtest,
)

# Re-export for backward compatibility
__all__ = ["ConsensusResult", "paper_trade_validation_workflow"]

logger = get_logger(__name__)


def _execute_paper_trade(
    storage: PortfolioStorage,
    workflow_id: str,
    symbol: str,
    action: str,
    thesis: str,
) -> object | None:
    """Create the paper trade and return trade_id, or None on failure."""
    tools = _setup_agent_tools(storage)
    trade_result = tools.execute_create_paper_trade(
        agent_run_id=workflow_id, symbol=symbol, action=action, thesis=thesis,
    )
    if trade_result.get("status") == "created":
        trade_id = trade_result.get("trade_id")
        logger.info(f"Created paper trade {trade_id} for {symbol} {action}")
        return trade_id
    logger.error(f"Failed to create paper trade: {trade_result}")
    return None


def _record_trade_completion(
    orchestrator: WorkflowOrchestrator,
    workflow_id: str,
    symbol: str,
    action: str,
    trade_id: object | None,
    consensus: ConsensusResult,
    backtest_metrics: dict[str, object] | None,
) -> None:
    """Record workflow completion in the orchestrator."""
    orchestrator.complete_workflow(
        workflow_id,
        result={
            "symbol": symbol, "action": action, "approved": consensus.approved,
            "agents_disagree": consensus.agents_disagree,
            "trade_id": str(trade_id) if trade_id else None,
            "strategy_approved": consensus.strategy_approved,
            "strategy_confidence": consensus.strategy_confidence,
            "strategy_reasoning": consensus.strategy_reasoning,
            "risk_approved": consensus.risk_approved,
            "risk_confidence": consensus.risk_confidence,
            "risk_reasoning": consensus.risk_reasoning,
            "weighted_score": round(consensus.weighted_score, 2),
            "backtest_metrics": backtest_metrics,
        },
    )
    logger.info(f"Paper trade validation workflow {workflow_id} completed: {'APPROVED' if consensus.approved else 'REJECTED'}")


def _commit_trade_result(
    workflow_id: str,
    symbol: str,
    action: str,
    thesis: str,
    trade_id: object | None,
    consensus: ConsensusResult,
    backtest_result: dict[str, object] | None,
    backtest_metrics: dict[str, object] | None,
) -> None:
    """Commit trade validation results to git."""
    trade_summary = _build_trade_summary(symbol, action, consensus.approved, backtest_metrics, trade_id)
    _commit_workflow_to_git(
        workflow_type="paper_trade_validation",
        workflow_id=workflow_id,
        date=datetime.now(UTC),
        result_summary=trade_summary,
        snapshot_data={
            "workflow_id": workflow_id, "symbol": symbol, "action": action, "thesis": thesis,
            "approved": consensus.approved,
            "trade_id": str(trade_id) if trade_id else None,
            "backtest_run_id": str(backtest_result.get("backtest_run_id")) if backtest_result else None,
            "backtest_metrics": backtest_metrics,
            "strategy_decision": "APPROVE" if consensus.strategy_approved else "REJECT",
            "strategy_reasoning": consensus.strategy_reasoning,
            "risk_decision": "APPROVE" if consensus.risk_approved else "REJECT",
            "risk_reasoning": consensus.risk_reasoning,
        },
    )


def _finalize_trade_workflow(
    orchestrator: WorkflowOrchestrator,
    storage: PortfolioStorage,
    workflow_id: str,
    symbol: str,
    action: str,
    thesis: str,
    consensus: ConsensusResult,
    backtest_result: dict[str, object] | None,
    backtest_metrics: dict[str, object] | None,
) -> dict[str, object]:
    """Execute trade (if approved), complete workflow, commit to git, return result."""
    trade_id = (
        _execute_paper_trade(storage, workflow_id, symbol, action, thesis)
        if consensus.approved
        else None
    )
    _record_trade_completion(orchestrator, workflow_id, symbol, action, trade_id, consensus, backtest_metrics)
    _commit_trade_result(workflow_id, symbol, action, thesis, trade_id, consensus, backtest_result, backtest_metrics)
    return {
        "status": "completed", "workflow_id": workflow_id, "approved": consensus.approved,
        "trade_id": trade_id, "strategy_approved": consensus.strategy_approved,
        "risk_approved": consensus.risk_approved, "backtest_metrics": backtest_metrics,
    }


def _start_trade_workflow(
    orchestrator: WorkflowOrchestrator,
    strategy_id: str,
    symbol: str,
    action: str,
    thesis: str,
) -> tuple[str, str] | dict[str, object]:
    """Start the paper trade validation workflow.

    Returns (workflow_id, log_msg) on success, or an early-exit result dict.
    """
    workflow_result = orchestrator.start_workflow(
        workflow_type="paper_trade_validation",
        config={"strategy_id": strategy_id, "symbol": symbol, "action": action,
                "thesis": thesis, "timestamp": datetime.now(UTC).isoformat()},
        agents_involved=["strategy_analyzer", "risk_evaluator"],
        triggered_by="agent_paper_trade_request",
        priority=5,
        max_duration_seconds=600,
    )
    if workflow_result.get("status") != "started":
        logger.error(f"Failed to start paper trade validation workflow: {workflow_result}")
        return workflow_result
    workflow_id = str(workflow_result["workflow_id"])
    orchestrator.update_workflow_status(workflow_id, status="running", current_step="backtest_validation")
    logger.info(f"Paper trade validation workflow {workflow_id} started for {symbol} ({action})")
    return workflow_id, f"{symbol} ({action})"


def paper_trade_validation_workflow(
    strategy_id: str, symbol: str, action: str, thesis: str
) -> dict[str, object]:
    """Multi-agent paper trade validation workflow.

    Workflow:
    1. Strategy agent validates trade using 1-year backtest
    2. Risk agent evaluates backtest metrics
    3. Consensus: Both agents must approve (APPROVE/REJECT)
    4. Execute paper trade if approved

    Returns:
        Workflow result dictionary
    """
    try:
        storage = PortfolioStorage()
        orchestrator = WorkflowOrchestrator(storage)
        client = DualProviderClient()

        start_result = _start_trade_workflow(orchestrator, strategy_id, symbol, action, thesis)
        if isinstance(start_result, dict):
            return start_result
        workflow_id = start_result[0]

        backtest_prep = _prepare_backtest(storage, orchestrator, workflow_id, symbol)
        if isinstance(backtest_prep, dict):
            return backtest_prep
        start_date, end_date, backtest_result, backtest_metrics = backtest_prep

        gating_exit = _apply_backtest_gating(orchestrator, workflow_id, symbol, action, backtest_metrics)
        if gating_exit is not None:
            return gating_exit

        consensus = _run_agent_consensus(
            client, orchestrator, workflow_id, symbol, action, thesis,
            start_date, end_date, backtest_metrics,
        )
        if consensus is None:
            return {"status": "failed", "workflow_id": workflow_id, "error": "One or both agents failed"}

        return _finalize_trade_workflow(
            orchestrator, storage, workflow_id, symbol, action, thesis,
            consensus, backtest_result, backtest_metrics,
        )

    except Exception as e:
        logger.error(f"Paper trade validation workflow failed: {e}")
        return {"status": "error", "error": str(e)}
