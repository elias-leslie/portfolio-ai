"""Integration tests for capability Celery tasks."""

from __future__ import annotations

import pytest

from app.storage.connection import get_connection_manager
from app.tasks.capability_tasks import analyze_capabilities, scan_system_capabilities


@pytest.fixture(autouse=True)
def setup_test_environment() -> None:
    """Setup test environment for capability tasks."""
    # Clean up capability tables before each test
    conn_mgr = get_connection_manager()
    with conn_mgr.connection() as conn:
        conn.execute("TRUNCATE TABLE capability_notes CASCADE")
        conn.execute("TRUNCATE TABLE capability_insights CASCADE")
        conn.execute("TRUNCATE TABLE api_capabilities CASCADE")
        conn.execute("TRUNCATE TABLE celery_capabilities CASCADE")
        conn.execute("TRUNCATE TABLE db_capabilities CASCADE")
        conn.commit()


class TestScanSystemCapabilities:
    """Test scan_system_capabilities Celery task."""

    def test_scan_task_success(self) -> None:
        """Test that scan task executes successfully."""
        # Run the task synchronously (not via Celery)
        result = scan_system_capabilities()

        # Verify result structure
        assert "status" in result
        assert "db_tables_scanned" in result
        assert "celery_tasks_scanned" in result
        assert "api_endpoints_scanned" in result
        assert "total_capabilities" in result
        assert "scan_duration_seconds" in result

        # Task should succeed
        assert result["status"] == "success"
        assert result["error"] is None

    def test_scan_task_populates_database(self) -> None:
        """Test that scan task populates database tables."""
        # Run scan
        result = scan_system_capabilities()

        assert result["status"] == "success"

        # Verify data was inserted
        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            # Check db_capabilities
            db_count = conn.execute("SELECT COUNT(*) FROM db_capabilities").fetchone()[0]
            assert db_count > 0  # Should have discovered some tables

            # Check celery_capabilities
            celery_count = conn.execute("SELECT COUNT(*) FROM celery_capabilities").fetchone()[0]
            assert celery_count > 0  # Should have discovered scheduled tasks

            # Check api_capabilities
            api_count = conn.execute("SELECT COUNT(*) FROM api_capabilities").fetchone()[0]
            assert api_count > 0  # Should have discovered API endpoints

    def test_scan_task_result_counts_match(self) -> None:
        """Test that result counts match database counts."""
        result = scan_system_capabilities()

        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            db_count = conn.execute("SELECT COUNT(*) FROM db_capabilities").fetchone()[0]
            celery_count = conn.execute("SELECT COUNT(*) FROM celery_capabilities").fetchone()[0]
            api_count = conn.execute("SELECT COUNT(*) FROM api_capabilities").fetchone()[0]

            assert result["db_tables_scanned"] == db_count
            assert result["celery_tasks_scanned"] == celery_count
            assert result["api_endpoints_scanned"] == api_count
            assert result["total_capabilities"] == db_count + celery_count + api_count

    def test_scan_task_upsert_behavior(self) -> None:
        """Test that scan task updates existing records (UPSERT)."""
        # Run scan twice
        result1 = scan_system_capabilities()
        result2 = scan_system_capabilities()

        # Both should succeed
        assert result1["status"] == "success"
        assert result2["status"] == "success"

        # Counts should be the same (no duplicates)
        assert result1["total_capabilities"] == result2["total_capabilities"]

        # Verify no duplicates in database
        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            # Check for unique table names in db_capabilities
            db_result = conn.execute(
                """
                SELECT COUNT(*) as total, COUNT(DISTINCT table_name) as unique_tables
                FROM db_capabilities
            """
            ).fetchone()

            assert db_result[0] == db_result[1]  # total == unique (no duplicates)


