"""Helper functions for building EvolutionResult objects."""

from __future__ import annotations

from .models import EvolutionResult, StrategyMutation


def build_failure_result(
    strategy_id: str,
    reason: str,
    message: str,
    parent_sharpe: float,
    buy_hold_sharpe: float,
    mutations_tested: int = 0,
    child_sharpe: float | None = None,
    best_mutation: StrategyMutation | None = None,
) -> EvolutionResult:
    """Build a failure EvolutionResult.

    Args:
        strategy_id: Original strategy ID
        reason: Evolution reason
        message: Failure message
        parent_sharpe: Parent strategy Sharpe ratio
        buy_hold_sharpe: Buy & hold benchmark Sharpe
        mutations_tested: Number of mutations tested (default 0)
        child_sharpe: Best child Sharpe if any (default None)
        best_mutation: Best mutation if any (default None)

    Returns:
        EvolutionResult with success=False
    """
    return EvolutionResult(
        success=False,
        original_strategy_id=strategy_id,
        new_strategy_id=None,
        parent_sharpe=parent_sharpe,
        child_sharpe=child_sharpe,
        buy_hold_sharpe=buy_hold_sharpe,
        changes_description=best_mutation.reasoning if best_mutation else "",
        evolution_reason=reason,
        mutations_tested=mutations_tested,
        best_mutation=best_mutation,
        message=message,
    )


def build_success_result(
    original_strategy_id: str,
    new_strategy_id: str,
    parent_sharpe: float,
    child_sharpe: float,
    buy_hold_sharpe: float,
    best_mutation: StrategyMutation,
    mutations_tested: int,
    reason: str,
) -> EvolutionResult:
    """Build a success EvolutionResult.

    Args:
        original_strategy_id: Original strategy ID
        new_strategy_id: New evolved strategy ID
        parent_sharpe: Parent strategy Sharpe ratio
        child_sharpe: Child strategy Sharpe ratio
        buy_hold_sharpe: Buy & hold benchmark Sharpe
        best_mutation: Best mutation that was applied
        mutations_tested: Number of mutations tested
        reason: Evolution reason

    Returns:
        EvolutionResult with success=True
    """
    return EvolutionResult(
        success=True,
        original_strategy_id=original_strategy_id,
        new_strategy_id=new_strategy_id,
        parent_sharpe=parent_sharpe,
        child_sharpe=child_sharpe,
        buy_hold_sharpe=buy_hold_sharpe,
        changes_description=best_mutation.reasoning,
        evolution_reason=reason,
        mutations_tested=mutations_tested,
        best_mutation=best_mutation,
        message=f"Evolution successful: Sharpe {parent_sharpe:.2f} → {child_sharpe:.2f}",
    )
