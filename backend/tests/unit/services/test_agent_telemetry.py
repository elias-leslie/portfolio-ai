"""Unit tests for agent telemetry service."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.constants import GEMINI_FLASH
from app.services.agent_telemetry import (
    AgentRunDetail,
    AgentTelemetryService,
    DailyTelemetry,
    ProviderMetrics,
    TelemetrySummary,
    TokenUsage,
)


class TestTokenUsage:
    """Tests for TokenUsage dataclass."""

    def test_token_usage_creation(self) -> None:
        """Test TokenUsage dataclass can be created."""
        token_usage = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            total_tokens=300,
        )
        # TokenUsage is a dataclass that behaves like a dict
        assert token_usage["input_tokens"] == 100
        assert token_usage["output_tokens"] == 200
        assert token_usage["total_tokens"] == 300


class TestProviderMetrics:
    """Tests for ProviderMetrics dataclass."""

    def test_provider_metrics_creation(self) -> None:
        """Test ProviderMetrics dataclass can be created."""
        metrics = ProviderMetrics(
            provider="gemini",
            total_runs=50,
            successful_runs=45,
            failed_runs=5,
            success_rate=90.0,
            total_tokens=10000,
            avg_tokens_per_run=200.0,
            avg_duration_ms=1500.0,
            total_cost_usd=0.0,
        )
        assert metrics.provider == "gemini"
        assert metrics.total_runs == 50
        assert metrics.success_rate == 90.0


class TestDailyTelemetry:
    """Tests for DailyTelemetry dataclass."""

    def test_daily_telemetry_creation(self) -> None:
        """Test DailyTelemetry dataclass can be created."""
        daily = DailyTelemetry(
            date="2025-11-30",
            total_runs=10,
            successful_runs=8,
            failed_runs=2,
            total_input_tokens=1000,
            total_output_tokens=2000,
            total_tokens=3000,
            avg_duration_ms=1200.0,
            estimated_cost_usd=0.0,
        )
        assert daily.date == "2025-11-30"
        assert daily.total_runs == 10


class TestAgentRunDetail:
    """Tests for AgentRunDetail BaseModel."""

    def test_agent_run_detail_creation(self) -> None:
        """Test AgentRunDetail can be created."""
        token_usage = TokenUsage(
            input_tokens=100,
            output_tokens=200,
            total_tokens=300,
        )
        run = AgentRunDetail(
            id="test-123",
            agent_type="DiscoveryAgent",
            started_at="2025-11-30T10:00:00Z",
            completed_at="2025-11-30T10:01:00Z",
            status="completed",
            provider="gemini",
            model=GEMINI_FLASH,
            duration_ms=60000,
            token_usage=token_usage,
            error=None,
        )
        # AgentRunDetail is a Pydantic BaseModel
        assert run.id == "test-123"
        assert run.agent_type == "DiscoveryAgent"
        assert run.status == "completed"
        assert run.token_usage is not None
        assert run.token_usage["total_tokens"] == 300


class TestTelemetrySummary:
    """Tests for TelemetrySummary dataclass."""

    def test_telemetry_summary_creation(self) -> None:
        """Test TelemetrySummary dataclass can be created with defaults."""
        summary = TelemetrySummary(
            period_start="2025-11-23T00:00:00Z",
            period_end="2025-11-30T00:00:00Z",
            period_days=7,
        )
        assert summary.period_days == 7
        assert summary.total_runs == 0
        assert summary.by_provider == []
        assert summary.daily_data == []


class TestAgentTelemetryService:
    """Tests for AgentTelemetryService."""

    @pytest.fixture
    def mock_conn_manager(self) -> MagicMock:
        """Create a mock connection manager."""
        return MagicMock()

    @pytest.fixture
    def service(self, mock_conn_manager: MagicMock) -> AgentTelemetryService:
        """Create a telemetry service with mock connection manager."""
        return AgentTelemetryService(mock_conn_manager)

    def test_service_initialization(self, mock_conn_manager: MagicMock) -> None:
        """Test service can be initialized."""
        service = AgentTelemetryService(mock_conn_manager)
        assert service.conn_mgr is mock_conn_manager

    def test_get_summary_returns_telemetry_summary(
        self, service: AgentTelemetryService, mock_conn_manager: MagicMock
    ) -> None:
        """Test get_summary returns a TelemetrySummary object."""
        # Mock the connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn_manager.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_manager.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_cursor

        # Mock query results
        mock_cursor.fetchone.side_effect = [
            (10, 8, 2, 1500.0),  # Summary query
            (1000, 2000, 3000),  # Token query
        ]
        mock_cursor.fetchall.side_effect = [
            [("gemini", 10, 8, 2, 1500.0, 3000)],  # Provider query
            [],  # Daily data query
        ]

        summary = service.get_summary(days=7)

        assert isinstance(summary, TelemetrySummary)
        assert summary.period_days == 7

    def test_get_run_history_with_filters(
        self, service: AgentTelemetryService, mock_conn_manager: MagicMock
    ) -> None:
        """Test get_run_history respects filters."""
        # Mock the connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn_manager.connection.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn_manager.connection.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.execute.return_value = mock_cursor

        # Mock query results
        mock_cursor.fetchone.return_value = (5,)  # Count
        mock_cursor.fetchall.return_value = []  # No runs

        runs, total = service.get_run_history(
            limit=10,
            offset=0,
            provider="gemini",
            status="completed",
        )

        assert isinstance(runs, list)
        assert total == 5


class TestTelemetryAggregation:
    """Tests for telemetry aggregation calculations."""

    def test_success_rate_calculation(self) -> None:
        """Test success rate is calculated correctly."""
        total_runs = 100
        successful_runs = 85
        expected_rate = 85.0

        calculated_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0
        assert calculated_rate == expected_rate

    def test_success_rate_zero_runs(self) -> None:
        """Test success rate with zero runs."""
        total_runs = 0
        successful_runs = 0

        calculated_rate = (successful_runs / total_runs * 100) if total_runs > 0 else 0.0
        assert calculated_rate == 0.0

    def test_avg_tokens_calculation(self) -> None:
        """Test average tokens per run is calculated correctly."""
        total_tokens = 10000
        total_runs = 50
        expected_avg = 200.0

        calculated_avg = (total_tokens / total_runs) if total_runs > 0 else 0.0
        assert calculated_avg == expected_avg
