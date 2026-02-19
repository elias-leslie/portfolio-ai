"""Agent consensus logic for paper trade validation."""

from __future__ import annotations

import json

from app.agents.llm_client import DualProviderClient
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.logging_config import get_logger
from app.tasks.triggers import emit_event
from app.tasks.workflow_tasks_helpers import (
    ConsensusResult,
    _compute_weighted_consensus,
    _parse_agent_decision,
)

logger = get_logger(__name__)


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
    """Run both agents and compute consensus.

    Returns ConsensusResult or None on agent failure.
    """
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
