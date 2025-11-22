"""Unit tests for StrategyStorage."""

import json
import uuid
from unittest.mock import Mock, patch

import pytest

from app.strategies.storage import StrategyStorage


@pytest.fixture
def mock_connection():
    """Create mock database connection with execute method."""
    conn = Mock()
    # Mock execute() to return self for chaining
    conn.execute.return_value = conn
    # Mock fetchall() and fetchone()
    conn.fetchall.return_value = []
    conn.fetchone.return_value = None
    return conn


@pytest.fixture
def mock_connection_manager(mock_connection):
    """Create mock ConnectionManager with connection() context manager."""
    manager = Mock()
    # Make connection() return a context manager that yields mock_connection
    manager.connection.return_value.__enter__ = Mock(return_value=mock_connection)
    manager.connection.return_value.__exit__ = Mock(return_value=False)
    return manager


@pytest.fixture
def storage(mock_connection_manager):
    """Create StrategyStorage with mock ConnectionManager."""
    with patch(
        "app.strategies.storage.get_connection_manager", return_value=mock_connection_manager
    ):
        return StrategyStorage()


@pytest.fixture
def sample_parameters():
    """Create sample strategy parameters."""
    return {
        "weight_price_trend": 0.20,
        "weight_rsi_health": 0.10,
        "weight_momentum": 0.25,
        "weight_volume": 0.10,
        "weight_fundamentals": 0.15,
        "weight_news_sentiment": 0.15,
        "weight_sector_alignment": 0.05,
        "min_confirmations": 6,
        "min_weighted_score": 0.65,
        "stop_loss_atr_multiplier": 2.0,
        "max_holding_days": 60,
        "position_sizing_method": "fixed_dollars",
        "position_size_value": 10000.00,
    }


@pytest.fixture
def sample_research_summary():
    """Create sample research summary."""
    return {
        "symbol": "AAPL",
        "overall_confidence": 0.85,
        "news_sentiment_score": 0.6,
        "company_health": "EXCELLENT",
        "trend_strength": "strong_up",
    }


@pytest.fixture
def sample_backtest_metrics():
    """Create sample backtest metrics."""
    return [
        {"sharpe_ratio": 1.5, "win_rate": 0.60, "max_drawdown": 0.15},
        {"sharpe_ratio": 1.4, "win_rate": 0.58, "max_drawdown": 0.16},
    ]


