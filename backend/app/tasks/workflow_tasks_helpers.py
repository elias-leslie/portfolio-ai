"""Shared helper functions for workflow tasks."""

from __future__ import annotations

import json
import re
from datetime import datetime

from app.agents.llm_client import DualProviderClient
from app.agents.tools import AgentTools
from app.logging_config import get_logger
from app.portfolio.analytics import PortfolioAnalytics
from app.portfolio.manager import PortfolioManager
from app.portfolio.price_fetcher import PriceDataFetcher
from app.services import NewsService
from app.sources.fred import FREDSource
from app.storage.facade import PortfolioStorage
from app.utils.git_automation import commit_workflow_results

logger = get_logger(__name__)


def _setup_agent_tools(storage: PortfolioStorage) -> AgentTools:
    """Initialize AgentTools with all required dependencies."""
    portfolio_mgr = PortfolioManager(storage)
    return AgentTools(
        storage=storage,
        news_service=NewsService(storage),
        fred_source=FREDSource(api_key=None),
        price_fetcher=PriceDataFetcher(storage),
        portfolio_mgr=portfolio_mgr,
        analytics=PortfolioAnalytics(),
    )


def _execute_agent_with_error_handling(
    client: DualProviderClient,
    prompt: str,
    system: str,
    agent_name: str,
    purpose: str | None = None,
) -> tuple[str | None, str | None]:
    """Execute an agent prompt with standardized error handling.

    Returns:
        Tuple of (output, error) - one will be None
    """
    try:
        response = client.generate(prompt=prompt, system=system, purpose=purpose)
        output = response.content
        logger.info(f"{agent_name} analysis: {len(output)} chars")
        return output, None
    except Exception as e:
        error = f"{type(e).__name__}: {e!s}"
        logger.error(f"{agent_name} agent failed: {error}", exc_info=True)
        return None, error


def _commit_workflow_to_git(
    workflow_type: str,
    workflow_id: str,
    date: datetime,
    result_summary: str,
    snapshot_data: dict[str, object],
) -> bool:
    """Commit workflow results to git with error handling.

    Returns:
        True if commit succeeded, False otherwise
    """
    try:
        commit_success = commit_workflow_results(
            workflow_type=workflow_type,
            date=date,
            result_summary=result_summary,
            snapshot_data=snapshot_data,
        )
        if commit_success:
            logger.info(f"Workflow {workflow_id} results committed to git")
        return commit_success
    except Exception as e:
        logger.warning(f"Git automation failed: {e} (non-blocking)")
        return False


def _get_available_data_range(
    storage: PortfolioStorage, symbol: str
) -> tuple[str | None, str | None]:
    """Get the available date range for a symbol in day_bars.

    Returns:
        (min_date, max_date) as ISO strings, or (None, None) if no data
    """
    query = """
        SELECT MIN(date) as min_date, MAX(date) as max_date
        FROM day_bars
        WHERE symbol = $1
    """
    result = storage.query(query, [symbol])
    if result.is_empty():
        return None, None

    row = result.to_dicts()[0]
    min_date = row.get("min_date")
    max_date = row.get("max_date")

    if min_date is None or max_date is None:
        return None, None

    return str(min_date), str(max_date)


def extract_json(text: str) -> str:
    """Extract JSON from potential markdown code blocks."""
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()


def _build_gap_analysis_summary(final_analysis: str) -> str:
    """Parse gap analysis JSON and build a human-readable summary."""
    try:
        analysis_data = json.loads(final_analysis)
        gaps_count = len(analysis_data.get("gaps_identified", []))
        coverage = analysis_data.get("coverage_estimate", 0)
        return f"{gaps_count} gaps identified, {int(coverage * 100)}% coverage"
    except Exception:
        return "Analysis complete"


