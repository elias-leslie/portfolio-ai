"""Strategy Evolution Agent - Compatibility shim.

DEPRECATED: This module has been refactored into app.agents.strategy_evolution.
Import from the new location instead:

    from app.agents.strategy_evolution import (
        BacktestMetrics,
        EvolutionResult,
        StrategyAnalysis,
        StrategyEvolutionAgent,
        StrategyMutation,
        get_strategy_evolution_agent,
    )

This file is maintained for backward compatibility only.
"""

from __future__ import annotations

# Re-export everything from the new module location
from app.agents.strategy_evolution import (
    BacktestMetrics,
    EvolutionResult,
    StrategyAnalysis,
    StrategyEvolutionAgent,
    StrategyMutation,
    get_strategy_evolution_agent,
)
from app.agents.strategy_evolution.backtest import run_walk_forward_validation

__all__ = [
    "BacktestMetrics",
    "EvolutionResult",
    "StrategyAnalysis",
    "StrategyEvolutionAgent",
    "StrategyMutation",
    "get_strategy_evolution_agent",
    "run_walk_forward_validation",
]
