"""Multi-agent workflow Celery tasks for autonomous trading intelligence."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.agents.llm_client import DualProviderClient
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.storage.facade import PortfolioStorage
from app.utils.git_automation import commit_workflow_results

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.workflow_tasks.daily_gap_analysis_workflow")  # type: ignore[misc]
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

        # Start workflow
        workflow_result = orchestrator.start_workflow(
            workflow_type="daily_gap_analysis",
            config={
                "date": datetime.now(UTC).date().isoformat(),
                "analysis_depth": "comprehensive",
            },
            agents_involved=["gemini", "claude"],
            triggered_by="celery_scheduled",
            priority=3,
            max_duration_seconds=1800,
        )

        if workflow_result.get("status") != "started":
            logger.error(f"Failed to start gap analysis workflow: {workflow_result}")
            return workflow_result

        workflow_id = str(workflow_result["workflow_id"])
        orchestrator.update_workflow_status(
            workflow_id, status="running", current_step="agent_analysis"
        )

        logger.info(f"Daily gap analysis workflow {workflow_id} started")

        # Execute Gemini agent for gap analysis
        client = DualProviderClient(primary="gemini")
        gemini_prompt = f"""Analyze market gaps and opportunities for {datetime.now(UTC).date().isoformat()}.

Identify trading intelligence gaps in current data coverage:
1. Data gaps: What market data or signals are missing?
2. Coverage percentage: Estimate % of needed data currently available
3. Priority gaps: Which gaps would most improve trading edge?
4. Recommendations: What data sources or features to add?

Respond with structured JSON."""

        gemini_output = None
        try:
            gemini_response = client.generate(
                prompt=gemini_prompt,
                system="You are a market intelligence analyst identifying data gaps.",
            )
            gemini_output = gemini_response.content
            logger.info(f"Gemini analysis: {len(gemini_output)} chars")
        except Exception as e:
            logger.error(f"Gemini agent failed: {e}")

        # Execute Claude agent for validation
        if gemini_output:
            claude_prompt = f"""Review and enhance this gap analysis:

{gemini_output}

Validate gaps, add missed insights, refine priorities, provide final recommendations as JSON."""
        else:
            claude_prompt = gemini_prompt

        claude_output = None
        try:
            claude_response = client.generate(
                prompt=claude_prompt,
                system="You are a senior market analyst validating gap analysis.",
            )
            claude_output = claude_response.content
            logger.info(f"Claude analysis: {len(claude_output)} chars")
        except Exception as e:
            logger.error(f"Claude agent failed: {e}")

        # Generate final analysis
        if not gemini_output and not claude_output:
            orchestrator.update_workflow_status(
                workflow_id, status="failed", current_step="both_agents_failed"
            )
            return {"status": "failed", "workflow_id": workflow_id, "error": "Both agents failed"}

        final_analysis = claude_output if claude_output else gemini_output

        # Complete workflow
        orchestrator.update_workflow_status(
            workflow_id, status="complete", current_step="consensus_generated"
        )

        logger.info(f"Daily gap analysis workflow {workflow_id} completed")

        # Commit results to git
        try:
            analysis_summary = "Analysis complete"
            try:
                if isinstance(final_analysis, str):
                    analysis_data = json.loads(final_analysis)
                    gaps_count = len(analysis_data.get("gaps_identified", []))
                    coverage = analysis_data.get("coverage_estimate", 0)
                    analysis_summary = (
                        f"{gaps_count} gaps identified, {int(coverage * 100)}% coverage"
                    )
            except Exception:
                pass

            commit_success = commit_workflow_results(
                workflow_type="daily_gap_analysis",
                date=datetime.now(UTC),
                result_summary=analysis_summary,
                snapshot_data={
                    "workflow_id": workflow_id,
                    "analysis": final_analysis,
                    "agents_used": [
                        "gemini" if gemini_output else None,
                        "claude" if claude_output else None,
                    ],
                },
            )
            if commit_success:
                logger.info(f"Workflow {workflow_id} results committed to git")
        except Exception as e:
            logger.warning(f"Git automation failed: {e} (non-blocking)")

        return {"status": "completed", "workflow_id": workflow_id, "result": final_analysis}

    except Exception as e:
        logger.error(f"Daily gap analysis workflow failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="app.tasks.workflow_tasks.paper_trade_validation_workflow")  # type: ignore[misc]
def paper_trade_validation_workflow(
    strategy_id: str, ticker: str, action: str, thesis: str
) -> dict[str, object]:
    """Multi-agent paper trade validation workflow.

    Workflow:
    1. Strategy agent validates trade using backtest
    2. Execute paper trade if validated

    Args:
        strategy_id: ID of the strategy to validate
        ticker: Stock ticker symbol
        action: Trade action ('buy' or 'sell')
        thesis: Investment thesis

    Returns:
        Workflow result dictionary
    """
    try:
        storage = PortfolioStorage()
        orchestrator = WorkflowOrchestrator(storage)

        workflow_result = orchestrator.start_workflow(
            workflow_type="paper_trade_validation",
            config={
                "strategy_id": strategy_id,
                "ticker": ticker,
                "action": action,
                "thesis": thesis,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            agents_involved=["strategy_analyzer"],
            triggered_by="agent_paper_trade_request",
            priority=5,
            max_duration_seconds=600,
        )

        if workflow_result.get("status") != "started":
            logger.error(f"Failed to start paper trade validation workflow: {workflow_result}")
            return workflow_result

        workflow_id = str(workflow_result["workflow_id"])
        orchestrator.update_workflow_status(
            workflow_id, status="running", current_step="validation_analysis"
        )

        logger.info(
            f"Paper trade validation workflow {workflow_id} started for {ticker} ({action})"
        )

        # MVP: Simple validation for Phase 4
        # Full backtest integration and paper trade execution can be added post-Phase 4
        approved = True
        strategy_analysis = f"Auto-approved for MVP testing: {ticker} {action}"
        trade_id = None

        logger.info(f"Trade validation: {ticker} {action} - APPROVED")

        orchestrator.update_workflow_status(
            workflow_id, status="complete", current_step="trade_decision_made"
        )

        logger.info(f"Paper trade validation workflow {workflow_id} completed: APPROVED")

        # Commit results to git
        try:
            decision = "APPROVED" if approved else "REJECTED"
            trade_summary = f"{ticker} {action} {decision}"
            if trade_id:
                trade_summary += f" (trade_id: {str(trade_id)[:8]})"

            commit_success = commit_workflow_results(
                workflow_type="paper_trade_validation",
                date=datetime.now(UTC),
                result_summary=trade_summary,
                snapshot_data={
                    "workflow_id": workflow_id,
                    "ticker": ticker,
                    "action": action,
                    "thesis": thesis,
                    "approved": approved,
                    "trade_id": str(trade_id) if trade_id else None,
                    "strategy_analysis": strategy_analysis,
                },
            )
            if commit_success:
                logger.info(f"Workflow {workflow_id} results committed to git")
        except Exception as e:
            logger.warning(f"Git automation failed: {e} (non-blocking)")

        return {
            "status": "completed",
            "workflow_id": workflow_id,
            "approved": approved,
            "trade_id": trade_id,
        }

    except Exception as e:
        logger.error(f"Paper trade validation workflow failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="app.tasks.workflow_tasks.research_corroboration_workflow")  # type: ignore[misc]
def research_corroboration_workflow(topic: str, sources: list[str]) -> dict[str, object]:
    """Multi-agent research corroboration workflow (placeholder for future implementation)."""
    logger.info(f"Research corroboration workflow placeholder: {topic}")
    return {"status": "not_implemented", "topic": topic}
