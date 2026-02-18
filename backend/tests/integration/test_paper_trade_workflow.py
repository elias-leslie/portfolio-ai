"""Integration tests for paper trade validation workflow with backtest integration."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import Mock, patch

import pytest

from app.agents.tool_executors_trading import TradingTools
from app.backtest.storage import create_backtest_run, update_backtest_result, update_backtest_status
from app.storage.facade import PortfolioStorage
from app.tasks.workflow_tasks import paper_trade_validation_workflow


@pytest.fixture
def storage() -> PortfolioStorage:
    """Create PortfolioStorage instance."""
    return PortfolioStorage()


def test_backtest_tool_executor_integration(storage: PortfolioStorage) -> None:
    """Test run_backtest tool executor with real database."""
    trading_tools = TradingTools(storage=storage)
    agent_run_id = str(uuid.uuid4())
    symbol = "AAPL"

    # Use recent 30-day window for quick test
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    # Mock the backtest task to avoid actual backtest execution
    with patch("app.tasks.backtest_tasks.run_backtest_task") as mock_task:
        mock_task.delay.return_value = Mock(id="task-123")

        # Create a real backtest_run record
        with patch("app.agents.tool_executors_trading.create_backtest_run") as mock_create:
            run_id = str(uuid.uuid4())
            mock_create.return_value = run_id

            # Manually create the backtest_run in database
            actual_run_id = create_backtest_run(
                storage=storage,
                strategy_name="signal_classifier",
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                initial_capital=Decimal("100000.00"),
            )

            # Update to running
            update_backtest_status(storage, actual_run_id, "running")

            # Simulate backtest completion with metrics
            from app.storage.connection import ConnectionManager as _ConnectionManager
            _cm = _ConnectionManager()
            update_backtest_result(
                storage=_cm,
                run_id=actual_run_id,
                final_equity=Decimal("110000.00"),
                total_return_pct=Decimal("10.0"),
                sharpe_ratio=Decimal("1.5"),
                max_drawdown_pct=Decimal("8.0"),
                win_rate=Decimal("60.0"),
                num_trades=5,
                profit_factor=Decimal("2.0"),
            )

            # Mock get_backtest_run to return our actual run
            with patch("app.agents.tool_executors_trading.get_backtest_run") as mock_get_backtest:
                from app.backtest.storage import get_backtest_run

                mock_get_backtest.side_effect = lambda storage, _run_id: get_backtest_run(
                    storage, actual_run_id
                )

                with patch("app.agents.tool_executors_trading.time.sleep"):
                    result = trading_tools.execute_run_backtest(
                        agent_run_id=agent_run_id,
                        symbol=symbol,
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                    )

    # Verify result
    assert result["status"] == "completed"
    assert result["symbol"] == symbol
    assert result["sharpe_ratio"] == 1.5
    assert result["win_rate"] == 60.0
    assert result["max_drawdown_pct"] == 8.0
    assert result["total_return_pct"] == 10.0
    assert result["num_trades"] == 5


def test_paper_trade_validation_workflow_approval(storage: PortfolioStorage) -> None:
    """Test paper trade validation workflow with good backtest metrics (should approve)."""
    strategy_id = str(uuid.uuid4())
    symbol = "NVDA"
    action = "buy"
    thesis = "Strong AI momentum, excellent technical setup"

    # Mock LLM responses to approve
    strategy_response = Mock()
    strategy_response.content = """{"decision": "APPROVE", "reasoning": "Backtest shows Sharpe 1.5, win rate 60%, meeting all thresholds", "metrics": {"sharpe_ratio": 1.5, "win_rate": 60.0, "max_drawdown_pct": 15.0, "total_return_pct": 20.0}}"""

    risk_response = Mock()
    risk_response.content = (
        """{"decision": "APPROVE", "reasoning": "Metrics exceed risk thresholds, thesis aligned"}"""
    )

    # Mock DualProviderClient
    with patch("app.tasks.workflow_tasks.DualProviderClient") as mock_client:
        mock_client_instance = Mock()
        mock_client_instance.generate.side_effect = [strategy_response, risk_response]
        mock_client.return_value = mock_client_instance

        # Mock paper trade creation by mocking the AgentTools class
        with patch("app.tasks.workflow_tasks.AgentTools") as mock_agent_tools_class:
            trade_id = str(uuid.uuid4())
            mock_tools_instance = Mock()
            mock_tools_instance.execute_create_paper_trade.return_value = {
                "status": "created",
                "trade_id": trade_id,
                "symbol": symbol,
                "action": action,
            }
            mock_agent_tools_class.return_value = mock_tools_instance

            # Mock git automation
            with patch("app.tasks.workflow_tasks.commit_workflow_results", return_value=True):
                result = paper_trade_validation_workflow(
                    strategy_id=strategy_id,
                    symbol=symbol,
                    action=action,
                    thesis=thesis,
                )

    # Verify workflow approved and created trade
    assert result["status"] == "completed"
    assert result["approved"] is True
    assert result["strategy_approved"] is True
    assert result["risk_approved"] is True
    assert result["trade_id"] == trade_id
    backtest_metrics: Any = result["backtest_metrics"]
    assert backtest_metrics["sharpe_ratio"] == 1.5
    assert backtest_metrics["win_rate"] == 60.0


def test_paper_trade_validation_workflow_rejection(storage: PortfolioStorage) -> None:
    """Test paper trade validation workflow with bad backtest metrics (should reject)."""
    strategy_id = str(uuid.uuid4())
    symbol = "BADSTOCK"
    action = "buy"
    thesis = "High risk speculative play"

    # Mock LLM responses to reject
    strategy_response = Mock()
    strategy_response.content = """{"decision": "REJECT", "reasoning": "Backtest shows Sharpe 0.5, win rate 40%, below thresholds", "metrics": {"sharpe_ratio": 0.5, "win_rate": 40.0, "max_drawdown_pct": 30.0, "total_return_pct": -5.0}}"""

    risk_response = Mock()
    risk_response.content = """{"decision": "REJECT", "reasoning": "Metrics fail risk thresholds, excessive drawdown"}"""

    with patch("app.tasks.workflow_tasks.DualProviderClient") as mock_client:
        mock_client_instance = Mock()
        mock_client_instance.generate.side_effect = [strategy_response, risk_response]
        mock_client.return_value = mock_client_instance

        # Mock git automation
        with patch("app.tasks.workflow_tasks.commit_workflow_results", return_value=True):
            result = paper_trade_validation_workflow(
                strategy_id=strategy_id,
                symbol=symbol,
                action=action,
                thesis=thesis,
            )

    # Verify workflow rejected and did NOT create trade
    assert result["status"] == "completed"
    assert result["approved"] is False
    assert result["strategy_approved"] is False
    assert result["risk_approved"] is False
    assert result["trade_id"] is None


def test_paper_trade_validation_workflow_split_decision(storage: PortfolioStorage) -> None:
    """Test workflow when strategy approves but risk rejects (should reject overall)."""
    strategy_id = str(uuid.uuid4())
    symbol = "RISKY"
    action = "buy"
    thesis = "Moderate setup with concerns"

    # Strategy approves, risk rejects
    strategy_response = Mock()
    strategy_response.content = """{"decision": "APPROVE", "reasoning": "Backtest marginally passes", "metrics": {"sharpe_ratio": 1.1, "win_rate": 52.0, "max_drawdown_pct": 19.0}}"""

    risk_response = Mock()
    risk_response.content = """{"decision": "REJECT", "reasoning": "Metrics too close to thresholds, market conditions unfavorable"}"""

    with patch("app.tasks.workflow_tasks.DualProviderClient") as mock_client:
        mock_client_instance = Mock()
        mock_client_instance.generate.side_effect = [strategy_response, risk_response]
        mock_client.return_value = mock_client_instance

        with patch("app.tasks.workflow_tasks.commit_workflow_results", return_value=True):
            result = paper_trade_validation_workflow(
                strategy_id=strategy_id,
                symbol=symbol,
                action=action,
                thesis=thesis,
            )

    # Verify consensus requires BOTH agents to approve
    assert result["status"] == "completed"
    assert result["approved"] is False  # Risk rejected
    assert result["strategy_approved"] is True
    assert result["risk_approved"] is False
    assert result["trade_id"] is None


def test_paper_trade_validation_workflow_agent_failure(storage: PortfolioStorage) -> None:
    """Test workflow when agent fails (should fail workflow)."""
    strategy_id = str(uuid.uuid4())
    symbol = "AAPL"
    action = "buy"
    thesis = "Test thesis"

    # Mock strategy agent failure
    with patch("app.tasks.workflow_tasks.DualProviderClient") as mock_client:
        mock_client_instance = Mock()
        mock_client_instance.generate.side_effect = Exception("LLM API unavailable")
        mock_client.return_value = mock_client_instance

        with patch("app.tasks.workflow_tasks.commit_workflow_results", return_value=True):
            result = paper_trade_validation_workflow(
                strategy_id=strategy_id,
                symbol=symbol,
                action=action,
                thesis=thesis,
            )

    # Verify workflow failed
    assert result["status"] == "failed"
    error_msg = result["error"]
    assert isinstance(error_msg, str)
    assert "One or both agents failed" in error_msg