class TestStrategyStorage:
    """Test suite for StrategyStorage."""

    def test_initialization(self, storage, mock_connection_manager):
        """Test storage initialization."""
        assert storage.conn is not None
        assert storage.conn == mock_connection_manager

    def test_store_strategy_creates_new_record(
        self,
        storage,
        mock_connection_manager,
        sample_parameters,
        sample_research_summary,
        sample_backtest_metrics,
    ):
        """Test storing a new strategy."""
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        # Mock version query
        mock_connection.execute.return_value = mock_connection
        mock_connection.fetchall.return_value = [(1,)]

        strategy_id = storage.store_strategy(
            symbol="AAPL",
            strategy_type="momentum",
            parameters=sample_parameters,
            research_summary=sample_research_summary,
            generation_reasoning="Strong momentum with positive fundamentals.",
            backtest_metrics=sample_backtest_metrics,
            expected_sharpe=1.45,
            expected_win_rate=0.59,
            expected_max_drawdown=0.155,
            created_by="workflow:test-123",
            status="testing",
        )

        # Verify strategy_id is valid UUID
        assert uuid.UUID(strategy_id)

        # Verify execute was called with INSERT statement
        assert mock_connection.execute.called
        call_args = mock_connection.execute.call_args_list[-1]
        query = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT INTO strategy_definitions" in query
        assert params[2] == "AAPL"  # symbol
        assert params[3] == "momentum"  # strategy_type

    def test_store_strategy_generates_unique_name(self, storage, mock_connection_manager):
        """Test strategy name generation."""
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        mock_connection.execute.return_value = mock_connection
        mock_connection.fetchall.return_value = [(1,)]

        # Store multiple strategies for same symbol
        storage.store_strategy(
            symbol="AAPL",
            strategy_type="momentum",
            parameters={},
            research_summary={},
            generation_reasoning="Test 1",
            backtest_metrics=[],
            expected_sharpe=1.0,
            expected_win_rate=0.5,
            expected_max_drawdown=0.2,
            created_by="test",
        )

        # Verify name was generated
        call_args = mock_connection.execute.call_args_list[-1]
        name = call_args[0][1][1]  # Second parameter is name
        assert "AAPL" in name
        assert "Momentum" in name  # Name is capitalized in _generate_strategy_name

    def test_store_strategy_increments_version(self, storage, mock_connection_manager):
        """Test version incrementing for same strategy."""
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        # First call returns version 1, second returns version 2
        mock_connection.execute.return_value = mock_connection
        mock_connection.fetchall.side_effect = [[(1,)], [(2,)]]

        # Store first version
        storage.store_strategy(
            symbol="AAPL",
            strategy_type="momentum",
            parameters={},
            research_summary={},
            generation_reasoning="Version 1",
            backtest_metrics=[],
            expected_sharpe=1.0,
            expected_win_rate=0.5,
            expected_max_drawdown=0.2,
            created_by="test",
        )

        # Store second version
        storage.store_strategy(
            symbol="AAPL",
            strategy_type="momentum",
            parameters={},
            research_summary={},
            generation_reasoning="Version 2",
            backtest_metrics=[],
            expected_sharpe=1.2,
            expected_win_rate=0.55,
            expected_max_drawdown=0.18,
            created_by="test",
        )

        # Verify versions were queried
        assert mock_connection.execute.call_count == 4

    def test_store_strategy_serializes_jsonb_fields(
        self,
        storage,
        mock_connection_manager,
        sample_parameters,
        sample_research_summary,
        sample_backtest_metrics,
    ):
        """Test JSONB field serialization."""
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        mock_connection.execute.return_value = mock_connection
        mock_connection.fetchall.return_value = [(1,)]

        storage.store_strategy(
            symbol="AAPL",
            strategy_type="momentum",
            parameters=sample_parameters,
            research_summary=sample_research_summary,
            generation_reasoning="Test",
            backtest_metrics=sample_backtest_metrics,
            expected_sharpe=1.5,
            expected_win_rate=0.6,
            expected_max_drawdown=0.15,
            created_by="test",
        )

        call_args = mock_connection.execute.call_args_list[-1]
        params = call_args[0][1]

        # Parameters should be JSON string
        parameters_json = params[4]
        assert isinstance(parameters_json, str)
        parameters_dict = json.loads(parameters_json)
        assert parameters_dict["weight_momentum"] == 0.25

        # Research summary should be JSON string
        research_json = params[5]
        assert isinstance(research_json, str)
        research_dict = json.loads(research_json)
        assert research_dict["symbol"] == "AAPL"

        # Backtest metrics should be JSON string
        backtest_json = params[7]
        assert isinstance(backtest_json, str)
        backtest_list = json.loads(backtest_json)
        assert len(backtest_list) == 2

    def test_get_strategy_by_id(self, storage, mock_connection_manager):
        """Test retrieving strategy by ID."""
        strategy_id = str(uuid.uuid4())
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value

        # Mock query result - tuple order must match _convert_row column_names
        # Column order from _convert_row: id, name, symbol, strategy_type, parameters, research_summary,
        # generation_reasoning, backtest_metrics, expected_sharpe, expected_win_rate,
        # expected_max_drawdown, created_by, version, status, created_at, activation_date,
        # archive_date, archive_reason, live_trades_count, live_win_rate, live_sharpe_ratio, last_used_at
        mock_connection.execute.return_value = mock_connection
        mock_connection.fetchall.return_value = [
            (
                strategy_id,  # id
                "AAPL_Momentum_2025Q4",  # name
                "AAPL",  # symbol
                "momentum",  # strategy_type
                {"weight_momentum": 0.25},  # parameters (dict)
                {"symbol": "AAPL"},  # research_summary (dict)
                "Test reasoning",  # generation_reasoning
                {"sharpe_ratio": 1.5, "win_rate": 0.6},  # backtest_metrics (dict)
                1.5,  # expected_sharpe
                0.6,  # expected_win_rate
                0.15,  # expected_max_drawdown
                "workflow:test",  # created_by
                1,  # version
                "active",  # status
                "2024-11-20 10:00:00",  # created_at
                "2024-11-20 11:00:00",  # activation_date
                None,  # archive_date
                None,  # archive_reason
                10,  # live_trades_count
                0.62,  # live_win_rate
                1.48,  # live_sharpe_ratio
                "2024-11-20 12:00:00",  # last_used_at
            )
        ]

        result = storage.get_strategy_by_id(strategy_id)

        # Verify query was executed
        assert mock_connection.execute.called
        call_args = mock_connection.execute.call_args[0]
        query = call_args[0]
        assert "SELECT" in query
        assert "WHERE id = %s" in query

        # Verify result structure
        assert result is not None
        assert result.id == strategy_id
        assert result.symbol == "AAPL"
        assert result.strategy_type == "momentum"

    def test_get_strategy_by_id_not_found(self, storage, mock_connection_manager):
        """Test get_strategy_by_id when strategy doesn't exist."""
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        mock_connection.execute.return_value = mock_connection
        mock_connection.fetchall.return_value = []

        result = storage.get_strategy_by_id("nonexistent-id")

        assert result is None

    def test_list_strategies_for_symbol(self, storage, mock_connection_manager):
        """Test listing all strategies for a symbol."""
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        # Mock query result with multiple strategies
        mock_connection.execute.return_value = mock_connection
        id1, id2 = str(uuid.uuid4()), str(uuid.uuid4())
        mock_connection.fetchall.return_value = [
            (
                id1,  # id
                "AAPL_Momentum_2025Q4",  # name
                "AAPL",  # symbol
                "momentum",  # strategy_type
                {},  # parameters (dict)
                {},  # research_summary (dict)
                "Test 1",  # generation_reasoning
                {},  # backtest_metrics (dict)
                1.5,  # expected_sharpe
                0.6,  # expected_win_rate
                0.15,  # expected_max_drawdown
                "test",  # created_by
                1,  # version
                "active",  # status
                "2024-11-20 10:00:00",  # created_at
                None,  # activation_date
                None,  # archive_date
                None,  # archive_reason
                0,  # live_trades_count
                None,  # live_win_rate
                None,  # live_sharpe_ratio
                None,  # last_used_at
            ),
            (
                id2,  # id
                "AAPL_Value_2025Q4",  # name
                "AAPL",  # symbol
                "value",  # strategy_type
                {},  # parameters (dict)
                {},  # research_summary (dict)
                "Test 2",  # generation_reasoning
                {},  # backtest_metrics (dict)
                1.3,  # expected_sharpe
                0.58,  # expected_win_rate
                0.18,  # expected_max_drawdown
                "test",  # created_by
                1,  # version
                "testing",  # status
                "2024-11-21 10:00:00",  # created_at
                None,  # activation_date
                None,  # archive_date
                None,  # archive_reason
                0,  # live_trades_count
                None,  # live_win_rate
                None,  # live_sharpe_ratio
                None,  # last_used_at
            ),
        ]

        result = storage.list_strategies(symbol="AAPL")

        # Verify query
        assert mock_connection.execute.called
        call_args = mock_connection.execute.call_args[0]
        query = call_args[0]
        assert "WHERE symbol = %s" in query

        # Verify results
        assert len(result) == 2
        assert result[0].strategy_type == "momentum"
        assert result[1].strategy_type == "value"

    def test_list_active_strategies(self, storage, mock_connection_manager):
        """Test listing only active strategies."""
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        # Mock query result
        mock_connection.execute.return_value = mock_connection
        strategy_id = str(uuid.uuid4())
        mock_connection.fetchall.return_value = [
            (
                strategy_id,  # id
                "AAPL_Momentum_2025Q4",  # name
                "AAPL",  # symbol
                "momentum",  # strategy_type
                {},  # parameters (dict)
                {},  # research_summary (dict)
                "Test",  # generation_reasoning
                {},  # backtest_metrics (dict)
                1.5,  # expected_sharpe
                0.6,  # expected_win_rate
                0.15,  # expected_max_drawdown
                "test",  # created_by
                1,  # version
                "active",  # status
                "2024-11-20 10:00:00",  # created_at
                "2024-11-20 10:00:00",  # activation_date
                None,  # archive_date
                None,  # archive_reason
                5,  # live_trades_count
                0.61,  # live_win_rate
                1.52,  # live_sharpe_ratio
                "2024-11-21 10:00:00",  # last_used_at
            )
        ]

        result = storage.list_strategies(status="active")

        # Verify query filters for active status
        call_args = mock_connection.execute.call_args[0]
        query = call_args[0]
        assert "WHERE status = %s" in query

        # Verify result
        assert len(result) == 1
        assert result[0].status == "active"

    def test_activate_strategy(self, storage, mock_connection_manager):
        """Test activating a strategy."""
        strategy_id = str(uuid.uuid4())
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        mock_connection.execute.return_value = mock_connection

        storage.activate_strategy(strategy_id)

        # Verify UPDATE query
        assert mock_connection.execute.called
        call_args = mock_connection.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "UPDATE strategy_definitions" in query
        assert "SET status = 'active'" in query
        assert params[0] == strategy_id

    def test_archive_strategy(self, storage, mock_connection_manager):
        """Test archiving a strategy."""
        strategy_id = str(uuid.uuid4())
        reason = "Underperformed expectations"
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        mock_connection.execute.return_value = mock_connection

        storage.archive_strategy(strategy_id, reason)

        # Verify UPDATE query
        call_args = mock_connection.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "UPDATE strategy_definitions" in query
        assert "SET status = 'archived'" in query
        assert reason in params

    def test_update_live_performance(self, storage, mock_connection_manager):
        """Test updating live performance metrics."""
        strategy_id = str(uuid.uuid4())
        mock_connection = mock_connection_manager.connection.return_value.__enter__.return_value
        mock_connection.execute.return_value = mock_connection

        storage.update_live_performance(
            strategy_id=strategy_id, trades_count=10, win_rate=0.62, sharpe_ratio=1.48
        )

        # Verify UPDATE query
        call_args = mock_connection.execute.call_args[0]
        query = call_args[0]
        params = call_args[1]

        assert "UPDATE strategy_definitions" in query
        assert "live_trades_count" in query
        assert "live_win_rate" in query
        assert "live_sharpe_ratio" in query
        assert params[0] == 10
        assert params[1] == 0.62
        assert params[2] == 1.48