def _build_trade_summary(
    symbol: str,
    action: str,
    approved: bool,
    backtest_metrics: dict[str, object] | None,
    trade_id: object | None,
) -> str:
    """Build a human-readable trade decision summary for git commits."""
    decision = "APPROVED" if approved else "REJECTED"
    summary = f"{symbol} {action} {decision}"

    if backtest_metrics:
        sharpe_raw = backtest_metrics.get("sharpe_ratio", 0)
        win_rate_raw = backtest_metrics.get("win_rate", 0)
        sharpe_f = float(str(sharpe_raw)) if sharpe_raw is not None else 0.0
        win_rate_f = float(str(win_rate_raw)) if win_rate_raw is not None else 0.0
        summary += f" (Sharpe {sharpe_f:.1f}, win rate {win_rate_f:.0f}%)"

    if trade_id:
        summary += f" (trade_id: {str(trade_id)[:8]})"

    return summary


def _check_backtest_gating(
    backtest_metrics: dict[str, object],
) -> list[str]:
    """Check if backtest metrics pass hard gating thresholds.

    Returns:
        List of failure reasons (empty if all pass)
    """
    sharpe_val = backtest_metrics["sharpe_ratio"]
    win_rate_val = backtest_metrics["win_rate"]
    max_dd_val = backtest_metrics["max_drawdown_pct"]
    sharpe = float(str(sharpe_val)) if sharpe_val is not None else 0.0
    win_rate = float(str(win_rate_val)) if win_rate_val is not None else 0.0
    max_dd = float(str(max_dd_val)) if max_dd_val is not None else 0.0

    failures = []
    if sharpe < 1.0:
        failures.append(f"Sharpe ratio {sharpe:.2f} < 1.0")
    if win_rate < 50.0:
        failures.append(f"Win rate {win_rate:.1f}% < 50%")
    if max_dd > 20.0:
        failures.append(f"Max drawdown {max_dd:.1f}% > 20%")
    return failures


def _parse_agent_decision(
    output: str, agent_name: str
) -> tuple[bool, str, int]:
    """Parse an agent's JSON decision response.

    Returns:
        (approved, reasoning, confidence)
    """
    try:
        data = json.loads(extract_json(output))
        approved = data.get("decision") == "APPROVE"
        reasoning = data.get("reasoning", "Unknown")
        confidence = int(data.get("confidence", 50))
        return approved, reasoning, confidence
    except Exception as e:
        logger.warning(f"Failed to parse {agent_name} agent response: {e}")
        return False, "Unknown", 50


def _compute_weighted_consensus(
    strategy_approved: bool,
    strategy_confidence: int,
    risk_approved: bool,
    risk_confidence: int,
) -> tuple[bool, bool, float]:
    """Compute confidence-weighted consensus from two agent decisions.

    Returns:
        (approved, agents_disagree, weighted_score)
    """
    strategy_score = 1 if strategy_approved else 0
    risk_score = 1 if risk_approved else 0
    total_weight = strategy_confidence + risk_confidence

    if total_weight > 0:
        weighted_score = (
            strategy_score * strategy_confidence + risk_score * risk_confidence
        ) / total_weight
    else:
        weighted_score = 0.0

    approved = strategy_approved and risk_approved
    agents_disagree = strategy_approved != risk_approved
    return approved, agents_disagree, weighted_score


def _resolve_strategy_params(
    storage: PortfolioStorage, symbol: str
) -> tuple[str, int, int, str, float]:
    """Load custom strategy parameters or fall back to defaults.

    Returns:
        (strategy_name, min_signal_strength, max_holding_days,
         position_sizing_method, position_size_value)
    """
    from app.strategies.storage import get_strategy_storage

    strategy_storage = get_strategy_storage()
    custom_strategy = strategy_storage.get_active_strategy(symbol)

    if custom_strategy:
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
        strategy_name = "signal_classifier"
        min_signal_strength = 7
        max_holding_days = 60
        position_sizing_method = "fixed_dollars"
        position_size_value = 10000.0
        logger.info(f"Using default SignalStrategy (no custom strategy found for {symbol})")

    return strategy_name, min_signal_strength, max_holding_days, position_sizing_method, position_size_value
