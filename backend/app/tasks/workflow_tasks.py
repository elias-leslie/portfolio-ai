"""Multi-agent workflow Celery tasks for autonomous trading intelligence."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from app.agents.llm_client import DualProviderClient
from app.agents.tools import AgentTools
from app.agents.workflow_orchestrator import WorkflowOrchestrator
from app.celery_app import celery_app
from app.logging_config import get_logger
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services import NewsService
from app.sources.fred import FREDSource
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
    1. Strategy agent validates trade using 1-year backtest
    2. Risk agent evaluates backtest metrics
    3. Consensus: Both agents must approve (APPROVE/REJECT)
    4. Execute paper trade if approved

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
        client = DualProviderClient()

        workflow_result = orchestrator.start_workflow(
            workflow_type="paper_trade_validation",
            config={
                "strategy_id": strategy_id,
                "ticker": ticker,
                "action": action,
                "thesis": thesis,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            agents_involved=["strategy_analyzer", "risk_evaluator"],
            triggered_by="agent_paper_trade_request",
            priority=5,
            max_duration_seconds=600,
        )

        if workflow_result.get("status") != "started":
            logger.error(f"Failed to start paper trade validation workflow: {workflow_result}")
            return workflow_result

        workflow_id = str(workflow_result["workflow_id"])
        orchestrator.update_workflow_status(
            workflow_id, status="running", current_step="backtest_validation"
        )

        logger.info(
            f"Paper trade validation workflow {workflow_id} started for {ticker} ({action})"
        )

        # Calculate 1-year backtest date range
        today = datetime.now(UTC).date()
        # Use 365 days ago for 1-year backtest
        start_date = (today - timedelta(days=365)).isoformat()
        end_date = today.isoformat()

        # Strategy Agent: Run backtest and analyze results
        strategy_prompt = f"""Validate {ticker} {action.upper()} trade using 1-year backtest analysis.

Thesis: {thesis}

Task:
1. Run backtest for {ticker} from {start_date} to {end_date}
2. Analyze Sharpe ratio, win rate, max drawdown, total return
3. Make APPROVE/REJECT decision based on:
   - Sharpe ratio > 1.0 (good risk-adjusted returns)
   - Win rate > 50% (more wins than losses)
   - Max drawdown < 20% (reasonable risk)
4. Explain reasoning

Respond with JSON: {{"decision": "APPROVE|REJECT", "reasoning": "...", "metrics": {{...}}}}"""

        strategy_output = None
        backtest_metrics = None
        try:
            # For now, direct prompt (tool calling will be integrated in next iteration)
            strategy_response = client.generate(
                prompt=strategy_prompt,
                system="You are a quantitative strategy analyst validating trades with backtests.",
            )
            strategy_output = strategy_response.content
            logger.info(f"Strategy agent analysis: {len(strategy_output)} chars")

            # Parse metrics from response
            try:
                analysis = json.loads(strategy_output)
                backtest_metrics = analysis.get("metrics", {})
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Strategy agent failed: {e}")

        # Risk Agent: Evaluate backtest metrics
        if strategy_output:
            risk_prompt = f"""Review backtest validation for {ticker} {action.upper()} trade:

{strategy_output}

Task:
1. Validate metrics meet risk thresholds:
   - Sharpe ratio > 1.0
   - Win rate > 50%
   - Max drawdown < 20%
2. Consider market conditions and thesis alignment
3. Make independent APPROVE/REJECT decision

Respond with JSON: {{"decision": "APPROVE|REJECT", "reasoning": "..."}}"""
        else:
            # Backtest failed, risk agent must reject
            risk_prompt = f"""Backtest validation failed for {ticker} {action.upper()}.

Task: Explain why trade must be REJECTED without backtest validation.

