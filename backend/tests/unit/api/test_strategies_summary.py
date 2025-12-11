"""Unit tests for strategies summary API endpoint."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.strategies.models import StrategyDefinition


class TestStrategySummaryAPI:
    """Tests for GET /api/strategies/summary endpoint."""

    @pytest.fixture
    def client(self) -> TestClient:
        """Create test client."""
        from app.main import app

        return TestClient(app)

    def test_empty_strategies_list(self, client: TestClient) -> None:
        """Test summary with no strategies returns zeros."""
        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = []

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 0
            assert data["active"] == 0
            assert data["testing"] == 0
            assert data["archived"] == 0
            assert data["avg_expected_sharpe"] is None
            assert data["avg_live_sharpe"] is None
            assert data["total_trades"] == 0
            assert data["exceeding_count"] == 0
            assert data["meeting_count"] == 0
            assert data["underperforming_count"] == 0

    def test_mixed_status_strategies(self, client: TestClient) -> None:
        """Test summary correctly counts strategies by status."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Active Strategy",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.5"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("1.4"),
            ),
            StrategyDefinition(
                id="strat-2",
                name="Testing Strategy 1",
                symbol="MSFT",
                strategy_type="value",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.2"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 2),
                version=1,
                status="testing",
                live_trades_count=5,
            ),
            StrategyDefinition(
                id="strat-3",
                name="Testing Strategy 2",
                symbol="GOOGL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=None,
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 3),
                version=1,
                status="testing",
                live_trades_count=0,
            ),
            StrategyDefinition(
                id="strat-4",
                name="Archived Strategy",
                symbol="TSLA",
                strategy_type="event",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("0.8"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 4),
                version=1,
                status="archived",
                archive_date=datetime(2025, 2, 1),
                archive_reason="Underperforming",
                live_trades_count=20,
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 4
            assert data["active"] == 1
            assert data["testing"] == 2
            assert data["archived"] == 1
            assert data["total_trades"] == 35  # 10 + 5 + 0 + 20

    def test_performance_flag_calculation_exceeding(self, client: TestClient) -> None:
        """Test exceeding performance flag (variance >= 0.9)."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Exceeding Strategy",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("1.2"),  # 1.2 / 1.0 = 1.2 >= 0.9
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            assert data["exceeding_count"] == 1
            assert data["meeting_count"] == 0
            assert data["underperforming_count"] == 0

    def test_performance_flag_calculation_meeting(self, client: TestClient) -> None:
        """Test meeting performance flag (0.7 <= variance < 0.9)."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Meeting Strategy",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("0.8"),  # 0.8 / 1.0 = 0.8 (0.7 <= 0.8 < 0.9)
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            assert data["exceeding_count"] == 0
            assert data["meeting_count"] == 1
            assert data["underperforming_count"] == 0

    def test_performance_flag_calculation_underperforming(self, client: TestClient) -> None:
        """Test underperforming performance flag (variance < 0.7)."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Underperforming Strategy",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("0.5"),  # 0.5 / 1.0 = 0.5 < 0.7
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            assert data["exceeding_count"] == 0
            assert data["meeting_count"] == 0
            assert data["underperforming_count"] == 1

    def test_performance_flags_skip_no_trades(self, client: TestClient) -> None:
        """Test that strategies with no trades are excluded from performance flags."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="No Trades Strategy",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="testing",
                live_trades_count=0,  # No trades
                live_sharpe_ratio=None,
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            # No performance flags because no trades
            assert data["exceeding_count"] == 0
            assert data["meeting_count"] == 0
            assert data["underperforming_count"] == 0

    def test_performance_flags_skip_null_sharpe(self, client: TestClient) -> None:
        """Test that strategies with null live_sharpe_ratio are excluded."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Null Sharpe Strategy",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=None,  # Null Sharpe
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            # No performance flags because live_sharpe_ratio is null
            assert data["exceeding_count"] == 0
            assert data["meeting_count"] == 0
            assert data["underperforming_count"] == 0

    def test_performance_flags_skip_null_expected_sharpe(self, client: TestClient) -> None:
        """Test that strategies with null expected_sharpe are excluded."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Null Expected Sharpe Strategy",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=None,  # Null expected Sharpe
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("1.2"),
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            # No performance flags because expected_sharpe is null
            assert data["exceeding_count"] == 0
            assert data["meeting_count"] == 0
            assert data["underperforming_count"] == 0

    def test_performance_flags_skip_zero_expected_sharpe(self, client: TestClient) -> None:
        """Test that strategies with zero expected_sharpe are excluded."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Zero Expected Sharpe Strategy",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("0.0"),  # Zero expected Sharpe
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("1.2"),
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            # No performance flags because expected_sharpe is 0
            assert data["exceeding_count"] == 0
            assert data["meeting_count"] == 0
            assert data["underperforming_count"] == 0

    def test_average_sharpe_calculation_with_nulls(self, client: TestClient) -> None:
        """Test average Sharpe calculation excludes null values."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Strategy 1",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.5"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("1.4"),
            ),
            StrategyDefinition(
                id="strat-2",
                name="Strategy 2",
                symbol="MSFT",
                strategy_type="value",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("2.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 2),
                version=1,
                status="testing",
                live_trades_count=5,
                live_sharpe_ratio=Decimal("1.8"),
            ),
            StrategyDefinition(
                id="strat-3",
                name="Strategy 3 - Null Expected",
                symbol="GOOGL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=None,  # Null - should be excluded
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 3),
                version=1,
                status="testing",
                live_trades_count=3,
                live_sharpe_ratio=Decimal("0.9"),
            ),
            StrategyDefinition(
                id="strat-4",
                name="Strategy 4 - Null Live",
                symbol="TSLA",
                strategy_type="event",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.2"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 4),
                version=1,
                status="active",
                live_trades_count=0,
                live_sharpe_ratio=None,  # Null - should be excluded
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            # avg_expected = (1.5 + 2.0 + 1.2) / 3 = 4.7 / 3 = 1.57 (rounded to 1.57)
            assert data["avg_expected_sharpe"] == 1.57

            # avg_live = (1.4 + 1.8 + 0.9) / 3 = 4.1 / 3 = 1.37 (rounded to 1.37)
            assert data["avg_live_sharpe"] == 1.37

    def test_average_sharpe_all_null_expected(self, client: TestClient) -> None:
        """Test that avg_expected_sharpe is None when all expected_sharpe values are null."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Strategy 1",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=None,
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="testing",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("1.2"),
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            assert data["avg_expected_sharpe"] is None
            assert data["avg_live_sharpe"] == 1.2

    def test_average_sharpe_all_null_live(self, client: TestClient) -> None:
        """Test that avg_live_sharpe is None when all live_sharpe_ratio values are null."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Strategy 1",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.5"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="testing",
                live_trades_count=0,
                live_sharpe_ratio=None,
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            assert data["avg_expected_sharpe"] == 1.5
            assert data["avg_live_sharpe"] is None

    def test_mixed_performance_flags(self, client: TestClient) -> None:
        """Test multiple strategies with different performance flags."""
        strategies = [
            # Strategy 1: Exceeding expectations (variance = 1.5)
            StrategyDefinition(
                id="strat-1",
                name="Exceeding 1",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("1.5"),  # 1.5 / 1.0 = 1.5
            ),
            # Strategy 2: Exceeding expectations at boundary (variance = 0.9)
            StrategyDefinition(
                id="strat-2",
                name="Exceeding 2",
                symbol="MSFT",
                strategy_type="value",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 2),
                version=1,
                status="active",
                live_trades_count=8,
                live_sharpe_ratio=Decimal("0.9"),  # 0.9 / 1.0 = 0.9 (exactly 0.9)
            ),
            # Strategy 3: Meeting expectations (variance = 0.8)
            StrategyDefinition(
                id="strat-3",
                name="Meeting 1",
                symbol="GOOGL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 3),
                version=1,
                status="active",
                live_trades_count=12,
                live_sharpe_ratio=Decimal("0.8"),  # 0.8 / 1.0 = 0.8
            ),
            # Strategy 4: Meeting expectations at boundary (variance = 0.7)
            StrategyDefinition(
                id="strat-4",
                name="Meeting 2",
                symbol="TSLA",
                strategy_type="event",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 4),
                version=1,
                status="active",
                live_trades_count=7,
                live_sharpe_ratio=Decimal("0.7"),  # 0.7 / 1.0 = 0.7 (exactly 0.7)
            ),
            # Strategy 5: Underperforming (variance = 0.5)
            StrategyDefinition(
                id="strat-5",
                name="Underperforming 1",
                symbol="NVDA",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 5),
                version=1,
                status="archived",
                archive_date=datetime(2025, 2, 1),
                archive_reason="Underperforming",
                live_trades_count=15,
                live_sharpe_ratio=Decimal("0.5"),  # 0.5 / 1.0 = 0.5
            ),
            # Strategy 6: No trades yet (excluded from performance flags)
            StrategyDefinition(
                id="strat-6",
                name="No Trades",
                symbol="META",
                strategy_type="value",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.0"),
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 6),
                version=1,
                status="testing",
                live_trades_count=0,
                live_sharpe_ratio=None,
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            assert data["total"] == 6
            assert data["exceeding_count"] == 2
            assert data["meeting_count"] == 2
            assert data["underperforming_count"] == 1

    def test_error_handling_storage_exception(self, client: TestClient) -> None:
        """Test that storage exceptions return 500 error."""
        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.side_effect = Exception(
                "Database connection failed"
            )

            response = client.get("/api/strategies/summary")

            assert response.status_code == 500
            assert "Failed to get strategy summary" in response.json()["detail"]

    def test_response_model_structure(self, client: TestClient) -> None:
        """Test that response contains all required fields."""
        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = []

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            # Verify all required fields exist
            required_fields = [
                "total",
                "active",
                "testing",
                "archived",
                "avg_expected_sharpe",
                "avg_live_sharpe",
                "total_trades",
                "exceeding_count",
                "meeting_count",
                "underperforming_count",
            ]

            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

    def test_sharpe_rounding(self, client: TestClient) -> None:
        """Test that average Sharpe values are rounded to 2 decimal places."""
        strategies = [
            StrategyDefinition(
                id="strat-1",
                name="Strategy 1",
                symbol="AAPL",
                strategy_type="momentum",
                parameters={},
                research_summary={},
                generation_reasoning="Testing",
                backtest_metrics=[],
                expected_sharpe=Decimal("1.234567"),  # Should round to 1.23
                expected_win_rate=None,
                expected_max_drawdown=None,
                created_by="system",
                created_at=datetime(2025, 1, 1),
                version=1,
                status="active",
                live_trades_count=10,
                live_sharpe_ratio=Decimal("1.876543"),  # Should round to 1.88
            ),
        ]

        with patch("app.api.strategies.get_strategy_storage") as mock_storage:
            mock_storage.return_value.list_strategies.return_value = strategies

            response = client.get("/api/strategies/summary")

            assert response.status_code == 200
            data = response.json()

            # Check rounding to 2 decimal places
            assert data["avg_expected_sharpe"] == 1.23
            assert data["avg_live_sharpe"] == 1.88
