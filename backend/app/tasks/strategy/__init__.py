"""Strategy tasks module.

Exports all strategy-related Celery tasks:
- Performance monitoring and evaluation
- Strategy generation and refresh
- Strategy evolution via LLM mutation
"""

from app.tasks.strategy.evolution_tasks import weekly_strategy_evolution
from app.tasks.strategy.generation_tasks import (
    daily_strategy_refresh,
    trigger_strategies_for_top_watchlist,
    trigger_strategy_from_seed,
    weekly_strategy_generation,
)
from app.tasks.strategy.performance_tasks import (
    auto_promote_strategies,
    evaluate_strategy_performance,
)

__all__ = [
    "auto_promote_strategies",
    "daily_strategy_refresh",
    "evaluate_strategy_performance",
    "trigger_strategies_for_top_watchlist",
    "trigger_strategy_from_seed",
    "weekly_strategy_evolution",
    "weekly_strategy_generation",
]
