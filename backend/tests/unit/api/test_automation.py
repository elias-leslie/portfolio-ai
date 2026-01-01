"""Unit tests for automation pipeline API endpoints.

Tests cover:
- POST /api/automation/run/strategy-research (with/without symbol, force flag)
- POST /api/automation/run/signal-generation
- POST /api/automation/run/auto-paper-trade (with min_strength param)
- POST /api/automation/run/full-pipeline (with skip_research flag)
- GET /api/automation/status (pipeline status retrieval)
- Error handling for all endpoints
- Task triggering and response validation
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_celery_task_factory() -> callable:
    """Create factory for mock Celery task results with unique IDs."""
    counter = {"value": 0}

    def create_task() -> MagicMock:
        mock_task = MagicMock()
        counter["value"] += 1
        mock_task.id = f"test-task-id-{counter['value']:05d}"
        return mock_task

    return create_task


@pytest.fixture
def mock_celery_app(mock_celery_task_factory: callable) -> MagicMock:
    """Mock celery_app.send_task method."""
    with patch("app.api.automation.celery_app") as mock_app:
        # Return new unique task each time send_task is called
        mock_app.send_task.side_effect = lambda *args, **kwargs: mock_celery_task_factory()
        yield mock_app


@pytest.fixture
def mock_connection() -> MagicMock:
    """Mock database connection for status endpoint."""
    mock_conn = MagicMock()
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=None)
    return mock_conn


@pytest.fixture
def mock_connection_manager(mock_connection: MagicMock) -> MagicMock:
    """Mock connection manager."""
    # The import is inside the function, so patch at the storage.connection module level
    with patch("app.storage.connection.get_connection_manager") as mock_mgr:
        mock_cm = MagicMock()
        mock_cm.connection.return_value = mock_connection
        mock_mgr.return_value = mock_cm
        yield mock_mgr


# =============================================================================
# Test Strategy Research Endpoint
# =============================================================================


class TestStrategyResearchEndpoint:
    """Tests for POST /api/automation/run/strategy-research endpoint."""

    def test_trigger_strategy_research_without_symbol(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test triggering strategy research for top watchlist symbols."""
        response = client.post("/api/automation/run/strategy-research")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert data["task_id"].startswith("test-task-id-")
        assert data["stage"] == "strategy_research"
        assert "top 5 watchlist symbols" in data["message"]

        # Verify correct Celery task called
        mock_celery_app.send_task.assert_called_once()
        call_args = mock_celery_app.send_task.call_args
        assert call_args[0][0] == "app.tasks.strategy.generation_tasks.daily_strategy_refresh"
        assert call_args[1]["kwargs"]["max_symbols"] == 5

    def test_trigger_strategy_research_with_symbol(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test triggering strategy research for specific symbol."""
        response = client.post(
            "/api/automation/run/strategy-research?symbol=AAPL&force=false"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert data["task_id"].startswith("test-task-id-")
        assert data["stage"] == "strategy_research"
        assert "AAPL" in data["message"]

        # Verify correct Celery task called
        mock_celery_app.send_task.assert_called_once()
        call_args = mock_celery_app.send_task.call_args
        assert call_args[0][0] == "run_strategy_research_for_symbol"
        assert call_args[1]["args"] == ["AAPL", False]

    def test_trigger_strategy_research_with_force_flag(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test triggering strategy research with force regeneration."""
        response = client.post(
            "/api/automation/run/strategy-research?symbol=TSLA&force=true"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert data["task_id"].startswith("test-task-id-")

        # Verify force=True passed to task
        call_args = mock_celery_app.send_task.call_args
        assert call_args[1]["args"] == ["TSLA", True]

    def test_strategy_research_error_handling(self) -> None:
        """Test error handling when Celery task fails to start."""
        with patch("app.api.automation.celery_app") as mock_app:
            mock_app.send_task.side_effect = Exception("Celery unavailable")

            response = client.post("/api/automation/run/strategy-research")

            assert response.status_code == 500
            assert "Celery unavailable" in response.json()["detail"]

    def test_strategy_research_response_model_validation(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test response model matches PipelineResponse schema."""
        response = client.post("/api/automation/run/strategy-research?symbol=NVDA")

        assert response.status_code == 200
        data = response.json()

        # Validate all required fields present
        assert "status" in data
        assert "task_id" in data
        assert "stage" in data
        assert "message" in data

        # Validate field types
        assert isinstance(data["status"], str)
        assert isinstance(data["task_id"], str)
        assert isinstance(data["stage"], str)
        assert isinstance(data["message"], str)


# =============================================================================
# Test Signal Generation Endpoint
# =============================================================================


class TestSignalGenerationEndpoint:
    """Tests for POST /api/automation/run/signal-generation endpoint."""

    def test_trigger_signal_generation(self, mock_celery_app: MagicMock) -> None:
        """Test triggering signal generation for all active strategies."""
        response = client.post("/api/automation/run/signal-generation")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert data["task_id"].startswith("test-task-id-")
        assert data["stage"] == "signal_generation"
        assert "all active strategies" in data["message"]

        # Verify correct Celery task called
        mock_celery_app.send_task.assert_called_once_with(
            "app.tasks.strategy_signal_tasks.generate_daily_strategy_signals"
        )

    def test_signal_generation_error_handling(self) -> None:
        """Test error handling when signal generation task fails."""
        with patch("app.api.automation.celery_app") as mock_app:
            mock_app.send_task.side_effect = RuntimeError("Task queue full")

            response = client.post("/api/automation/run/signal-generation")

            assert response.status_code == 500
            assert "Task queue full" in response.json()["detail"]

    def test_signal_generation_response_validation(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test response model validation for signal generation."""
        response = client.post("/api/automation/run/signal-generation")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert data["stage"] == "signal_generation"
        assert isinstance(data["task_id"], str)
        assert len(data["task_id"]) > 0


# =============================================================================
# Test Auto Paper Trade Endpoint
# =============================================================================


class TestAutoPaperTradeEndpoint:
    """Tests for POST /api/automation/run/auto-paper-trade endpoint."""

    def test_trigger_auto_paper_trade_default_strength(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test triggering auto paper trade with default min_strength=5."""
        response = client.post("/api/automation/run/auto-paper-trade")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert data["task_id"].startswith("test-task-id-")
        assert data["stage"] == "auto_paper_trade"
        assert "min strength: 5" in data["message"]

        # Verify correct Celery task called with default strength
        mock_celery_app.send_task.assert_called_once()
        call_args = mock_celery_app.send_task.call_args
        assert call_args[0][0] == "app.tasks.strategy_signal_tasks.auto_paper_trade_from_signals"
        assert call_args[1]["kwargs"]["min_signal_strength"] == 5

    def test_trigger_auto_paper_trade_custom_strength(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test triggering auto paper trade with custom min_strength."""
        response = client.post("/api/automation/run/auto-paper-trade?min_strength=8")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert "min strength: 8" in data["message"]

        # Verify custom strength passed to task
        call_args = mock_celery_app.send_task.call_args
        assert call_args[1]["kwargs"]["min_signal_strength"] == 8

    def test_auto_paper_trade_strength_validation_min(self) -> None:
        """Test min_strength validation rejects values < 1."""
        response = client.post("/api/automation/run/auto-paper-trade?min_strength=0")

        assert response.status_code == 422  # Validation error

    def test_auto_paper_trade_strength_validation_max(self) -> None:
        """Test min_strength validation rejects values > 10."""
        response = client.post("/api/automation/run/auto-paper-trade?min_strength=11")

        assert response.status_code == 422  # Validation error

    def test_auto_paper_trade_strength_boundary_values(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test min_strength boundary values (1 and 10) are accepted."""
        # Test min boundary
        response = client.post("/api/automation/run/auto-paper-trade?min_strength=1")
        assert response.status_code == 200

        # Test max boundary
        response = client.post("/api/automation/run/auto-paper-trade?min_strength=10")
        assert response.status_code == 200

    def test_auto_paper_trade_error_handling(self) -> None:
        """Test error handling when auto paper trade task fails."""
        with patch("app.api.automation.celery_app") as mock_app:
            mock_app.send_task.side_effect = ConnectionError("Redis connection failed")

            response = client.post("/api/automation/run/auto-paper-trade")

            assert response.status_code == 500
            assert "Redis connection failed" in response.json()["detail"]


# =============================================================================
# Test Full Pipeline Endpoint
# =============================================================================


class TestFullPipelineEndpoint:
    """Tests for POST /api/automation/run/full-pipeline endpoint."""

    def test_trigger_full_pipeline_all_stages(self, mock_celery_app: MagicMock) -> None:
        """Test triggering full pipeline with all stages."""
        response = client.post("/api/automation/run/full-pipeline")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert data["message"] == "Started 3 pipeline stages"
        assert "stages" in data

        # Verify all 3 stages present
        stages = data["stages"]
        assert "strategy_research" in stages
        assert "signal_generation" in stages
        assert "auto_paper_trade" in stages

        # Verify each stage has task_id and status
        for stage_name, stage_data in stages.items():
            assert "task_id" in stage_data
            assert stage_data["status"] == "started"

        # Verify 3 Celery tasks called
        assert mock_celery_app.send_task.call_count == 3

    def test_trigger_full_pipeline_skip_research(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test triggering full pipeline with skip_research=true."""
        response = client.post("/api/automation/run/full-pipeline?skip_research=true")

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert data["message"] == "Started 2 pipeline stages"

        # Verify only 2 stages present (no strategy_research)
        stages = data["stages"]
        assert "strategy_research" not in stages
        assert "signal_generation" in stages
        assert "auto_paper_trade" in stages

        # Verify only 2 Celery tasks called
        assert mock_celery_app.send_task.call_count == 2

    def test_full_pipeline_task_order(self, mock_celery_app: MagicMock) -> None:
        """Test full pipeline tasks called in correct order."""
        response = client.post("/api/automation/run/full-pipeline")

        assert response.status_code == 200

        # Verify task call order
        calls = mock_celery_app.send_task.call_args_list
        assert len(calls) == 3

        # Order: strategy_research, signal_generation, auto_paper_trade
        assert "daily_strategy_refresh" in calls[0][0][0]
        assert "generate_daily_strategy_signals" in calls[1][0][0]
        assert "auto_paper_trade_from_signals" in calls[2][0][0]

    def test_full_pipeline_error_handling(self) -> None:
        """Test error handling when pipeline task fails to start."""
        with patch("app.api.automation.celery_app") as mock_app:
            # First task succeeds, second fails
            mock_app.send_task.side_effect = [
                MagicMock(id="task-1"),
                ValueError("Invalid task config"),
            ]

            response = client.post("/api/automation/run/full-pipeline")

            assert response.status_code == 500
            assert "Invalid task config" in response.json()["detail"]

    def test_full_pipeline_response_structure(
        self, mock_celery_app: MagicMock
    ) -> None:
        """Test full pipeline response structure validation."""
        response = client.post("/api/automation/run/full-pipeline")

        assert response.status_code == 200
        data = response.json()

        # Validate top-level fields
        assert isinstance(data["status"], str)
        assert isinstance(data["message"], str)
        assert isinstance(data["stages"], dict)

        # Validate stages structure
        for stage_name, stage_data in data["stages"].items():
            assert isinstance(stage_name, str)
            assert isinstance(stage_data, dict)
            assert "task_id" in stage_data
            assert "status" in stage_data


# =============================================================================
# Test Pipeline Status Endpoint
# =============================================================================


class TestPipelineStatusEndpoint:
    """Tests for GET /api/automation/status endpoint."""

    def test_get_pipeline_status_success(
        self, mock_connection_manager: MagicMock, mock_connection: MagicMock
    ) -> None:
        """Test successful pipeline status retrieval."""
        from datetime import datetime

        # Mock database query results - use datetime object for last_backtest
        mock_dt = datetime(2025, 12, 11, 10, 30, 0)
        mock_connection.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=(10,))),  # active_strategies
            MagicMock(fetchone=MagicMock(return_value=(5,))),  # today_signals
            MagicMock(fetchone=MagicMock(return_value=(3,))),  # open_trades
            MagicMock(
                fetchone=MagicMock(return_value=(mock_dt,))
            ),  # last_backtest (datetime object)
        ]

        response = client.get("/api/automation/status")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "stages" in data
        assert "last_run" in data

        # Validate stages data
        stages = data["stages"]
        assert stages["strategies"]["active_count"] == 10
        assert stages["signals"]["today_count"] == 5
        assert stages["paper_trades"]["open_count"] == 3

        # Validate last_run data
        assert data["last_run"]["backtest"] == "2025-12-11T10:30:00"

    def test_get_pipeline_status_null_counts(
        self, mock_connection_manager: MagicMock, mock_connection: MagicMock
    ) -> None:
        """Test pipeline status handles NULL/empty database results."""
        # Mock database query results with None values
        mock_connection.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=None)),  # No strategies
            MagicMock(fetchone=MagicMock(return_value=(0,))),  # 0 signals
            MagicMock(fetchone=MagicMock(return_value=(0,))),  # 0 trades
            MagicMock(fetchone=MagicMock(return_value=(None,))),  # No backtest
        ]

        response = client.get("/api/automation/status")

        assert response.status_code == 200
        data = response.json()

        # Validate defaults for NULL results
        assert data["stages"]["strategies"]["active_count"] == 0
        assert data["stages"]["signals"]["today_count"] == 0
        assert data["stages"]["paper_trades"]["open_count"] == 0
        assert data["last_run"]["backtest"] is None

    def test_get_pipeline_status_datetime_conversion(
        self, mock_connection_manager: MagicMock, mock_connection: MagicMock
    ) -> None:
        """Test pipeline status handles datetime objects correctly."""
        from datetime import datetime

        # Mock datetime object from database
        mock_dt = datetime(2025, 12, 11, 14, 30, 0)
        mock_connection.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=(5,))),
            MagicMock(fetchone=MagicMock(return_value=(2,))),
            MagicMock(fetchone=MagicMock(return_value=(1,))),
            MagicMock(fetchone=MagicMock(return_value=(mock_dt,))),
        ]

        response = client.get("/api/automation/status")

        assert response.status_code == 200
        data = response.json()

        # Verify datetime converted to ISO format string
        assert data["last_run"]["backtest"] == "2025-12-11T14:30:00"

    def test_get_pipeline_status_database_error(self) -> None:
        """Test error handling when database query fails."""
        with patch("app.storage.connection.get_connection_manager") as mock_mgr:
            mock_mgr.side_effect = ConnectionError("Database unavailable")

            response = client.get("/api/automation/status")

            assert response.status_code == 500
            assert "Database unavailable" in response.json()["detail"]

    def test_pipeline_status_response_model_validation(
        self, mock_connection_manager: MagicMock, mock_connection: MagicMock
    ) -> None:
        """Test pipeline status response matches PipelineStatusResponse schema."""
        mock_connection.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=(8,))),
            MagicMock(fetchone=MagicMock(return_value=(12,))),
            MagicMock(fetchone=MagicMock(return_value=(4,))),
            MagicMock(fetchone=MagicMock(return_value=("2025-12-11T09:00:00",))),
        ]

        response = client.get("/api/automation/status")

        assert response.status_code == 200
        data = response.json()

        # Validate required fields and types
        assert isinstance(data["stages"], dict)
        assert isinstance(data["last_run"], dict)

        # Validate stages structure
        assert "strategies" in data["stages"]
        assert "signals" in data["stages"]
        assert "paper_trades" in data["stages"]

        # Validate last_run structure
        assert "backtest" in data["last_run"]


