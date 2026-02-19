"""Paper trade validation workflow logic."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from datetime import date as date_type

from app.agents.llm_client import DualProviderClient
from app.agents.tools import AgentTools
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.logging_config import get_logger
from app.storage.facade import PortfolioStorage
from app.tasks.triggers import emit_event
from app.tasks.workflow_tasks_helpers import (
    _build_trade_summary,
    _check_backtest_gating,
    _commit_workflow_to_git,
    _compute_weighted_consensus,
    _get_available_data_range,
    _parse_agent_decision,
    _resolve_strategy_params,
    _setup_agent_tools,
)

logger = get_logger(__name__)


@dataclass
class ConsensusResult:
    """Holds consensus data from both agents."""

    strategy_approved: bool
    strategy_confidence: int
    strategy_reasoning: str
    risk_approved: bool
    risk_confidence: int
    risk_reasoning: str
    approved: bool
    agents_disagree: bool
    weighted_score: float


def _resolve_backtest_date_range(
    storage: PortfolioStorage,
    symbol: str,
    workflow_id: str,
) -> tuple[str, str] | dict[str, object]:
    """Compute start/end dates for backtest, triggering backfill if needed.

    Returns either (start_date, end_date) strings or an early-exit result dict.
    """
    today = datetime.now(UTC).date()
    end_date = today.isoformat()
    requested_start = today - timedelta(days=365)

    data_min, _data_max = _get_available_data_range(storage, symbol)
    if data_min is None:
        logger.warning(f"No historical data for {symbol}, triggering backfill")
        from app.tasks.ingestion.price_ingestion import ingest_historical_ohlcv

        ingest_historical_ohlcv([symbol], days=1300)
        return {
            "status": "pending_data",
            "message": f"Triggered historical data fetch for {symbol}. Retry in 5 minutes.",
            "workflow_id": workflow_id,
        }

    data_min_date = date_type.fromisoformat(data_min)
    if requested_start < data_min_date:
        logger.info(f"Adjusting backtest start to {data_min_date} (data only available from {data_min})")
        return data_min, end_date
    return requested_start.isoformat(), end_date


def _run_backtest(
    tools: AgentTools,
    workflow_id: str,
    orchestrator: WorkflowOrchestrator,
    symbol: str,
    start_date: str,
    end_date: str,
    strategy_name: str,
    min_signal_strength: int,
    max_holding_days: int,
    position_sizing_method: str,
    position_size_value: float,
) -> tuple[dict[str, object] | None, dict[str, object] | None, dict[str, object] | None]:
    """Execute backtest and return (backtest_result, metrics, early_exit_result).

    If early_exit_result is not None, the caller should return it immediately.
    """
    logger.info(f"Executing 1-year backtest for {symbol} ({start_date} to {end_date})")
    backtest_result = tools.execute_run_backtest(
        agent_run_id=workflow_id,
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        strategy=strategy_name,
        min_signal_strength=min_signal_strength,
        max_holding_days=max_holding_days,
        position_sizing_method=position_sizing_method,
        position_size_value=position_size_value,
    )

    if backtest_result.get("status") != "completed":
        error_msg = str(backtest_result.get("error", "Unknown backtest error"))
        logger.error(f"Backtest failed: {error_msg}")
        orchestrator.update_workflow_status(
            workflow_id, status="failed", current_step="backtest_failed", error=error_msg
        )
        return None, None, {
            "status": "failed",
            "workflow_id": workflow_id,
            "error": f"Backtest execution failed: {error_msg}",
        }

    metrics: dict[str, object] = {
        "sharpe_ratio": backtest_result.get("sharpe_ratio", 0.0),
        "win_rate": backtest_result.get("win_rate", 0.0),
        "max_drawdown_pct": backtest_result.get("max_drawdown_pct", 0.0),
        "total_return_pct": backtest_result.get("total_return_pct", 0.0),
        "num_trades": backtest_result.get("num_trades", 0),
    }
    logger.info(f"Backtest complete: {metrics}")
    return backtest_result, metrics, None


def _apply_backtest_gating(
    orchestrator: WorkflowOrchestrator,
    workflow_id: str,
    symbol: str,
    action: str,
    backtest_metrics: dict[str, object],
) -> dict[str, object] | None:
    """Apply hard gating thresholds to backtest metrics.

    Returns an early-exit result dict if gating fails, else None.
    """
    gating_failures = _check_backtest_gating(backtest_metrics)
    if not gating_failures:
        return None

    gating_reason = "; ".join(gating_failures)
    logger.warning(f"Backtest gating FAILED for {symbol}: {gating_reason}")
    orchestrator.complete_workflow(
        workflow_id,
        result={
            "symbol": symbol, "action": action, "approved": False, "trade_id": None,
            "gating_failed": True, "gating_reason": gating_reason,
            "backtest_metrics": backtest_metrics,
        },
    )
    return {
        "status": "completed", "workflow_id": workflow_id, "approved": False,
        "gating_failed": True, "gating_reason": gating_reason,
        "backtest_metrics": backtest_metrics,
    }


def _run_strategy_agent(
    client: DualProviderClient,
    symbol: str,
    action: str,
    thesis: str,
    start_date: str,
    end_date: str,
    backtest_metrics: dict[str, object],
    workflow_id: str,
) -> str | None:
    """Run the strategy agent and emit an insight event on success."""
    prompt = (
        f"Validate {symbol} {action.upper()} trade using 1-year backtest results.\n\n"
        f"Thesis: {thesis}\n\nBacktest Results ({start_date} to {end_date}):\n"
        f"{json.dumps(backtest_metrics, indent=2)}\n\n"
        "Task:\n1. Analyze the backtest metrics above\n"
        "2. Make APPROVE/REJECT decision based on:\n"
        "   - Sharpe ratio > 1.0, Win rate > 50%, Max drawdown < 20%\n"
        "3. Rate your confidence in the decision (0-100%)\n"
        "4. Explain reasoning based on ACTUAL metrics\n\n"
        'Respond with JSON: {"decision": "APPROVE|REJECT", "confidence": <0-100>, "reasoning": "..."}'
    )
    try:
        response = client.generate(
            prompt=prompt,
            system="You are a quantitative strategy analyst validating trades using real backtest data.",
            purpose="strategy_validation",
        )
        output = response.content
        logger.info(f"Strategy agent analysis: {len(output)} chars")
        if output and len(output) > 50:
            emit_event(
                "insight_generated",
                {"output": output, "context_type": "strategy_validation",
                 "symbol": symbol, "confidence": 0.75},
            )
        return output
    except Exception as e:
        logger.error(f"Strategy agent failed: {e}")
        return None


def _run_risk_agent(
    client: DualProviderClient,
    symbol: str,
    action: str,
    thesis: str,
    start_date: str,
    end_date: str,
    backtest_metrics: dict[str, object],
    strategy_output: str | None,
) -> str | None:
    """Run the risk evaluation agent."""
    prompt = (
        f"Independent risk evaluation for {symbol} {action.upper()} trade.\n\n"
        f"Thesis: {thesis}\n\nBacktest Results ({start_date} to {end_date}):\n"
        f"{json.dumps(backtest_metrics, indent=2)}\n\n"
        f"Strategy Agent Decision:\n{strategy_output}\n\n"
        "Task:\n1. Make INDEPENDENT risk assessment\n"
        "2. Validate metrics: Sharpe > 1.0, Win rate > 50%, Max drawdown < 20%\n"
        "3. Consider if thesis is supported by backtest performance\n"
        "4. Rate your confidence (0-100%) and make APPROVE/REJECT decision\n\n"
        'Respond with JSON: {"decision": "APPROVE|REJECT", "confidence": <0-100>, "reasoning": "..."}'
    )
    try:
        response = client.generate(
            prompt=prompt,
            system="You are a risk management analyst evaluating trade proposals.",
            purpose="risk_evaluation",
        )
        output = response.content
        logger.info(f"Risk agent analysis: {len(output)} chars")
        return output
    except Exception as e:
        logger.error(f"Risk agent failed: {e}")
        return None


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


def _run_agent_consensus(
    client: DualProviderClient,
    orchestrator: WorkflowOrchestrator,
    workflow_id: str,
    symbol: str,
    action: str,
    thesis: str,
    start_date: str,
    end_date: str,
    backtest_metrics: dict[str, object],
) -> ConsensusResult | None:
    """Run both agents and compute consensus. Returns ConsensusResult or None on agent failure."""
    strategy_output = _run_strategy_agent(
        client, symbol, action, thesis, start_date, end_date, backtest_metrics, workflow_id
    )
    risk_output = _run_risk_agent(
        client, symbol, action, thesis, start_date, end_date, backtest_metrics, strategy_output
    )

    if not strategy_output or not risk_output:
        error_msg = "One or both agents failed"
        orchestrator.update_workflow_status(
            workflow_id, status="failed", current_step="agent_failure", error=error_msg
        )
        return None

    s_approved, s_reasoning, s_conf = _parse_agent_decision(strategy_output, "strategy")
    r_approved, r_reasoning, r_conf = _parse_agent_decision(risk_output, "risk")
    approved, agents_disagree, weighted_score = _compute_weighted_consensus(s_approved, s_conf, r_approved, r_conf)

    _log_consensus(symbol, action, s_approved, s_conf, r_approved, r_conf,
                   agents_disagree, weighted_score, approved, s_reasoning, r_reasoning)

    return ConsensusResult(
        strategy_approved=s_approved, strategy_confidence=s_conf, strategy_reasoning=s_reasoning,
        risk_approved=r_approved, risk_confidence=r_conf, risk_reasoning=r_reasoning,
        approved=approved, agents_disagree=agents_disagree, weighted_score=weighted_score,
    )


def _log_consensus(
    symbol: str,
    action: str,
    s_approved: bool,
    s_conf: int,
    r_approved: bool,
    r_conf: int,
    agents_disagree: bool,
    weighted_score: float,
    approved: bool,
    s_reasoning: str,
    r_reasoning: str,
) -> None:
    """Log consensus decision details."""
    if agents_disagree:
        logger.warning(
            f"AGENT DISAGREEMENT on {symbol} {action}: "
            f"Strategy={s_approved} (conf={s_conf}%), Risk={r_approved} (conf={r_conf}%). "
            f"Weighted score: {weighted_score:.2f}. "
            f"Strategy: {s_reasoning[:100]}... | Risk: {r_reasoning[:100]}..."
        )
    logger.info(
        f"Trade validation: {symbol} {action} - "
        f"Strategy: {'APPROVE' if s_approved else 'REJECT'}, "
        f"Risk: {'APPROVE' if r_approved else 'REJECT'} = "
        f"{'APPROVED' if approved else 'REJECTED'}"
        f"{' (DISAGREEMENT)' if agents_disagree else ''}"
    )


def _prepare_backtest(
    storage: PortfolioStorage,
    orchestrator: WorkflowOrchestrator,
    workflow_id: str,
    symbol: str,
) -> tuple[str, str, dict[str, object] | None, dict[str, object] | None] | dict[str, object]:
    """Resolve date range, strategy params, and run backtest.

    Returns either (start, end, backtest_result, metrics) or an early-exit dict.
    """
    date_range = _resolve_backtest_date_range(storage, symbol, workflow_id)
    if isinstance(date_range, dict):
        return date_range
    start_date, end_date = date_range

    try:
        strategy_name, min_sig, max_hold, sizing_method, size_value = _resolve_strategy_params(
            storage, symbol
        )
    except Exception as e:
        logger.error(f"Backtest execution error: {e}")
        orchestrator.update_workflow_status(
            workflow_id, status="failed", current_step="backtest_error", error=str(e)
        )
        return {"status": "failed", "workflow_id": workflow_id,
                "error": f"Backtest execution exception: {e}"}

    tools = _setup_agent_tools(storage)
    backtest_result, backtest_metrics, early_exit = _run_backtest(
        tools, workflow_id, orchestrator, symbol, start_date, end_date,
        strategy_name, min_sig, max_hold, sizing_method, size_value,
    )
    if early_exit is not None:
        return early_exit

    return start_date, end_date, backtest_result, backtest_metrics


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