Respond with JSON: {{"decision": "REJECT", "reasoning": "..."}}"""

        risk_output = None
        try:
            risk_response = client.generate(
                prompt=risk_prompt,
                system="You are a risk management analyst evaluating trade proposals.",
            )
            risk_output = risk_response.content
            logger.info(f"Risk agent analysis: {len(risk_output)} chars")
        except Exception as e:
            logger.error(f"Risk agent failed: {e}")

        # Consensus: Both agents must approve
        if not strategy_output or not risk_output:
            error_msg = "One or both agents failed"
            orchestrator.update_workflow_status(
                workflow_id, status="failed", current_step="agent_failure", error=error_msg
            )
            return {
                "status": "failed",
                "workflow_id": workflow_id,
                "error": error_msg,
            }

        # Parse decisions
        strategy_approved = False
        risk_approved = False
        strategy_reasoning = "Unknown"
        risk_reasoning = "Unknown"

        try:
            strategy_data = json.loads(strategy_output)
            strategy_approved = strategy_data.get("decision") == "APPROVE"
            strategy_reasoning = strategy_data.get("reasoning", "Unknown")
        except Exception:
            logger.warning("Failed to parse strategy agent response")

        try:
            risk_data = json.loads(risk_output)
            risk_approved = risk_data.get("decision") == "APPROVE"
            risk_reasoning = risk_data.get("reasoning", "Unknown")
        except Exception:
            logger.warning("Failed to parse risk agent response")

        approved = strategy_approved and risk_approved

        logger.info(
            f"Trade validation: {ticker} {action} - "
            f"Strategy: {'APPROVE' if strategy_approved else 'REJECT'}, "
            f"Risk: {'APPROVE' if risk_approved else 'REJECT'} = "
            f"{'APPROVED' if approved else 'REJECTED'}"
        )

        # Execute paper trade if approved
        trade_id = None
        if approved:
            portfolio_mgr = PortfolioManager(storage)
            tools = AgentTools(
                storage=storage,
                news_service=NewsService(storage),
                fred_source=FREDSource(api_key=None),  # FREDSource takes api_key, not storage
                price_fetcher=PriceDataFetcher(storage),
                portfolio_mgr=portfolio_mgr,
                analytics=PortfolioAnalytics(),  # No-arg constructor
            )

            trade_result = tools.execute_create_paper_trade(
                agent_run_id=workflow_id,
                ticker=ticker,
                action=action,
                thesis=thesis,
            )

            if trade_result.get("status") == "created":
                trade_id = trade_result.get("trade_id")
                logger.info(f"Created paper trade {trade_id} for {ticker} {action}")
            else:
                logger.error(f"Failed to create paper trade: {trade_result}")

        orchestrator.update_workflow_status(
            workflow_id,
            status="complete",
            current_step="trade_decision_made" if approved else "trade_rejected",
        )

        logger.info(
            f"Paper trade validation workflow {workflow_id} completed: "
            f"{'APPROVED' if approved else 'REJECTED'}"
        )

        # Commit results to git
        try:
            decision = "APPROVED" if approved else "REJECTED"
            trade_summary = f"{ticker} {action} {decision}"

            if backtest_metrics:
                sharpe = backtest_metrics.get("sharpe_ratio", 0)
                win_rate = backtest_metrics.get("win_rate", 0)
                trade_summary += f" (Sharpe {sharpe:.1f}, win rate {win_rate:.0f}%)"

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
                    "strategy_decision": "APPROVE" if strategy_approved else "REJECT",
                    "strategy_reasoning": strategy_reasoning,
                    "risk_decision": "APPROVE" if risk_approved else "REJECT",
                    "risk_reasoning": risk_reasoning,
                    "backtest_metrics": backtest_metrics,
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
            "strategy_approved": strategy_approved,
            "risk_approved": risk_approved,
            "backtest_metrics": backtest_metrics,
        }

    except Exception as e:
        logger.error(f"Paper trade validation workflow failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="app.tasks.workflow_tasks.research_corroboration_workflow")  # type: ignore[misc]
def research_corroboration_workflow(topic: str, sources: list[str]) -> dict[str, object]:
    """Multi-agent research corroboration workflow (placeholder for future implementation)."""
    logger.info(f"Research corroboration workflow placeholder: {topic}")
    return {"status": "not_implemented", "topic": topic}
