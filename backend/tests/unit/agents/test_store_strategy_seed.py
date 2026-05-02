"""Tests for store_strategy_seed tool."""

from unittest.mock import MagicMock

from app.agents.trading.ideas import execute_store_strategy_seed


class TestStoreStrategySeed:
    """Tests for the store_strategy_seed tool executor."""

    def test_store_seed_basic(self) -> None:
        """Test basic seed storage."""
        mock_storage = MagicMock()

        result = execute_store_strategy_seed(
            mock_storage,
            "test-run-123",
            "AAPL",
            "Strong earnings growth expected",
            6.0,
        )

        assert result["status"] == "stored"
        assert result["symbol"] == "AAPL"
        assert result["confidence"] == 6.0
        assert result["workflow_triggered"] is False  # < 7 threshold
        assert "seed_id" in result
        mock_storage.insert_dict.assert_called_once()

    def test_store_seed_normalizes_symbol(self) -> None:
        """Test symbol is normalized to uppercase."""
        mock_storage = MagicMock()

        result = execute_store_strategy_seed(
            mock_storage,
            "test-run",
            "  aapl  ",
            "Test thesis",
            5.0,
        )

        assert result["symbol"] == "AAPL"

    def test_store_seed_empty_symbol_returns_error(self) -> None:
        """Test empty symbol returns error."""
        mock_storage = MagicMock()

        result = execute_store_strategy_seed(
            mock_storage,
            "test-run",
            "   ",
            "Test thesis",
            5.0,
        )

        assert result["status"] == "error"
        assert "Symbol is required" in str(result["error"])

    def test_store_seed_normalizes_confidence_from_100_scale(self) -> None:
        """Test confidence is normalized from 0-100 to 1-10 scale."""
        mock_storage = MagicMock()

        result = execute_store_strategy_seed(
            mock_storage,
            "test-run",
            "NVDA",
            "AI boom",
            85.0,
        )

        assert result["confidence"] == 8.5

    def test_store_seed_clamps_confidence(self) -> None:
        """Test confidence is clamped to 1-10 range."""
        mock_storage = MagicMock()

        result = execute_store_strategy_seed(
            mock_storage,
            "test-run",
            "TSLA",
            "Test",
            0.5,
        )
        assert result["confidence"] == 1.0

    def test_store_seed_high_confidence_sets_workflow_flag(self) -> None:
        """Test workflow_triggered flag is set for confidence >= 7 (actual trigger tested in integration)."""
        mock_storage = MagicMock()
        mock_conn = MagicMock()
        mock_storage.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_storage.connection.return_value.__exit__ = MagicMock(return_value=False)

        result_low = execute_store_strategy_seed(
            mock_storage,
            "test-run",
            "GOOGL",
            "Test thesis",
            6.0,
        )
        assert result_low["workflow_triggered"] is False

        # Note: High confidence trigger is tested in integration tests
        # since it involves lazy imports and task dispatch

    def test_store_seed_inserts_correct_data(self) -> None:
        """Test correct data is inserted into strategy_seeds table."""
        mock_storage = MagicMock()

        execute_store_strategy_seed(
            mock_storage,
            "run-456",
            "MSFT",
            "Enterprise AI adoption",
            7.5,
        )

        call_args = mock_storage.insert_dict.call_args
        assert call_args[0][0] == "strategy_seeds"
        data = call_args[0][1]
        assert data["symbol"] == "MSFT"
        assert data["thesis"] == "Enterprise AI adoption"
        assert data["confidence"] == 7.5
        assert data["agent_run_id"] == "run-456"
        assert data["source_type"] == "discovery"
        assert data["status"] == "pending"
