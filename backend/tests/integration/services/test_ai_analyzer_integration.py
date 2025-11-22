"""Integration tests for AI analyzer with CLI.

Tests full analysis pipeline with mocked CLI responses and real database.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.ai_analyzer import CapabilityAnalyzer
from app.storage.connection import get_connection_manager


@pytest.fixture(autouse=True)
def cleanup_test_data() -> None:
    """Clean up test data before and after each test."""
    conn_mgr = get_connection_manager()
    with conn_mgr.connection() as conn:
        conn.execute("DELETE FROM capability_insights WHERE table_name LIKE 'test_%'")
        conn.commit()

    yield

    with conn_mgr.connection() as conn:
        conn.execute("DELETE FROM capability_insights WHERE table_name LIKE 'test_%'")
        conn.commit()


def test_full_analysis_pipeline_with_cli() -> None:
    """Test complete analysis pipeline with mocked CLI response."""
    # Mock CLI response
    mock_insights = [
        {
            "capability_type": "db",
            "capability_id": 1,
            "table_name": "test_table",
            "insight_type": "data_quality",
            "severity": "high",
            "finding": "Test finding",
            "expected_behavior": "Expected behavior",
            "actual_behavior": "Actual behavior",
            "impact": "Test impact",
            "suggested_fix": "Test fix",
            "reference_data": {"files": ["test.py"]},
            "ai_confidence": 0.85,
        }
    ]

    mock_cli_response = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": json.dumps(mock_insights),
    }

    # Mock subprocess.run to return our CLI response
    mock_result = MagicMock()
    mock_result.stdout = json.dumps(mock_cli_response)
    mock_result.returncode = 0

    with (
        patch("subprocess.run", return_value=mock_result),
        patch("shutil.which", return_value="/usr/local/bin/claude"),
    ):
        # Create analyzer
        conn_mgr = get_connection_manager()
        analyzer = CapabilityAnalyzer(conn_mgr)

        # Mock capabilities (would normally be loaded from DB)
        with patch.object(
            analyzer,
            "load_capabilities",
            return_value={
                "db_capabilities": [
                    {
                        "id": 1,
                        "table_name": "test_table",
                        "category": "test",
                        "row_count": 100,
                        "total_columns": 5,
                        "columns": ["id", "name", "value", "created_at", "updated_at"],
                        "columns_with_data": 5,
                        "columns_mostly_null": [],
                        "completeness_pct": 100.0,
                        "date_range_start": None,
                        "date_range_end": None,
                        "expected_freshness": "24h",
                        "days_since_update": 0,
                        "freshness_status": "fresh",
                        "last_scanned_at": "2025-11-16T00:00:00",
                    }
                ],
                "celery_capabilities": [],
                "api_capabilities": [],
            },
        ):
            # Run analysis
            insights = analyzer.analyze()

            # Verify insights were returned
            assert len(insights) == 1
            assert insights[0]["capability_type"] == "db"
            assert insights[0]["table_name"] == "test_table"
            assert insights[0]["ai_confidence"] == 0.85

    # Verify insights were saved to database
    with conn_mgr.connection() as conn:
        result = conn.execute(
            """
            SELECT capability_type, table_name, ai_confidence
            FROM capability_insights
            WHERE table_name = 'test_table'
            """
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "db"
        assert row[1] == "test_table"
        assert float(row[2]) == 0.85


def test_cli_timeout_handling() -> None:
    """Test that CLI timeout is handled gracefully."""
    import subprocess

    with (
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="claude", timeout=300),
        ),
        patch("shutil.which", return_value="/usr/local/bin/claude"),
    ):
        conn_mgr = get_connection_manager()
        analyzer = CapabilityAnalyzer(conn_mgr)

        with (
            patch.object(
                analyzer,
                "load_capabilities",
                return_value={
                    "db_capabilities": [],
                    "celery_capabilities": [],
                    "api_capabilities": [],
                },
            ),
            pytest.raises(subprocess.TimeoutExpired),
        ):
            analyzer.analyze()


def test_cli_error_handling() -> None:
    """Test that CLI errors are handled gracefully."""
    # Mock CLI error response
    mock_cli_response = {
        "type": "result",
        "subtype": "error",
        "is_error": True,
        "result": "Test error message",
    }

    mock_result = MagicMock()
    mock_result.stdout = json.dumps(mock_cli_response)
    mock_result.returncode = 0

    with (
        patch("subprocess.run", return_value=mock_result),
        patch("shutil.which", return_value="/usr/local/bin/claude"),
    ):
        conn_mgr = get_connection_manager()
        analyzer = CapabilityAnalyzer(conn_mgr)

        with (
            patch.object(
                analyzer,
                "load_capabilities",
                return_value={
                    "db_capabilities": [],
                    "celery_capabilities": [],
                    "api_capabilities": [],
                },
            ),
            pytest.raises(ValueError, match="CLI returned error"),
        ):
            analyzer.analyze()


def test_confidence_filtering() -> None:
    """Test that insights below confidence threshold are filtered out."""
    # Mock CLI response with varying confidence levels
    mock_insights = [
        {
            "capability_type": "db",
            "capability_id": 1,
            "table_name": "high_confidence",
            "insight_type": "data_quality",
            "severity": "high",
            "finding": "High confidence finding",
            "expected_behavior": "Expected",
            "actual_behavior": "Actual",
            "impact": "Impact",
            "suggested_fix": "Fix",
            "reference_data": {},
            "ai_confidence": 0.85,  # Above threshold
        },
        {
            "capability_type": "db",
            "capability_id": 2,
            "table_name": "low_confidence",
            "insight_type": "data_quality",
            "severity": "low",
            "finding": "Low confidence finding",
            "expected_behavior": "Expected",
            "actual_behavior": "Actual",
            "impact": "Impact",
            "suggested_fix": "Fix",
            "reference_data": {},
            "ai_confidence": 0.65,  # Below threshold (0.70)
        },
    ]

    mock_cli_response = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": json.dumps(mock_insights),
    }

    mock_result = MagicMock()
    mock_result.stdout = json.dumps(mock_cli_response)
    mock_result.returncode = 0

    with (
        patch("subprocess.run", return_value=mock_result),
        patch("shutil.which", return_value="/usr/local/bin/claude"),
    ):
        conn_mgr = get_connection_manager()
        analyzer = CapabilityAnalyzer(conn_mgr)

        with patch.object(
            analyzer,
            "load_capabilities",
            return_value={
                "db_capabilities": [],
                "celery_capabilities": [],
                "api_capabilities": [],
            },
        ):
            insights = analyzer.analyze()

            # Should only return high confidence insight
            assert len(insights) == 1
            assert insights[0]["table_name"] == "high_confidence"
            assert insights[0]["ai_confidence"] == 0.85
