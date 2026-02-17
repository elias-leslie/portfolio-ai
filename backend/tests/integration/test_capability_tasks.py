"""Integration tests for capability scan tasks."""

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
    """Test scan_system_capabilities task."""

    def test_scan_task_success(self) -> None:
        """Test that scan task executes successfully."""
        # Run the task synchronously
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
            row = conn.execute("SELECT COUNT(*) FROM db_capabilities").fetchone()
            assert row is not None
            db_count = row[0]
            assert isinstance(db_count, int)
            assert db_count > 0  # Should have discovered some tables

            # Check celery_capabilities (DB table not yet renamed)
            row = conn.execute("SELECT COUNT(*) FROM celery_capabilities").fetchone()
            assert row is not None
            hatchet_count = row[0]
            assert isinstance(hatchet_count, int)
            assert hatchet_count == 0  # Task scanner disabled, no tasks scanned

            # Check api_capabilities
            row = conn.execute("SELECT COUNT(*) FROM api_capabilities").fetchone()
            assert row is not None
            api_count = row[0]
            assert isinstance(api_count, int)
            assert api_count > 0  # Should have discovered API endpoints

    def test_scan_task_result_counts_match(self) -> None:
        """Test that result counts match database counts."""
        result = scan_system_capabilities()

        conn_mgr = get_connection_manager()
        with conn_mgr.connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM db_capabilities").fetchone()
            assert row is not None
            db_count = row[0]
            assert isinstance(db_count, int)

            hatchet_count = 0  # Task scanner disabled, no tasks scanned

            row = conn.execute("SELECT COUNT(*) FROM api_capabilities").fetchone()
            assert row is not None
            api_count = row[0]
            assert isinstance(api_count, int)

            assert result["db_tables_scanned"] == db_count
            assert result["celery_tasks_scanned"] == hatchet_count
            assert result["api_endpoints_scanned"] == api_count
            assert result["total_capabilities"] == db_count + hatchet_count + api_count

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

            assert db_result is not None
            total, unique_tables = db_result
            assert total == unique_tables  # total == unique (no duplicates)


@pytest.mark.skip(reason="analyze_capabilities function was removed")
class TestAnalyzeCapabilities:
    """Test analyze_capabilities task (SKIPPED - function removed)."""

    def test_analyze_task_without_api_key(self) -> None:
        """Placeholder - analyze_capabilities was removed."""
        pytest.skip("analyze_capabilities was removed")


@pytest.mark.skip(reason="analyze_capabilities function was removed")
class TestTaskIntegration:
    """Test integration between scan and analyze tasks (SKIPPED - function removed)."""

    def test_scan_then_analyze_workflow(self) -> None:
        """Placeholder - analyze_capabilities was removed."""
        pytest.skip("analyze_capabilities was removed")
