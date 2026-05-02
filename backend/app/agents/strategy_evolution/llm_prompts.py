"""LLM prompting and interaction for strategy evolution."""

from __future__ import annotations

import json

from app.agents.clients.agent_hub_client import AgentHubAPIClient
from app.logging_config import get_logger
from app.services.agent_hub_prompt_service import render_agent_hub_prompt, require_agent_hub_prompt
from app.strategies.models import StrategyDefinition

from .models import StrategyAnalysis, StrategyMutation

logger = get_logger(__name__)

STRATEGY_DIAGNOSIS_PROMPT = "portfolio-strategy-evolution-diagnosis-template"
STRATEGY_DIAGNOSIS_SYSTEM_PROMPT = "portfolio-strategy-evolution-diagnosis-system"
STRATEGY_MUTATION_PROMPT = "portfolio-strategy-evolution-mutation-template"
STRATEGY_MUTATION_SYSTEM_PROMPT = "portfolio-strategy-evolution-mutation-system"


async def llm_diagnose_performance(
    strategy: StrategyDefinition,
    actual_sharpe: float,
    expected_sharpe: float,
    trades_count: int,
    win_rate: float,
    avg_pnl: float,
    max_drawdown: float,
    buy_hold_sharpe: float,
) -> str:
    """Use LLM to diagnose why strategy is underperforming.

    Args:
        strategy: Strategy definition
        actual_sharpe: Actual Sharpe ratio
        expected_sharpe: Expected Sharpe ratio
        trades_count: Number of trades
        win_rate: Win rate (0-1)
        avg_pnl: Average P&L per trade
        max_drawdown: Maximum drawdown (0-1)
        buy_hold_sharpe: Buy & hold benchmark Sharpe

    Returns:
        LLM-generated diagnosis (2-3 sentences)
    """
    prompt = render_agent_hub_prompt(
        STRATEGY_DIAGNOSIS_PROMPT,
        symbol=strategy.symbol,
        strategy_type=str(strategy.strategy_type),
        strategy_parameters=json.dumps(strategy.parameters, indent=2),
        expected_sharpe=f"{expected_sharpe:.2f}",
        actual_sharpe=f"{actual_sharpe:.2f}",
        sharpe_shortfall=f"{(expected_sharpe - actual_sharpe):.2f}",
        win_rate=f"{win_rate:.1%}",
        avg_pnl=f"{avg_pnl:.2f}",
        max_drawdown=f"{max_drawdown:.1%}",
        trades_count=trades_count,
        buy_hold_sharpe=f"{buy_hold_sharpe:.2f}",
    )

    client = AgentHubAPIClient(agent_slug="risk-manager")
    response = client.generate(
        prompt=prompt,
        system=require_agent_hub_prompt(STRATEGY_DIAGNOSIS_SYSTEM_PROMPT),
        purpose="underperformance_diagnosis",
    )

    return response.content


async def propose_mutations(
    strategy: StrategyDefinition,
    analysis: StrategyAnalysis,
) -> list[StrategyMutation]:
    """Generate strategy mutations using LLM.

    Args:
        strategy: Current strategy definition
        analysis: Performance analysis

    Returns:
        List of proposed mutations (max 5)
    """
    logger.info("proposing_mutations", symbol=strategy.symbol, actual_sharpe=round(analysis.actual_sharpe, 2))

    # Build LLM prompt
    prompt = render_agent_hub_prompt(
        STRATEGY_MUTATION_PROMPT,
        symbol=strategy.symbol,
        strategy_type=str(strategy.strategy_type),
        strategy_parameters=json.dumps(strategy.parameters, indent=2),
        actual_sharpe=f"{analysis.actual_sharpe:.2f}",
        expected_sharpe=f"{analysis.expected_sharpe:.2f}",
        performance_ratio=f"{analysis.performance_ratio:.1%}",
        win_rate=f"{analysis.win_rate:.1%}",
        trades_count=analysis.trades_count,
        max_drawdown=f"{analysis.max_drawdown:.1%}",
        buy_hold_sharpe=f"{analysis.buy_hold_sharpe:.2f}",
        beats_benchmark=str(analysis.beats_benchmark),
        diagnosis=analysis.diagnosis,
    )

    client = AgentHubAPIClient(agent_slug="trade-manager")
    response = client.generate(
        prompt=prompt,
        system=require_agent_hub_prompt(STRATEGY_MUTATION_SYSTEM_PROMPT),
        purpose="strategy_evolution",
    )

    # Parse mutations
    try:
        mutations_data = json.loads(response.content)
        mutations = [
            StrategyMutation(
                mutation_type=m["mutation_type"],
                parameter_changes=m["parameter_changes"],
                reasoning=m["reasoning"],
                confidence=m["confidence"],
            )
            for m in mutations_data
        ]
        logger.info("mutations_proposed", count=len(mutations))
        return mutations[:5]  # Limit to 5
    except json.JSONDecodeError as e:
        logger.exception("llm_mutations_json_invalid", error=str(e))
        return []
    except (KeyError, TypeError) as e:
        logger.exception("llm_mutations_schema_invalid", error=str(e))
        return []
