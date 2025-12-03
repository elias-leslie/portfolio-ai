"""Multi-agent workflow Celery tasks for autonomous trading intelligence."""

from __future__ import annotations

import json
import re
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


def _get_available_data_range(storage: PortfolioStorage, ticker: str) -> tuple[str | None, str | None]:
    """Get the available date range for a ticker in day_bars.

    Args:
        storage: Database connection
        ticker: Stock ticker symbol

    Returns:
        (min_date, max_date) as ISO strings, or (None, None) if no data
    """
    query = """
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM day_bars
        WHERE symbol = $1
    """
    result = storage.query(query, [ticker])
    if result.is_empty():
        return None, None

    row = result.to_dicts()[0]
    min_date = row.get("min_date")
    max_date = row.get("max_date")

    if min_date is None or max_date is None:
        return None, None

    return str(min_date), str(max_date)


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
        gemini_error = None
        try:
            gemini_response = client.generate(
                prompt=gemini_prompt,
                system="You are a market intelligence analyst identifying data gaps.",
            )
            gemini_output = gemini_response.content
            logger.info(f"Gemini analysis: {len(gemini_output)} chars")
        except Exception as e:
            gemini_error = f"{type(e).__name__}: {e!s}"
            logger.error(f"Gemini agent failed: {gemini_error}", exc_info=True)

        # Execute Claude agent for validation
        if gemini_output:
            claude_prompt = f"""Review and enhance this gap analysis:

{gemini_output}

Validate gaps, add missed insights, refine priorities, provide final recommendations as JSON."""
        else:
            claude_prompt = gemini_prompt

        claude_output = None
        claude_error = None
        try:
            claude_response = client.generate(
                prompt=claude_prompt,
                system="You are a senior market analyst validating gap analysis.",
            )
            claude_output = claude_response.content
            logger.info(f"Claude analysis: {len(claude_output)} chars")
        except Exception as e:
            claude_error = f"{type(e).__name__}: {e!s}"
            logger.error(f"Claude agent failed: {claude_error}", exc_info=True)

        # Generate final analysis
        if not gemini_output and not claude_output:
            error_details = (
                f"Gemini: {gemini_error or 'unknown'}, Claude: {claude_error or 'unknown'}"
            )
            orchestrator.update_workflow_status(
                workflow_id,
                status="failed",
                current_step="both_agents_failed",
                error=f"Both agents failed - {error_details}",
            )
            return {
                "status": "failed",
                "workflow_id": workflow_id,
                "error": error_details,
            }

        final_analysis = claude_output if claude_output else gemini_output

        # Complete workflow with result
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
def paper_trade_validation_workflow(  # noqa: PLR0911
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

        # Calculate backtest date range based on available data
        today = datetime.now(UTC).date()
        requested_start = today - timedelta(days=365)  # Target 1-year backtest
        end_date = today.isoformat()

        # Check available data range
        data_min, _data_max = _get_available_data_range(storage, ticker)
        if data_min is None:
            logger.warning(f"No historical data for {ticker}, triggering backfill")
            # Trigger historical data fetch
            from app.tasks.ingestion.price_ingestion import ingest_historical_ohlcv  # noqa: PLC0415

            ingest_historical_ohlcv.delay([ticker], days=1300)  # ~5 years
            return {
                "status": "pending_data",
                "message": f"Triggered historical data fetch for {ticker}. Retry in 5 minutes.",
                "workflow_id": workflow_id,
            }

        # Adjust start_date to available data if needed
        from datetime import date as date_type  # noqa: PLC0415

        data_min_date = date_type.fromisoformat(data_min)
        if requested_start < data_min_date:
            logger.info(
                f"Adjusting backtest start from {requested_start} to {data_min_date} "
                f"(data only available from {data_min})"
            )
            start_date = data_min
        else:
            start_date = requested_start.isoformat()

        # Execute REAL backtest using AgentTools
        # Check for custom strategy (NEW: Task 4.7)
        from app.strategies.storage import get_strategy_storage  # noqa: PLC0415

        backtest_result: dict[str, object] | None = None
        backtest_metrics: dict[str, object] | None = None
        try:
            strategy_storage = get_strategy_storage()
            custom_strategy = strategy_storage.get_active_strategy(ticker)

            # Determine backtest parameters (custom or default)
            if custom_strategy:
                # Use dynamic strategy parameters
                params = custom_strategy.parameters
                strategy_name = f"{custom_strategy.name}_v{custom_strategy.version}"
                min_signal_strength = params.get("min_confirmations", 7)
                max_holding_days = params.get("max_holding_days", 60)
                position_sizing_method = params.get("position_sizing_method", "fixed_dollars")
                position_size_value = float(params.get("position_size_value", 10000.0))
                logger.info(
                    f"Using custom strategy: {strategy_name}",
                    strategy_id=custom_strategy.id,
                    strategy_type=custom_strategy.strategy_type,
                )
            else:
                # Fall back to default SignalStrategy parameters
                strategy_name = "signal_classifier"
                min_signal_strength = 7
                max_holding_days = 60
                position_sizing_method = "fixed_dollars"
                position_size_value = 10000.0
                logger.info(f"Using default SignalStrategy (no custom strategy found for {ticker})")

            # Initialize tools to execute backtest
            portfolio_mgr = PortfolioManager(storage)
            tools = AgentTools(
                storage=storage,
                news_service=NewsService(storage),
                fred_source=FREDSource(api_key=None),
                price_fetcher=PriceDataFetcher(storage),
                portfolio_mgr=portfolio_mgr,
                analytics=PortfolioAnalytics(),
            )

            logger.info(f"Executing 1-year backtest for {ticker} ({start_date} to {end_date})")

            # Execute backtest tool directly
            backtest_result = tools.execute_run_backtest(
                agent_run_id=workflow_id,
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                strategy=strategy_name,
                min_signal_strength=min_signal_strength,
                max_holding_days=max_holding_days,
                position_sizing_method=position_sizing_method,
                position_size_value=position_size_value,
            )

            if backtest_result.get("status") == "completed":
                # Metrics are at top level, not in a "metrics" dict
                backtest_metrics = {
                    "sharpe_ratio": backtest_result.get("sharpe_ratio", 0.0),
                    "win_rate": backtest_result.get("win_rate", 0.0),
                    "max_drawdown_pct": backtest_result.get("max_drawdown_pct", 0.0),
                    "total_return_pct": backtest_result.get("total_return_pct", 0.0),
                    "num_trades": backtest_result.get("num_trades", 0),
                }
                logger.info(f"Backtest complete: {backtest_metrics}")

                # B3: Hard gating - reject if metrics fail thresholds (VISION.md compliance)
                sharpe_val = backtest_metrics["sharpe_ratio"]
                win_rate_val = backtest_metrics["win_rate"]
                max_dd_val = backtest_metrics["max_drawdown_pct"]
                sharpe = float(str(sharpe_val)) if sharpe_val is not None else 0.0
                win_rate = float(str(win_rate_val)) if win_rate_val is not None else 0.0
                max_dd = float(str(max_dd_val)) if max_dd_val is not None else 0.0

                gating_failures = []
                if sharpe < 1.0:
                    gating_failures.append(f"Sharpe ratio {sharpe:.2f} < 1.0")
                if win_rate < 50.0:
                    gating_failures.append(f"Win rate {win_rate:.1f}% < 50%")
                if max_dd > 20.0:
                    gating_failures.append(f"Max drawdown {max_dd:.1f}% > 20%")

                if gating_failures:
                    gating_reason = "; ".join(gating_failures)
                    logger.warning(f"Backtest gating FAILED for {ticker}: {gating_reason}")
                    orchestrator.complete_workflow(
                        workflow_id,
                        result={
                            "ticker": ticker,
                            "action": action,
                            "approved": False,
                            "trade_id": None,
                            "gating_failed": True,
                            "gating_reason": gating_reason,
                            "backtest_metrics": backtest_metrics,
                        },
                    )
                    return {
                        "status": "completed",
                        "workflow_id": workflow_id,
                        "approved": False,
                        "gating_failed": True,
                        "gating_reason": gating_reason,
                        "backtest_metrics": backtest_metrics,
                    }
            else:
                error_msg_obj = backtest_result.get("error", "Unknown backtest error")
                error_msg = str(error_msg_obj)
                logger.error(f"Backtest failed: {error_msg}")
                orchestrator.update_workflow_status(
                    workflow_id, status="failed", current_step="backtest_failed", error=error_msg
                )
                return {
                    "status": "failed",
                    "workflow_id": workflow_id,
                    "error": f"Backtest execution failed: {error_msg}",
                }

        except Exception as e:
            logger.error(f"Backtest execution error: {e}")
            orchestrator.update_workflow_status(
                workflow_id, status="failed", current_step="backtest_error", error=str(e)
            )
            return {
                "status": "failed",
                "workflow_id": workflow_id,
                "error": f"Backtest execution exception: {e}",
            }

        # Strategy Agent: Analyze REAL backtest results
        strategy_prompt = f"""Validate {ticker} {action.upper()} trade using 1-year backtest results.

Thesis: {thesis}

Backtest Results ({start_date} to {end_date}):
{json.dumps(backtest_metrics, indent=2)}

Task:
1. Analyze the backtest metrics above
2. Make APPROVE/REJECT decision based on:
   - Sharpe ratio > 1.0 (good risk-adjusted returns)
   - Win rate > 50% (more wins than losses)
   - Max drawdown < 20% (reasonable risk)
3. Rate your confidence in the decision (0-100%)
4. Explain reasoning based on ACTUAL metrics (not hypothetical)

Respond with JSON: {{"decision": "APPROVE|REJECT", "confidence": <0-100>, "reasoning": "..."}}"""

        strategy_output = None
        try:
            strategy_response = client.generate(
                prompt=strategy_prompt,
                system="You are a quantitative strategy analyst validating trades using real backtest data.",
            )
            strategy_output = strategy_response.content
            logger.info(f"Strategy agent analysis: {len(strategy_output)} chars")

        except Exception as e:
            logger.error(f"Strategy agent failed: {e}")

        # Risk Agent: Independent evaluation of REAL backtest metrics
        risk_prompt = f"""Independent risk evaluation for {ticker} {action.upper()} trade.

Thesis: {thesis}

Backtest Results ({start_date} to {end_date}):
{json.dumps(backtest_metrics, indent=2)}

Strategy Agent Decision:
{strategy_output}

Task:
1. Make INDEPENDENT risk assessment (don't just agree with strategy agent)
2. Validate metrics meet risk thresholds:
   - Sharpe ratio > 1.0 (risk-adjusted returns acceptable)
   - Win rate > 50% (more wins than losses)
   - Max drawdown < 20% (risk level acceptable)
3. Consider if thesis is supported by backtest performance
4. Rate your confidence in the decision (0-100%)
5. Make your own APPROVE/REJECT decision

Respond with JSON: {{"decision": "APPROVE|REJECT", "confidence": <0-100>, "reasoning": "..."}}"""

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

        # Parse decisions (handle markdown code blocks from LLM)
        def extract_json(text: str) -> str:
            """Extract JSON from potential markdown code blocks."""
            # Try to find JSON in markdown code block
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            if match:
                return match.group(1).strip()
            return text.strip()

        strategy_approved = False
        risk_approved = False
        strategy_reasoning = "Unknown"
        risk_reasoning = "Unknown"
        strategy_confidence = 50  # Default confidence
        risk_confidence = 50

        try:
            strategy_json = extract_json(strategy_output)
            strategy_data = json.loads(strategy_json)
            strategy_approved = strategy_data.get("decision") == "APPROVE"
            strategy_reasoning = strategy_data.get("reasoning", "Unknown")
            strategy_confidence = int(strategy_data.get("confidence", 50))
        except Exception as e:
            logger.warning(f"Failed to parse strategy agent response: {e}")

        try:
            risk_json = extract_json(risk_output)
            risk_data = json.loads(risk_json)
            risk_approved = risk_data.get("decision") == "APPROVE"
            risk_reasoning = risk_data.get("reasoning", "Unknown")
            risk_confidence = int(risk_data.get("confidence", 50))
        except Exception as e:
            logger.warning(f"Failed to parse risk agent response: {e}")

        # A2: Confidence-weighted consensus (VISION.md compliance)
        # Convert decisions to scores: APPROVE=1, REJECT=0
        strategy_score = 1 if strategy_approved else 0
        risk_score = 1 if risk_approved else 0

        # Weighted average: each agent's vote weighted by confidence
        total_weight = strategy_confidence + risk_confidence
        if total_weight > 0:
            weighted_score = (
                strategy_score * strategy_confidence + risk_score * risk_confidence
            ) / total_weight
        else:
            weighted_score = 0.0

        # Conservative consensus: require >= 0.5 weighted score AND no hard reject
        # This means both must approve for approval, but confidence matters for logging
        approved = strategy_approved and risk_approved

        # A1: Detect agent disagreement (VISION.md compliance)
        agents_disagree = strategy_approved != risk_approved
        if agents_disagree:
            logger.warning(
                f"AGENT DISAGREEMENT on {ticker} {action}: "
                f"Strategy={strategy_approved} (conf={strategy_confidence}%), "
                f"Risk={risk_approved} (conf={risk_confidence}%). "
                f"Weighted score: {weighted_score:.2f}. "
                f"Strategy: {strategy_reasoning[:100]}... | Risk: {risk_reasoning[:100]}..."
            )

        logger.info(
            f"Trade validation: {ticker} {action} - "
            f"Strategy: {'APPROVE' if strategy_approved else 'REJECT'}, "
            f"Risk: {'APPROVE' if risk_approved else 'REJECT'} = "
            f"{'APPROVED' if approved else 'REJECTED'}"
            f"{' (DISAGREEMENT)' if agents_disagree else ''}"
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

        # Complete workflow with result (required by DB constraint)
        orchestrator.complete_workflow(
            workflow_id,
            result={
                "ticker": ticker,
                "action": action,
                "approved": approved,
                "agents_disagree": agents_disagree,  # A1: Track disagreements
                "trade_id": str(trade_id) if trade_id else None,
                "strategy_approved": strategy_approved,
                "strategy_confidence": strategy_confidence,  # A2
                "strategy_reasoning": strategy_reasoning,
                "risk_approved": risk_approved,
                "risk_confidence": risk_confidence,  # A2
                "risk_reasoning": risk_reasoning,
                "weighted_score": round(weighted_score, 2),  # A2
                "backtest_metrics": backtest_metrics,
            },
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
                sharpe_raw = backtest_metrics.get("sharpe_ratio", 0)
                win_rate_raw = backtest_metrics.get("win_rate", 0)
                sharpe_f = float(str(sharpe_raw)) if sharpe_raw is not None else 0.0
                win_rate_f = float(str(win_rate_raw)) if win_rate_raw is not None else 0.0
                trade_summary += f" (Sharpe {sharpe_f:.1f}, win rate {win_rate_f:.0f}%)"

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
                    "backtest_run_id": str(backtest_result.get("backtest_run_id"))
                    if backtest_result
                    else None,
                    "backtest_metrics": backtest_metrics,
                    "strategy_decision": "APPROVE" if strategy_approved else "REJECT",
                    "strategy_reasoning": strategy_reasoning,
                    "risk_decision": "APPROVE" if risk_approved else "REJECT",
                    "risk_reasoning": risk_reasoning,
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
