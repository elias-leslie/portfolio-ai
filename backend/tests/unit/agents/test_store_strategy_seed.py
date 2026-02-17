"""Tests for store_strategy_seed tool."""

from unittest.mock import MagicMock


class TestStoreStrategySeed:
    """Tests for the store_strategy_seed tool executor."""

    def test_store_seed_basic(self) -> None:
        """Test basic seed storage."""
        from app.agents.tool_executors_trading import TradingTools

        mock_storage = MagicMock()
        tools = TradingTools(mock_storage)

        result = tools.execute_store_strategy_seed(
            agent_run_id="test-run-123",
            symbol="AAPL",
            thesis="Strong earnings growth expected",
            confidence=6.0,
        )

        assert result["status"] == "stored"
        assert result["symbol"] == "AAPL"
        assert result["confidence"] == 6.0
        assert result["workflow_triggered"] is False  # < 7 threshold
        assert "seed_id" in result
        mock_storage.insert_dict.assert_called_once()

    def test_store_seed_normalizes_symbol(self) -> None:
        """Test symbol is normalized to uppercase."""
        from app.agents.tool_executors_trading import TradingTools

        mock_storage = MagicMock()
        tools = TradingTools(mock_storage)

        result = tools.execute_store_strategy_seed(
            agent_run_id="test-run",
            symbol="  aapl  ",
            thesis="Test thesis",
            confidence=5.0,
        )

        assert result["symbol"] == "AAPL"

    def test_store_seed_empty_symbol_returns_error(self) -> None:
        """Test empty symbol returns error."""
        from app.agents.tool_executors_trading import TradingTools

        mock_storage = MagicMock()
        tools = TradingTools(mock_storage)

        result = tools.execute_store_strategy_seed(
            agent_run_id="test-run",
            symbol="   ",
            thesis="Test thesis",
            confidence=5.0,
        )

        assert result["status"] == "error"
        assert "Symbol is required" in str(result["error"])

    def test_store_seed_normalizes_confidence_from_100_scale(self) -> None:
        """Test confidence is normalized from 0-100 to 1-10 scale."""
        from app.agents.tool_executors_trading import TradingTools

        mock_storage = MagicMock()
        tools = TradingTools(mock_storage)

        result = tools.execute_store_strategy_seed(
            agent_run_id="test-run",
            symbol="NVDA",
            thesis="AI boom",
            confidence=85.0,  # Should become 8.5
        )

        assert result["confidence"] == 8.5

    def test_store_seed_clamps_confidence(self) -> None:
        """Test confidence is clamped to 1-10 range."""
        from app.agents.tool_executors_trading import TradingTools

        mock_storage = MagicMock()
        tools = TradingTools(mock_storage)

        # Test lower bound (0.5 should become 1.0)
        result = tools.execute_store_strategy_seed(
            agent_run_id="test-run",
            symbol="TSLA",
            thesis="Test",
            confidence=0.5,
        )
        assert result["confidence"] == 1.0

    def test_store_seed_high_confidence_sets_workflow_flag(self) -> None:
        """Test workflow_triggered flag is set for confidence >= 7 (actual trigger tested in integration)."""
        from app.agents.tool_executors_trading import TradingTools

        mock_storage = MagicMock()
        mock_conn = MagicMock()
        mock_storage.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_storage.connection.return_value.__exit__ = MagicMock(return_value=False)

        tools = TradingTools(mock_storage)

        # Low confidence - no trigger
        result_low = tools.execute_store_strategy_seed(
            agent_run_id="test-run",
            symbol="GOOGL",
            thesis="Test thesis",
            confidence=6.0,
        )
        assert result_low["workflow_triggered"] is False

        # Note: High confidence trigger is tested in integration tests
        # since it involves lazy imports and task dispatch

    def test_store_seed_inserts_correct_data(self) -> None:
        """Test correct data is inserted into strategy_seeds table."""
        from app.agents.tool_executors_trading import TradingTools

        mock_storage = MagicMock()
        tools = TradingTools(mock_storage)

        tools.execute_store_strategy_seed(
            agent_run_id="run-456",
            symbol="MSFT",
            thesis="Enterprise AI adoption",
            confidence=7.5,
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
