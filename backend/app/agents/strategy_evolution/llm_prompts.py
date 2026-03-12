"""LLM prompting and interaction for strategy evolution."""

from __future__ import annotations

import json

from app.agents.llm_client import AgentHubAPIClient
from app.constants import GEMINI_FLASH
from app.logging_config import get_logger
from app.strategies.models import StrategyDefinition

from .models import StrategyAnalysis, StrategyMutation

logger = get_logger(__name__)


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
    prompt = f"""Analyze this underperforming trading strategy and diagnose the likely root cause.

**Strategy:**
- Symbol: {strategy.symbol}
- Type: {strategy.strategy_type}
- Parameters: {json.dumps(strategy.parameters, indent=2)}

**Performance:**
- Expected Sharpe: {expected_sharpe:.2f}
- Actual Sharpe: {actual_sharpe:.2f}
- Shortfall: {(expected_sharpe - actual_sharpe):.2f}
- Win Rate: {win_rate:.1%}
- Avg P&L: ${avg_pnl:.2f}
- Max Drawdown: {max_drawdown:.1%}
- Trades: {trades_count}
- Buy & Hold Sharpe: {buy_hold_sharpe:.2f}

Provide a 2-3 sentence diagnosis identifying the most likely cause of underperformance.
Focus on actionable insights (e.g., "too aggressive entries", "holding too long", "ignoring volatility").
"""

    client = AgentHubAPIClient(model=GEMINI_FLASH)
    response = client.generate(
        prompt=prompt,
        system="You are a quantitative trading analyst. Diagnose strategy underperformance concisely.",
        temperature=0.3,
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
    prompt = f"""You are a quantitative trading strategist analyzing an underperforming strategy.

**Current Strategy:**
- Symbol: {strategy.symbol}
- Type: {strategy.strategy_type}
- Parameters: {json.dumps(strategy.parameters, indent=2)}

**Performance Analysis:**
- Actual Sharpe: {analysis.actual_sharpe:.2f}
- Expected Sharpe: {analysis.expected_sharpe:.2f}
- Performance Ratio: {analysis.performance_ratio:.1%}
- Win Rate: {analysis.win_rate:.1%}
- Trades: {analysis.trades_count}
- Max Drawdown: {analysis.max_drawdown:.1%}
- Buy & Hold Sharpe: {analysis.buy_hold_sharpe:.2f}
- Beats Benchmark: {analysis.beats_benchmark}

**Diagnosis:**
{analysis.diagnosis}

**Your Task:**
Propose 3-5 specific parameter mutations that could improve performance. Each mutation should:
1. Target a specific weakness identified in the diagnosis
2. Make conservative changes (10-20% adjustments, not radical shifts)
3. Explain why the change should help

Return JSON array with this schema:
[
  {{
    "mutation_type": "weight_adjustment|threshold_change|risk_tightening|entry_timing",
    "parameter_changes": {{"param_name": new_value}},
    "reasoning": "Why this should improve performance",
    "confidence": 0.75
  }}
]

**Critical Rules:**
- If adjusting weights, ensure they still sum to 1.0
- Keep thresholds within valid ranges (RSI 0-100, sentiment -1 to +1)
- Don't change more than 3 parameters per mutation
- Focus on the most impactful changes first
"""

    # Call LLM
    client = AgentHubAPIClient(model=GEMINI_FLASH)
    response = client.generate(
        prompt=prompt,
        system="You are a quantitative trading strategy optimizer. Analyze underperforming strategies and propose concrete parameter improvements.",
        temperature=0.7,  # Allow some creativity
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
    except Exception as e:
        logger.exception("llm_mutations_parse_failed", error=str(e))
        return []
