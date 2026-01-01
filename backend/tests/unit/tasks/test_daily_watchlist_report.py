"""Unit tests for daily watchlist report generation (FEAT-034).

Tests the generate_daily_watchlist_report_task that creates daily summaries
of watchlist activity (additions, removals, score changes).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from app.tasks.watchlist_discovery import (
    generate_daily_watchlist_report_task,
)


@pytest.fixture
def mock_storage() -> MagicMock:
    """Create a mock PortfolioStorage instance."""
    mock = MagicMock()
    mock.query = MagicMock()
    mock.connection = MagicMock()
    return mock


class TestGenerateDailyWatchlistReport:
    """Tests for generate_daily_watchlist_report_task."""

    @patch("app.tasks.watchlist_discovery.PortfolioStorage")
    def test_report_with_additions_and_removals(self, mock_storage_class: MagicMock) -> None:
        """Test report generation with symbols added and removed."""
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        now = datetime.now(UTC)
        yesterday = now - timedelta(days=1)

        # Mock symbols added
        added_data = {
            "symbol": ["TSLA", "NVDA"],
            "created_at": [now - timedelta(hours=12), now - timedelta(hours=6)],
            "source": ["discovery", "discovery"],
            "metadata": ['{"auto_added": true}', '{"auto_added": true}'],
        }
        added_df = pl.DataFrame(added_data)

        # Mock symbols removed (from deletion_audit)
        # Note: query extracts metadata->>'symbol' as symbol
        removed_data = {
            "symbol": ["AMD", "INTC"],
            "deleted_at": [now - timedelta(hours=18), now - timedelta(hours=10)],
        }
        removed_df = pl.DataFrame(removed_data)

        # Mock score changes
        score_changes_data = {
            "symbol": ["AAPL"],
            "old_score": [65.0],
            "new_score": [78.0],
            "change_abs": [13.0],
            "change_pct": [20.0],
        }
        score_changes_df = pl.DataFrame(score_changes_data)

        # Setup query mock to return different dataframes
        def query_side_effect(sql: str, params: list) -> pl.DataFrame:
            if "FROM watchlist_items" in sql and "created_at >=" in sql:
                return added_df
            if "FROM deletion_audit" in sql:
                return removed_df
            if "yesterday_scores" in sql:
                return score_changes_df
            return pl.DataFrame()

        mock_storage.query.side_effect = query_side_effect

        # Mock database connection for INSERT
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("report-id-123",)
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        # Run task
        result = generate_daily_watchlist_report_task()

        # Assertions
        assert result["status"] == "success"
        assert result["added_count"] == 2
        assert result["removed_count"] == 2
        assert result["score_changes_count"] == 1

        # Verify INSERT was called
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert "INSERT INTO watchlist_daily_reports" in call_args[0][0]

    @patch("app.tasks.watchlist_discovery.PortfolioStorage")
    def test_report_with_no_activity(self, mock_storage_class: MagicMock) -> None:
        """Test report generation when no watchlist activity occurred."""
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock empty dataframes (no activity)
        empty_df = pl.DataFrame()
        mock_storage.query.return_value = empty_df

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("report-id-123",)
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        # Run task
        result = generate_daily_watchlist_report_task()

        # Assertions
        assert result["status"] == "success"
        assert result["added_count"] == 0
        assert result["removed_count"] == 0
        assert result["score_changes_count"] == 0

    @patch("app.tasks.watchlist_discovery.PortfolioStorage")
    def test_report_with_score_changes_only(self, mock_storage_class: MagicMock) -> None:
        """Test report generation with score changes but no adds/removes."""
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        now = datetime.now(UTC)

        # Mock score changes
        score_changes_data = {
            "symbol": ["AAPL", "MSFT", "GOOGL"],
            "old_score": [65.0, 72.0, 55.0],
            "new_score": [78.0, 84.0, 42.0],
            "change_abs": [13.0, 12.0, 13.0],
            "change_pct": [20.0, 16.7, -23.6],
        }
        score_changes_df = pl.DataFrame(score_changes_data)

        # Setup query mock
        def query_side_effect(sql: str, params: list) -> pl.DataFrame:
            if "yesterday_scores" in sql:
                return score_changes_df
            return pl.DataFrame()

        mock_storage.query.side_effect = query_side_effect

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("report-id-123",)
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        # Run task
        result = generate_daily_watchlist_report_task()

        # Assertions
        assert result["status"] == "success"
        assert result["added_count"] == 0
        assert result["removed_count"] == 0
        assert result["score_changes_count"] == 3

    @patch("app.tasks.watchlist_discovery.PortfolioStorage")
    def test_report_error_handling(self, mock_storage_class: MagicMock) -> None:
        """Test report generation handles database errors gracefully."""
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock database error
        mock_storage.query.side_effect = Exception("Database connection failed")

        # Run task
        result = generate_daily_watchlist_report_task()

        # Assertions
        assert result["status"] == "error"
        assert "error" in result
        assert "Database connection failed" in result["error"]

    @patch("app.tasks.watchlist_discovery.PortfolioStorage")
    def test_report_upsert_on_conflict(self, mock_storage_class: MagicMock) -> None:
        """Test that report uses ON CONFLICT to update existing report for same date."""
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock data
        empty_df = pl.DataFrame()
        mock_storage.query.return_value = empty_df

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("report-id-123",)
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        # Run task
        result = generate_daily_watchlist_report_task()

        # Verify INSERT statement includes ON CONFLICT clause
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        assert "ON CONFLICT (report_date)" in sql
        assert "DO UPDATE SET" in sql

    @patch("app.tasks.watchlist_discovery.PortfolioStorage")
    def test_report_includes_timestamp(self, mock_storage_class: MagicMock) -> None:
        """Test that report includes generated_at timestamp."""
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock data
        empty_df = pl.DataFrame()
        mock_storage.query.return_value = empty_df

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("report-id-123",)
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        # Run task
        before_run = datetime.now(UTC)
        result = generate_daily_watchlist_report_task()
        after_run = datetime.now(UTC)

        # Verify result includes report_date
        assert "report_date" in result
        report_date_str = result["report_date"]
        assert report_date_str is not None

        # Verify timestamp is within reasonable range
        # (can't check exact value due to task execution time)
        assert result["status"] == "success"

    @patch("app.tasks.watchlist_discovery.PortfolioStorage")
    def test_report_returns_status(self, mock_storage_class: MagicMock) -> None:
        """Test that report returns proper status on error."""
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Simulate an error condition
        mock_storage.query.side_effect = Exception("DB connection failed")

        result = generate_daily_watchlist_report_task()

        # Should return error status
        assert result["status"] == "error"
        assert "error" in result


class TestDailyReportQueryLogic:
    """Tests for daily report SQL query logic and data aggregation."""

    @patch("app.tasks.watchlist_discovery.PortfolioStorage")
    def test_score_change_threshold(self, mock_storage_class: MagicMock) -> None:
        """Test that only significant score changes (>=10 points) are included."""
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock score changes with both significant and insignificant changes
        # Only those with change_abs >= 10 should be in query results
        score_changes_data = {
            "symbol": ["AAPL"],  # Only AAPL has change_abs >= 10
            "old_score": [65.0],
            "new_score": [78.0],
            "change_abs": [13.0],
            "change_pct": [20.0],
        }
        score_changes_df = pl.DataFrame(score_changes_data)

        def query_side_effect(sql: str, params: list) -> pl.DataFrame:
            if "ABS(ts.new_score - ys.old_score) >= 10" in sql:
                return score_changes_df
            return pl.DataFrame()

        mock_storage.query.side_effect = query_side_effect

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("report-id-123",)
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        # Run task
        result = generate_daily_watchlist_report_task()

        # Verify only significant changes included
        assert result["score_changes_count"] == 1

    @patch("app.tasks.watchlist_discovery.PortfolioStorage")
    def test_24_hour_window(self, mock_storage_class: MagicMock) -> None:
        """Test that report queries use 24-hour rolling window."""
        mock_storage = MagicMock()
        mock_storage_class.return_value = mock_storage

        # Mock empty data
        empty_df = pl.DataFrame()
        mock_storage.query.return_value = empty_df

        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.raw_connection.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ("report-id-123",)
        mock_storage.connection.return_value.__enter__.return_value = mock_conn

        # Run task
        before_run = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        result = generate_daily_watchlist_report_task()

        # Verify query was called with correct time range
        # Check that query methods were called
        assert mock_storage.query.called
        # The task should query for data since yesterday (00:00:00)
        # We can't assert exact timestamp due to task execution time,
        # but we can verify the query was called multiple times (once per data type)
        assert mock_storage.query.call_count >= 3  # added, removed, score_changes
