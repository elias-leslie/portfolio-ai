"""Unit tests for Rules Validation Tasks (FEAT-008).

Tests cover:
1. daily_rules_validation task execution
2. weekly_optimization_review task execution
3. Database storage of validation reports
4. Error logging and alerting
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.agents.rules_validator_agent import (
    Recommendation,
    ValidationError,
    ValidationReport,
)
from app.tasks.rules_validation_tasks import (
    _get_recent_performance_data,
    daily_rules_validation,
    weekly_optimization_review,
)


@pytest.fixture
def mock_validation_report() -> ValidationReport:
    """Create a mock validation report."""
    return ValidationReport(
        timestamp=datetime.now(UTC),
        rules_version="1.0.0",
        overall_status="valid",
        errors=[],
        recommendations=[],
        summary="All validation checks passed",
    )


@pytest.fixture
def mock_validation_report_with_errors() -> ValidationReport:
    """Create a mock validation report with errors."""
    return ValidationReport(
        timestamp=datetime.now(UTC),
        rules_version="1.0.0",
        overall_status="critical",
        errors=[
            ValidationError(
                severity="critical",
                category="threshold_range",
                field_path="technical_thresholds.rsi_oversold",
                message="RSI oversold out of range",
                current_value=150,
                expected_range="0-100",
            ),
            ValidationError(
                severity="warning",
                category="fee_assumptions",
                field_path="fees.commission_per_share",
                message="Zero commission unrealistic",
                current_value=0,
            ),
        ],
        recommendations=[],
        summary="Found: 1 critical error(s), 1 warning(s)",
    )


@pytest.fixture
def mock_recommendations() -> list[Recommendation]:
    """Create mock optimization recommendations."""
    return [
        Recommendation(
            priority="high",
            category="technical_thresholds",
            field_path="technical_thresholds.rsi_oversold",
            recommendation="Raise RSI oversold threshold",
            rationale="Current value 20 may trigger too rarely",
            suggested_value=30,
        ),
        Recommendation(
            priority="medium",
            category="position_sizing",
            field_path="position_sizing.max_position_percent",
            recommendation="Increase max position size",
            rationale="Current 3% limits diversification",
            suggested_value=0.10,
        ),
    ]


class TestDailyRulesValidation:
    """Test daily_rules_validation task."""

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_daily_validation_success(
        self,
        mock_agent_class: MagicMock,
        mock_conn_mgr: MagicMock,
        mock_validation_report: ValidationReport,
    ) -> None:
        """Daily validation should store report and return success."""
        # Setup mocks
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent

        # Mock async validate_rules to return sync result
        async def mock_validate() -> ValidationReport:
            return mock_validation_report

        with patch("asyncio.run", return_value=mock_validation_report):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

            # Execute task
            result = daily_rules_validation()

            # Verify database insert was called
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0]
            assert "INSERT INTO rules_validation_reports" in call_args[0]

            # Verify return value
            assert result["status"] == "valid"
            assert result["rules_version"] == "1.0.0"
            assert result["error_count"] == 0

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_daily_validation_with_warnings(
        self,
        mock_agent_class: MagicMock,
        mock_conn_mgr: MagicMock,
    ) -> None:
        """Daily validation with warnings should log warning."""
        report = ValidationReport(
            timestamp=datetime.now(UTC),
            rules_version="1.0.0",
            overall_status="warnings",
            errors=[
                ValidationError(
                    severity="warning",
                    category="fee_assumptions",
                    field_path="fees.commission_per_share",
                    message="Zero commission unrealistic",
                    current_value=0,
                )
            ],
            recommendations=[],
            summary="Found: 1 warning(s)",
        )

        with patch("asyncio.run", return_value=report):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

            result = daily_rules_validation()

            assert result["status"] == "warnings"
            assert result["error_count"] == 1

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_daily_validation_with_critical_errors(
        self,
        mock_agent_class: MagicMock,
        mock_conn_mgr: MagicMock,
        mock_validation_report_with_errors: ValidationReport,
    ) -> None:
        """Daily validation with critical errors should log error and alert."""
        with patch("asyncio.run", return_value=mock_validation_report_with_errors):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

            result = daily_rules_validation()

            # Verify critical status returned
            assert result["status"] == "critical"
            assert result["error_count"] == 2

            # Verify maintenance_log insert was called
            assert mock_cursor.execute.call_count == 2  # validation report + alert
            maintenance_call = mock_cursor.execute.call_args_list[1][0]
            assert "INSERT INTO maintenance_log" in maintenance_call[0]
            assert "critical_failure" in maintenance_call[1]

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_daily_validation_stores_errors_as_json(
        self,
        mock_agent_class: MagicMock,
        mock_conn_mgr: MagicMock,
        mock_validation_report_with_errors: ValidationReport,
    ) -> None:
        """Daily validation should store errors as JSONB."""
        with patch("asyncio.run", return_value=mock_validation_report_with_errors):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

            daily_rules_validation()

            # Verify JSON serialization of errors
            call_args = mock_cursor.execute.call_args_list[0][0]
            # Check that Json() was used (from psycopg2.extras)
            from psycopg2.extras import Json

            params = call_args[1]
            validation_errors_param = params[6]
            assert isinstance(validation_errors_param, Json)

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_daily_validation_handles_exception(
        self, mock_agent_class: MagicMock, mock_conn_mgr: MagicMock
    ) -> None:
        """Daily validation should handle exceptions gracefully."""
        with patch("asyncio.run", side_effect=Exception("Validation failed")):
            result = daily_rules_validation()

            assert result["status"] == "error"
            assert "error" in result
            assert "Validation failed" in result["error"]

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_daily_validation_counts_errors_by_severity(
        self,
        mock_agent_class: MagicMock,
        mock_conn_mgr: MagicMock,
        mock_validation_report_with_errors: ValidationReport,
    ) -> None:
        """Daily validation should count errors by severity."""
        with patch("asyncio.run", return_value=mock_validation_report_with_errors):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

            daily_rules_validation()

            # Check that critical_count and warning_count were calculated correctly
            call_args = mock_cursor.execute.call_args_list[0][0]
            params = call_args[1]
            critical_count = params[3]
            warning_count = params[4]
            info_count = params[5]

            assert critical_count == 1
            assert warning_count == 1
            assert info_count == 0


class TestWeeklyOptimizationReview:
    """Test weekly_optimization_review task."""

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks._get_recent_performance_data")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_weekly_optimization_success(
        self,
        mock_agent_class: MagicMock,
        mock_perf_data: MagicMock,
        mock_conn_mgr: MagicMock,
        mock_recommendations: list[Recommendation],
    ) -> None:
        """Weekly optimization should store recommendations."""
        mock_agent = MagicMock()
        mock_agent_class.return_value = mock_agent
        mock_perf_data.return_value = {"period_days": 30}

        with patch("asyncio.run", return_value=mock_recommendations):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

            result = weekly_optimization_review()

            # Verify database update was called
            mock_cursor.execute.assert_called_once()
            call_args = mock_cursor.execute.call_args[0]
            assert "UPDATE rules_validation_reports" in call_args[0]

            # Verify return value
            assert result["status"] == "completed"
            assert result["recommendation_count"] == 2

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks._get_recent_performance_data")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_weekly_optimization_no_recommendations(
        self,
        mock_agent_class: MagicMock,
        mock_perf_data: MagicMock,
        mock_conn_mgr: MagicMock,
    ) -> None:
        """Weekly optimization with no recommendations should still complete."""
        mock_perf_data.return_value = {"period_days": 30}

        with patch("asyncio.run", return_value=[]):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

            result = weekly_optimization_review()

            assert result["status"] == "completed"
            assert result["recommendation_count"] == 0

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks._get_recent_performance_data")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_weekly_optimization_stores_performance_data(
        self,
        mock_agent_class: MagicMock,
        mock_perf_data: MagicMock,
        mock_conn_mgr: MagicMock,
    ) -> None:
        """Weekly optimization should store performance data."""
        perf_data = {
            "period_days": 30,
            "trade_stats": {"total_trades": 10, "win_rate": 0.6},
        }
        mock_perf_data.return_value = perf_data

        with patch("asyncio.run", return_value=[]):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

            weekly_optimization_review()

            # Verify performance_data was stored
            call_args = mock_cursor.execute.call_args[0]
            from psycopg2.extras import Json

            params = call_args[1]
            perf_data_param = params[1]
            assert isinstance(perf_data_param, Json)

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks._get_recent_performance_data")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_weekly_optimization_handles_exception(
        self, mock_agent_class: MagicMock, mock_perf_data: MagicMock, mock_conn_mgr: MagicMock
    ) -> None:
        """Weekly optimization should handle exceptions gracefully."""
        mock_perf_data.side_effect = Exception("Database error")

        result = weekly_optimization_review()

        assert result["status"] == "error"
        assert "error" in result


class TestPerformanceDataRetrieval:
    """Test _get_recent_performance_data helper function."""

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    def test_get_recent_performance_data_success(self, mock_conn_mgr: MagicMock) -> None:
        """Performance data retrieval should return trade and signal stats."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock trade stats query - return dict-like object
        class MockRow:
            def __init__(self, data: dict[str, Any]) -> None:
                self._data = data

            def __iter__(self) -> Any:
                return iter(self._data.items())

        trade_stats_row = MockRow(
            {
                "total_trades": 10,
                "win_rate": 0.6,
                "avg_pnl": 100.0,
                "std_pnl": 50.0,
                "max_drawdown": 15.0,
            }
        )

        # Mock signal stats query
        signal_stats_rows = [
            MockRow({"signal_classification": "strong_buy", "signal_count": 5, "avg_score": 8.5}),
            MockRow({"signal_classification": "buy", "signal_count": 10, "avg_score": 7.2}),
        ]

        mock_cursor.fetchone.return_value = trade_stats_row
        mock_cursor.fetchall.return_value = signal_stats_rows

        mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

        result = _get_recent_performance_data()

        assert result["period_days"] == 30
        assert "trade_stats" in result
        assert "signal_stats" in result
        assert len(result["signal_stats"]) == 2

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    def test_get_recent_performance_data_handles_exception(self, mock_conn_mgr: MagicMock) -> None:
        """Performance data retrieval should handle exceptions."""
        mock_conn = MagicMock()
        mock_conn._conn.cursor.side_effect = Exception("Connection error")
        mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

        result = _get_recent_performance_data()

        # Should return empty dict on error
        assert result == {}

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    def test_get_recent_performance_data_30_day_window(self, mock_conn_mgr: MagicMock) -> None:
        """Performance data should query last 30 days."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # Mock empty row with dict-like interface
        class MockRow:
            def __init__(self, data: dict[str, Any]) -> None:
                self._data = data

            def __iter__(self) -> Any:
                return iter(self._data.items())

        mock_cursor.fetchone.return_value = MockRow(
            {
                "total_trades": 0,
                "win_rate": None,
                "avg_pnl": None,
                "std_pnl": None,
                "max_drawdown": None,
            }
        )
        mock_cursor.fetchall.return_value = []
        mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

        result = _get_recent_performance_data()

        # Verify 30-day interval was used
        calls = mock_cursor.execute.call_args_list
        assert len(calls) == 2  # Two queries
        for call in calls:
            sql = call[0][0]
            assert "30 days" in sql

        assert result["period_days"] == 30


class TestTaskIntegration:
    """Test integration between validation and optimization tasks."""

    @patch("app.tasks.rules_validation_tasks.get_connection_manager")
    @patch("app.tasks.rules_validation_tasks.RulesValidatorAgent")
    def test_optimization_updates_latest_validation_report(
        self, mock_agent_class: MagicMock, mock_conn_mgr: MagicMock
    ) -> None:
        """Optimization should update most recent validation report."""
        with (
            patch("asyncio.run", return_value=[]),
            patch(
                "app.tasks.rules_validation_tasks._get_recent_performance_data",
                return_value={},
            ),
        ):
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn._conn.cursor.return_value.__enter__.return_value = mock_cursor
            mock_conn_mgr.return_value.connection.return_value.__enter__.return_value = mock_conn

            weekly_optimization_review()

            # Verify UPDATE query targets latest report
            call_args = mock_cursor.execute.call_args[0]
            sql = call_args[0]
            assert "ORDER BY validation_time DESC" in sql
            assert "LIMIT 1" in sql