# =============================================================================
# Integration Tests (Cross-Endpoint)
# =============================================================================


class TestAutomationPipelineIntegration:
    """Integration tests for automation pipeline workflow."""

    def test_full_pipeline_workflow_simulation(
        self, mock_celery_app: MagicMock, mock_connection_manager: MagicMock
    ) -> None:
        """Test simulated full pipeline workflow: trigger → check status."""
        # Mock connection for status endpoint
        mock_conn = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=None)
        mock_conn.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=(5,))),
            MagicMock(fetchone=MagicMock(return_value=(10,))),
            MagicMock(fetchone=MagicMock(return_value=(2,))),
            MagicMock(fetchone=MagicMock(return_value=(None,))),
        ]

        mock_connection_manager.return_value.connection.return_value = mock_conn

        # Step 1: Trigger full pipeline
        trigger_response = client.post("/api/automation/run/full-pipeline")
        assert trigger_response.status_code == 200
        trigger_data = trigger_response.json()
        assert len(trigger_data["stages"]) == 3

        # Step 2: Check pipeline status
        status_response = client.get("/api/automation/status")
        assert status_response.status_code == 200
        status_data = status_response.json()

        # Verify status reflects activity
        assert status_data["stages"]["strategies"]["active_count"] == 5
        assert status_data["stages"]["signals"]["today_count"] == 10
        assert status_data["stages"]["paper_trades"]["open_count"] == 2

    def test_individual_stage_triggers(self, mock_celery_app: MagicMock) -> None:
        """Test triggering individual pipeline stages independently."""
        # Trigger each stage independently
        response1 = client.post("/api/automation/run/strategy-research?symbol=AAPL")
        response2 = client.post("/api/automation/run/signal-generation")
        response3 = client.post("/api/automation/run/auto-paper-trade?min_strength=7")

        # Verify all stages triggered successfully
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

        # Verify correct number of Celery tasks dispatched
        assert mock_celery_app.send_task.call_count == 3

        # Verify each returned task IDs (should be unique due to factory)
        task_ids = [
            response1.json()["task_id"],
            response2.json()["task_id"],
            response3.json()["task_id"],
        ]
        # All should have task IDs
        assert all(task_id.startswith("test-task-id-") for task_id in task_ids)
        # All should be unique
        assert len(set(task_ids)) == 3
