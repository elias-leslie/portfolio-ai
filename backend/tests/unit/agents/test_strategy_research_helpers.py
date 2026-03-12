"""Unit tests for psycopg-aware strategy research helper paths."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import psycopg
import pytest

from app.agents.workflows.strategy_research_helpers import (
    commit_and_build_result,
    store_strategy_and_backtest,
)


@dataclass
class FakeResearch:
    """Dataclass so helper code can serialize with asdict()."""

    thesis: str
    overall_confidence: float = 0.82


def _optimized_result() -> SimpleNamespace:
    return SimpleNamespace(
        parameters=SimpleNamespace(model_dump=lambda: {"lookback_days": 30}),
        optimization_metrics={"avg_sharpe": 1.7},
        avg_sharpe=1.7,
        avg_win_rate=0.58,
        max_drawdown=0.14,
        confidence=0.82,
    )


def _agent_result() -> SimpleNamespace:
    return SimpleNamespace(
        strategy_type="mean_reversion",
        reasoning="Signals are mean reverting after earnings volatility.",
    )


def test_store_strategy_and_backtest_returns_backtest_run_id() -> None:
    """Successful persist path should return both the strategy and run ids."""
    storage = MagicMock()
    storage.store_strategy.return_value = "strategy-123"
    optimizer = MagicMock()
    optimizer.persist_backtest.return_value = "backtest-456"

    result = store_strategy_and_backtest(
        storage,
        optimizer,
        symbol="AAPL",
        workflow_id="wf-1",
        agent_result=_agent_result(),
        optimized=_optimized_result(),
        research=FakeResearch(thesis="Earnings mean reversion"),
    )

    assert result == ("strategy-123", "backtest-456")
    storage.store_strategy.assert_called_once()
    optimizer.persist_backtest.assert_called_once()


@pytest.mark.parametrize(
    "exc",
    [
        psycopg.IntegrityError("duplicate key"),
        psycopg.OperationalError("connection lost"),
        TimeoutError("backtest timed out"),
    ],
)
def test_store_strategy_and_backtest_swallows_expected_persistence_failures(
    exc: Exception,
) -> None:
    """Known persistence failures should keep the workflow alive without a run id."""
    storage = MagicMock()
    storage.store_strategy.return_value = "strategy-123"
    optimizer = MagicMock()
    optimizer.persist_backtest.side_effect = exc

    strategy_id, backtest_run_id = store_strategy_and_backtest(
        storage,
        optimizer,
        symbol="AAPL",
        workflow_id="wf-2",
        agent_result=_agent_result(),
        optimized=_optimized_result(),
        research=FakeResearch(thesis="Momentum exhaustion"),
    )

    assert strategy_id == "strategy-123"
    assert backtest_run_id is None
    optimizer.persist_backtest.assert_called_once()


@patch("app.agents.workflows.strategy_research_helpers.commit_workflow_results")
def test_commit_and_build_result_uses_commit_workflow_results(
    mock_commit_workflow_results: MagicMock,
) -> None:
    """The completion path should emit a workflow snapshot through git automation."""
    result = commit_and_build_result(
        workflow_id="wf-3",
        symbol="MSFT",
        strategy_id="strategy-789",
        agent_result=_agent_result(),
        optimized=_optimized_result(),
        research=FakeResearch(thesis="AI capex cycle"),
    )

    commit_kwargs = mock_commit_workflow_results.call_args.kwargs
    snapshot = commit_kwargs["snapshot_data"]

    assert commit_kwargs["workflow_type"] == "strategy_research"
    assert snapshot["strategy_id"] == "strategy-789"
    assert snapshot["symbol"] == "MSFT"
    assert result["status"] == "completed"
    assert result["strategy_id"] == "strategy-789"
