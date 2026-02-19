"""Daily gap analysis workflow logic."""

from __future__ import annotations

from datetime import UTC, datetime

from app.agents.llm_client import DualProviderClient
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.logging_config import get_logger
from app.storage.facade import PortfolioStorage
from app.tasks.workflow_tasks_helpers import (
    _build_gap_analysis_summary,
    _commit_workflow_to_git,
    _execute_agent_with_error_handling,
)

logger = get_logger(__name__)


def _build_gemini_gap_prompt(date_str: str) -> str:
    """Build the Gemini gap analysis prompt."""
    return f"""Analyze market gaps and opportunities for {date_str}.

Identify trading intelligence gaps in current data coverage:
1. Data gaps: What market data or signals are missing?
2. Coverage percentage: Estimate % of needed data currently available
3. Priority gaps: Which gaps would most improve trading edge?
4. Recommendations: What data sources or features to add?

Respond with structured JSON."""


def _build_claude_gap_prompt(gemini_output: str | None, fallback_prompt: str) -> str:
    """Build the Claude validation prompt from Gemini output or fallback."""
    if not gemini_output:
        return fallback_prompt
    return f"""Review and enhance this gap analysis:

{gemini_output}

Validate gaps, add missed insights, refine priorities, provide final recommendations as JSON."""


def _run_gap_agents(
    client: DualProviderClient, date_str: str
) -> tuple[str | None, str | None, str | None, str | None]:
    """Run both agents for gap analysis.

    Returns:
        (gemini_output, gemini_error, claude_output, claude_error)
    """
    gemini_prompt = _build_gemini_gap_prompt(date_str)
    gemini_output, gemini_error = _execute_agent_with_error_handling(
        client=client,
        prompt=gemini_prompt,
        system="You are a market intelligence analyst identifying data gaps.",
        agent_name="Gemini",
    )
    claude_prompt = _build_claude_gap_prompt(gemini_output, gemini_prompt)
    claude_output, claude_error = _execute_agent_with_error_handling(
        client=client,
        prompt=claude_prompt,
        system="You are a senior market analyst validating gap analysis.",
        agent_name="Claude",
    )
    return gemini_output, gemini_error, claude_output, claude_error


def _commit_gap_analysis(
    workflow_id: str,
    final_analysis: str | None,
    gemini_output: str | None,
    claude_output: str | None,
) -> None:
    """Commit gap analysis results to git (non-blocking)."""
    try:
        summary = _build_gap_analysis_summary(final_analysis or "")
        _commit_workflow_to_git(
            workflow_type="daily_gap_analysis",
            workflow_id=workflow_id,
            date=datetime.now(UTC),
            result_summary=summary,
            snapshot_data={
                "workflow_id": workflow_id,
                "analysis": final_analysis,
                "agents_used": [
                    "gemini" if gemini_output else None,
                    "claude" if claude_output else None,
                ],
            },
        )
    except Exception:
        pass  # Errors already logged in helper


def _handle_gap_agent_failure(
    orchestrator: WorkflowOrchestrator,
    workflow_id: str,
    gemini_error: str | None,
    claude_error: str | None,
) -> dict[str, object]:
    """Mark workflow as failed when both agents fail and return result dict."""
    error_details = f"Gemini: {gemini_error or 'unknown'}, Claude: {claude_error or 'unknown'}"
    orchestrator.update_workflow_status(
        workflow_id,
        status="failed",
        current_step="both_agents_failed",
        error=f"Both agents failed - {error_details}",
    )
    return {"status": "failed", "workflow_id": workflow_id, "error": error_details}


def _complete_gap_workflow(
    orchestrator: WorkflowOrchestrator,
    workflow_id: str,
    gemini_output: str | None,
    claude_output: str | None,
) -> str | None:
    """Complete workflow in orchestrator and return the final analysis string."""
    final_analysis = claude_output if claude_output else gemini_output
    orchestrator.complete_workflow(
        workflow_id,
        result={
            "analysis": final_analysis,
            "gemini_output": gemini_output,
            "claude_output": claude_output,
            "agents_used": [
                "gemini" if gemini_output else None,
                "claude" if claude_output else None,
            ],
        },
    )
    logger.info(f"Daily gap analysis workflow {workflow_id} completed")
    return final_analysis


def _start_gap_workflow(
    orchestrator: WorkflowOrchestrator, date_str: str
) -> dict[str, object]:
    """Start the gap analysis workflow and return orchestrator result."""
    return orchestrator.start_workflow(
        workflow_type="daily_gap_analysis",
        config={"date": date_str, "analysis_depth": "comprehensive"},
        agents_involved=["gemini", "claude"],
        triggered_by="hatchet_scheduled",
        priority=3,
        max_duration_seconds=1800,
    )


def daily_gap_analysis_workflow() -> dict[str, object]:
    """Daily multi-agent gap analysis workflow.

    Workflow:
    1. Gemini agent analyzes current market gaps
    2. Claude agent validates and enhances analysis
    3. Generate final report and commit to git

    Returns:
        Workflow result dictionary
    """
    try:
        storage = PortfolioStorage()
        orchestrator = WorkflowOrchestrator(storage)
        date_str = datetime.now(UTC).date().isoformat()

        workflow_result = _start_gap_workflow(orchestrator, date_str)
        if workflow_result.get("status") != "started":
            logger.error(f"Failed to start gap analysis workflow: {workflow_result}")
            return workflow_result

        workflow_id = str(workflow_result["workflow_id"])
        orchestrator.update_workflow_status(
            workflow_id, status="running", current_step="agent_analysis"
        )
        logger.info(f"Daily gap analysis workflow {workflow_id} started")

        client = DualProviderClient(primary="gemini")
        gemini_output, gemini_error, claude_output, claude_error = _run_gap_agents(
            client, date_str
        )

        if not gemini_output and not claude_output:
            return _handle_gap_agent_failure(orchestrator, workflow_id, gemini_error, claude_error)

        final_analysis = _complete_gap_workflow(orchestrator, workflow_id, gemini_output, claude_output)
        _commit_gap_analysis(workflow_id, final_analysis, gemini_output, claude_output)

        return {"status": "completed", "workflow_id": workflow_id, "result": final_analysis}

    except Exception as e:
        logger.error(f"Daily gap analysis workflow failed: {e}")
        return {"status": "error", "error": str(e)}