class TestAnalyzeCapabilities:
    """Test analyze_capabilities Celery task."""

    def test_analyze_task_without_api_key(self) -> None:
        """Test that analyze task handles missing API key gracefully."""
        import os

        # Temporarily remove API key
        original_key = os.environ.get("ANTHROPIC_API_KEY")
        if "ANTHROPIC_API_KEY" in os.environ:
            del os.environ["ANTHROPIC_API_KEY"]

        try:
            # Run analyze task (should handle missing key gracefully)
            result = analyze_capabilities()

            # Task should return error status
            assert result["status"] == "error"
            assert result["insights_generated"] == 0

        finally:
            # Restore API key
            if original_key:
                os.environ["ANTHROPIC_API_KEY"] = original_key

    def test_analyze_task_with_no_capabilities(self) -> None:
        """Test analyze task with empty database (no capabilities to analyze)."""
        # Database is empty (from fixture)
        # Skip if no API key
        import os

        if not os.environ.get("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

        # Run analyze task
        result = analyze_capabilities()

        # Should succeed but generate no insights (no data to analyze)
        assert result["status"] == "success"
        # May generate 0 or some insights depending on AI response
        assert result["insights_generated"] >= 0

    @pytest.mark.skipif(
        "ANTHROPIC_API_KEY" not in __import__("os").environ,
        reason="ANTHROPIC_API_KEY not set",
    )
    def test_analyze_task_after_scan(self) -> None:
        """Test analyze task after populating capabilities via scan.

        This test requires ANTHROPIC_API_KEY to be set.
        It will make actual AI API calls (costs money).
        """
        # First, run scan to populate capabilities
        scan_result = scan_system_capabilities()
        assert scan_result["status"] == "success"
        assert scan_result["total_capabilities"] > 0

        # Now run analysis
        analyze_result = analyze_capabilities()

        # Verify result structure
        assert "status" in analyze_result
        assert "insights_generated" in analyze_result
        assert "insights_saved" in analyze_result
        assert "analysis_duration_seconds" in analyze_result

        # Analysis should succeed
        assert analyze_result["status"] == "success"

        # Should generate some insights (AI will likely find issues)
        # Note: This is not guaranteed, depends on AI analysis
        assert analyze_result["insights_generated"] >= 0

        # If insights were generated, verify they're in database
        if analyze_result["insights_saved"] > 0:
            conn_mgr = get_connection_manager()
            with conn_mgr.connection() as conn:
                insight_count = conn.execute("SELECT COUNT(*) FROM capability_insights").fetchone()[
                    0
                ]

                assert insight_count == analyze_result["insights_saved"]

    def test_analyze_task_result_structure(self) -> None:
        """Test that analyze task returns correct result structure."""
        import os

        if not os.environ.get("ANTHROPIC_API_KEY"):
            pytest.skip("ANTHROPIC_API_KEY not set")

        result = analyze_capabilities()

        # Verify all required fields exist
        required_fields = [
            "status",
            "insights_generated",
            "insights_saved",
            "analysis_duration_seconds",
            "error",
        ]

        for field in required_fields:
            assert field in result

        # Status should be success or error
        assert result["status"] in ["success", "error"]

        # Duration should be positive
        assert result["analysis_duration_seconds"] > 0


class TestTaskIntegration:
    """Test integration between scan and analyze tasks."""

    @pytest.mark.skipif(
        "ANTHROPIC_API_KEY" not in __import__("os").environ,
        reason="ANTHROPIC_API_KEY not set",
    )
    def test_scan_then_analyze_workflow(self) -> None:
        """Test complete workflow: scan -> analyze.

        This simulates the scheduled task flow (scan at 03:00, analyze at 03:15).
        """
        # Step 1: Scan capabilities
        scan_result = scan_system_capabilities()

        assert scan_result["status"] == "success"
        assert scan_result["total_capabilities"] > 0

        # Step 2: Analyze capabilities
        analyze_result = analyze_capabilities()

        assert analyze_result["status"] == "success"

        # Step 3: Verify data integrity
        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            # Verify capabilities exist
            total_caps = (
                conn.execute("SELECT COUNT(*) FROM db_capabilities").fetchone()[0]
                + conn.execute("SELECT COUNT(*) FROM celery_capabilities").fetchone()[0]
                + conn.execute("SELECT COUNT(*) FROM api_capabilities").fetchone()[0]
            )

            assert total_caps == scan_result["total_capabilities"]

            # Verify insights exist (if any were generated)
            insight_count = conn.execute("SELECT COUNT(*) FROM capability_insights").fetchone()[0]

            assert insight_count == analyze_result["insights_saved"]
