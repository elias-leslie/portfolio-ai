"""Integration tests for capability Celery tasks."""

from __future__ import annotations

import pytest

from app.storage.connection import get_connection_manager
from app.tasks.capability_tasks import scan_system_capabilities

# analyze_capabilities was removed - tests kept as stubs for potential future implementation


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


@pytest.mark.skip(reason="analyze_capabilities function was removed")
class TestAnalyzeCapabilities:
    """Test analyze_capabilities Celery task (SKIPPED - function removed)."""

    def test_analyze_task_without_api_key(self) -> None:
        """Placeholder - analyze_capabilities was removed."""
        pytest.skip("analyze_capabilities was removed")


@pytest.mark.skip(reason="analyze_capabilities function was removed")
class TestTaskIntegration:
    """Test integration between scan and analyze tasks (SKIPPED - function removed)."""

    def test_scan_then_analyze_workflow(self) -> None:
        """Placeholder - analyze_capabilities was removed."""
        pytest.skip("analyze_capabilities was removed")
