"""Unit tests for run_backtest tool executor."""

import uuid
from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from app.agents.tool_executors_trading import TradingTools


@pytest.fixture
def mock_storage():
    """Create mock storage."""
    return Mock()


@pytest.fixture
def trading_tools(mock_storage):
    """Create TradingTools instance with mocked storage."""
    return TradingTools(storage=mock_storage)


def test_execute_run_backtest_success(trading_tools, mock_storage):
    """Test successful backtest execution."""
    agent_run_id = str(uuid.uuid4())
    ticker = "AAPL"
    start_date = "2023-01-01"
    end_date = "2024-01-01"

    # Mock backtest run creation
    run_id = str(uuid.uuid4())
    with patch("app.agents.tool_executors_trading.create_backtest_run", return_value=run_id):
        with patch("app.agents.tool_executors_trading.update_backtest_status"):
            with patch("app.tasks.backtest_tasks.run_backtest_task") as mock_task:
                # Mock Celery task
                mock_task.delay.return_value = Mock(id="task-123")

                # Mock get_backtest_run to return completed run
                mock_run = Mock()
                mock_run.status = "completed"
                mock_run.sharpe_ratio = Decimal("1.5")
                mock_run.win_rate = Decimal("60.0")
                mock_run.max_drawdown_pct = Decimal("15.0")
                mock_run.total_return_pct = Decimal("25.5")
                mock_run.num_trades = 10

                with (
                    patch(
                        "app.agents.tool_executors_trading.get_backtest_run", return_value=mock_run
                    ),
                    patch("app.agents.tool_executors_trading.time.sleep"),
                ):
                    result = trading_tools.execute_run_backtest(
                        agent_run_id=agent_run_id,
                        ticker=ticker,
                        start_date=start_date,
                        end_date=end_date,
                    )

    assert result["status"] == "completed"
    assert result["backtest_run_id"] == run_id
    assert result["ticker"] == ticker
    assert result["sharpe_ratio"] == 1.5
    assert result["win_rate"] == 60.0
    assert result["max_drawdown_pct"] == 15.0
    assert result["total_return_pct"] == 25.5
    assert result["num_trades"] == 10
    assert "Backtest complete" in result["message"]


def test_execute_run_backtest_invalid_dates(trading_tools):
    """Test backtest with invalid date format."""
    agent_run_id = str(uuid.uuid4())

    result = trading_tools.execute_run_backtest(
        agent_run_id=agent_run_id,
        ticker="AAPL",
        start_date="invalid-date",
        end_date="2024-01-01",
    )

    assert result["status"] == "error"
    assert "Invalid date format" in result["error"]


def test_execute_run_backtest_end_before_start(trading_tools):
    """Test backtest with end_date before start_date."""
    agent_run_id = str(uuid.uuid4())

    result = trading_tools.execute_run_backtest(
        agent_run_id=agent_run_id,
        ticker="AAPL",
        start_date="2024-01-01",
        end_date="2023-01-01",
    )

    assert result["status"] == "error"
    assert "end_date" in result["error"]
    assert "must be >=" in result["error"]


def test_execute_run_backtest_failed(trading_tools, mock_storage):
    """Test backtest execution that fails."""
    agent_run_id = str(uuid.uuid4())
    ticker = "INVALID"
    start_date = "2023-01-01"
    end_date = "2024-01-01"

    run_id = str(uuid.uuid4())
    with patch("app.agents.tool_executors_trading.create_backtest_run", return_value=run_id):
        with patch("app.agents.tool_executors_trading.update_backtest_status"):
            with patch("app.tasks.backtest_tasks.run_backtest_task") as mock_task:
                mock_task.delay.return_value = Mock(id="task-123")

                # Mock get_backtest_run to return failed run
                mock_run = Mock()
                mock_run.status = "failed"
                mock_run.error_message = "Symbol not found"

                with (
                    patch(
                        "app.agents.tool_executors_trading.get_backtest_run", return_value=mock_run
                    ),
                    patch("app.agents.tool_executors_trading.time.sleep"),
                ):
                    result = trading_tools.execute_run_backtest(
                        agent_run_id=agent_run_id,
                        ticker=ticker,
                        start_date=start_date,
                        end_date=end_date,
                    )

    assert result["status"] == "error"
    assert result["backtest_run_id"] == run_id
    assert result["ticker"] == ticker
    assert "Symbol not found" in result["error"]


def test_execute_run_backtest_timeout(trading_tools, mock_storage):
    """Test backtest execution that times out."""
    agent_run_id = str(uuid.uuid4())
    ticker = "AAPL"
    start_date = "2023-01-01"
    end_date = "2024-01-01"

    run_id = str(uuid.uuid4())
    with patch("app.agents.tool_executors_trading.create_backtest_run", return_value=run_id):
        with patch("app.agents.tool_executors_trading.update_backtest_status"):
            with patch("app.tasks.backtest_tasks.run_backtest_task") as mock_task:
                mock_task.delay.return_value = Mock(id="task-123")

                # Mock get_backtest_run to return running run (never completes)
                mock_run = Mock()
                mock_run.status = "running"

                with (
                    patch(
                        "app.agents.tool_executors_trading.get_backtest_run", return_value=mock_run
                    ),
                    patch("app.agents.tool_executors_trading.time.sleep"),
                ):
                    # Force immediate timeout by patching elapsed time
                    result = trading_tools.execute_run_backtest(
                        agent_run_id=agent_run_id,
                        ticker=ticker,
                        start_date=start_date,
                        end_date=end_date,
                    )

    assert result["status"] == "timeout"
    assert result["backtest_run_id"] == run_id
    assert "timed out" in result["error"]


def test_execute_run_backtest_with_custom_params(trading_tools, mock_storage):
    """Test backtest with custom strategy parameters."""
    agent_run_id = str(uuid.uuid4())
    ticker = "NVDA"
    start_date = "2023-06-01"
    end_date = "2024-06-01"

    run_id = str(uuid.uuid4())
    with patch("app.agents.tool_executors_trading.create_backtest_run", return_value=run_id):
        with patch("app.agents.tool_executors_trading.update_backtest_status"):
            with patch("app.tasks.backtest_tasks.run_backtest_task") as mock_task:
                mock_task.delay.return_value = Mock(id="task-123")

                mock_run = Mock()
                mock_run.status = "completed"
                mock_run.sharpe_ratio = Decimal("2.0")
                mock_run.win_rate = Decimal("65.0")
                mock_run.max_drawdown_pct = Decimal("10.0")
                mock_run.total_return_pct = Decimal("40.0")
                mock_run.num_trades = 15

                with (
                    patch(
                        "app.agents.tool_executors_trading.get_backtest_run", return_value=mock_run
                    ),
                    patch("app.agents.tool_executors_trading.time.sleep"),
                ):
                    result = trading_tools.execute_run_backtest(
                        agent_run_id=agent_run_id,
                        ticker=ticker,
                        start_date=start_date,
                        end_date=end_date,
                        initial_capital=50000.0,
                        min_signal_strength=8,
                        max_holding_days=30,
                        position_size_value=5000.0,
                    )

                # Verify task was called with custom params
                mock_task.delay.assert_called_once()
                call_kwargs = mock_task.delay.call_args[1]
                assert call_kwargs["min_signal_strength"] == 8
                assert call_kwargs["max_holding_days"] == 30
                assert call_kwargs["position_size_value"] == 5000.0

    assert result["status"] == "completed"
    assert result["sharpe_ratio"] == 2.0
    assert result["win_rate"] == 65.0
