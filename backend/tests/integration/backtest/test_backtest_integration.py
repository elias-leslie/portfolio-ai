"""Integration tests for backtest functionality.

Tests the complete backtest flow from submission to completion.
Requires test database with day_bars data.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.backtest.storage import (
    create_backtest_run,
    get_backtest_run,
    update_backtest_result,
    update_backtest_status,
)
from app.storage.connection import ConnectionManager


@pytest.fixture
def storage():
    """Get storage connection for tests."""
    return ConnectionManager.get_instance()


@pytest.fixture
def cleanup_backtest(storage):
    """Cleanup backtest runs after test."""
    run_ids = []
    yield run_ids
    # Cleanup: Delete created backtest runs
    with storage.connection() as conn:
        for run_id in run_ids:
            conn.execute("DELETE FROM backtest_equity WHERE run_id = %s", (run_id,))
            conn.execute("DELETE FROM backtest_trades WHERE run_id = %s", (run_id,))
            conn.execute("DELETE FROM backtest_runs WHERE id = %s", (run_id,))
            conn.commit()


class TestBacktestStorage:
    """Test backtest storage operations."""

    def test_create_backtest_run(self, storage, cleanup_backtest):
        """Test creating a backtest run record."""
        run_id = create_backtest_run(
            storage=storage,
            strategy_name="signal_classifier",
            symbol="TEST",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("10000"),
        )
        cleanup_backtest.append(run_id)

        # Verify run was created
        run = get_backtest_run(storage, run_id)
        assert run is not None
        assert run.symbol == "TEST"
        assert run.status == "pending"
        assert run.initial_capital == Decimal("10000")

    def test_update_backtest_status(self, storage, cleanup_backtest):
        """Test updating backtest status."""
        run_id = create_backtest_run(
            storage=storage,
            strategy_name="signal_classifier",
            symbol="TEST",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("10000"),
        )
        cleanup_backtest.append(run_id)

        # Update to running
        update_backtest_status(storage, run_id, "running")
        run = get_backtest_run(storage, run_id)
        assert run.status == "running"

        # Update to completed
        update_backtest_status(storage, run_id, "completed")
        run = get_backtest_run(storage, run_id)
        assert run.status == "completed"
        assert run.completed_at is not None

    def test_update_backtest_result(self, storage, cleanup_backtest):
        """Test updating backtest result metrics."""
        run_id = create_backtest_run(
            storage=storage,
            strategy_name="signal_classifier",
            symbol="TEST",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=Decimal("10000"),
        )
        cleanup_backtest.append(run_id)

        # Update with result metrics
        update_backtest_result(
            storage=storage,
            run_id=run_id,
            total_return_pct=5.5,
            sharpe_ratio=1.2,
            max_drawdown_pct=8.5,
            win_rate=55.0,
            num_trades=10,
            final_equity=Decimal("10550"),
        )

        # Verify metrics were saved
        run = get_backtest_run(storage, run_id)
        assert run.total_return_pct == pytest.approx(5.5, rel=0.01)
        assert run.sharpe_ratio == pytest.approx(1.2, rel=0.01)
        assert run.max_drawdown_pct == pytest.approx(8.5, rel=0.01)
        assert run.win_rate == pytest.approx(55.0, rel=0.01)
        assert run.num_trades == 10


class TestBacktestExecution:
    """Test backtest execution flow."""

    @pytest.mark.skipif(True, reason="Requires Hatchet worker running")
    def test_full_backtest_flow(self, storage, cleanup_backtest):
        """Test complete backtest from submission to completion.

        This test requires:
        - Hatchet worker running
        - day_bars data for the symbol

        Skip for CI/CD environments.
        """
        from app.agents.tool_executors_trading import TradingTools

        tools = TradingTools(storage)

        # Run a 30-day backtest
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=30)

        result = tools.execute_run_backtest(
            agent_run_id="test-agent-001",
            symbol="AAPL",
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            initial_capital=10000.0,
        )

        # Check result
        assert result.get("status") in ("completed", "error")

        if result.get("status") == "completed":
            # Verify metrics are populated
            assert "sharpe_ratio" in result
            assert "win_rate" in result
            assert "total_return_pct" in result
            assert "num_trades" in result

            # Add run_id to cleanup
            if result.get("run_id"):
                cleanup_backtest.append(result["run_id"])
