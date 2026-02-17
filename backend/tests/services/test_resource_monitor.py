"""Tests for resource monitoring service."""

from __future__ import annotations

from typing import cast

from sqlalchemy.engine import Connection

from app.services.resource_monitor import (
    get_cpu_usage,
    get_db_pool_stats,
    get_disk_usage,
    get_memory_usage,
)
from app.storage.connection import get_connection_manager


def test_get_disk_usage() -> None:
    """Test disk usage returns valid data."""
    result = get_disk_usage()

    assert "total_gb" in result
    assert "used_gb" in result
    assert "free_gb" in result
    assert "percent_used" in result
    assert "status" in result

    assert result["total_gb"] > 0
    assert result["used_gb"] >= 0
    assert result["free_gb"] >= 0
    assert 0 <= result["percent_used"] <= 100
    assert result["status"] in ["ok", "warning", "critical"]


def test_get_memory_usage() -> None:
    """Test memory usage returns valid data."""
    result = get_memory_usage()

    assert "total_gb" in result
    assert "used_gb" in result
    assert "available_gb" in result
    assert "percent_used" in result
    assert "status" in result

    assert result["total_gb"] > 0
    assert result["used_gb"] >= 0
    assert result["available_gb"] >= 0
    assert 0 <= result["percent_used"] <= 100
    assert result["status"] in ["ok", "warning", "critical"]


def test_get_cpu_usage() -> None:
    """Test CPU usage returns valid data."""
    result = get_cpu_usage()

    assert "percent_used" in result
    assert "status" in result
    assert "cores" in result

    assert 0 <= result["percent_used"] <= 100
    assert result["status"] in ["ok", "warning", "critical"]
    assert isinstance(result["cores"], int)
    assert result["cores"] > 0


def test_get_db_pool_stats(clean_database: object) -> None:
    """Test database pool stats returns valid data."""
    mgr = get_connection_manager()
    with mgr.connection() as conn:
        result = get_db_pool_stats(cast(Connection, conn))

        assert "pool_size" in result
        assert "checked_out" in result
        assert "overflow" in result
        assert "percent_used" in result
        assert "status" in result

        assert result["pool_size"] >= 0
        assert result["checked_out"] >= 0
        assert result["overflow"] >= 0
        assert 0 <= result["percent_used"] <= 100
        assert result["status"] in ["ok", "warning", "critical"]


def test_disk_usage_thresholds() -> None:
    """Test disk usage status based on thresholds."""
    result = get_disk_usage()

    # Verify threshold logic
    if result["percent_used"] < 80:
        assert result["status"] == "ok"
    elif result["percent_used"] < 90:
        assert result["status"] == "warning"
    else:
        assert result["status"] == "critical"


def test_memory_usage_thresholds() -> None:
    """Test memory usage status based on thresholds."""
    result = get_memory_usage()

    # Verify threshold logic
    if result["percent_used"] < 85:
        assert result["status"] == "ok"
    elif result["percent_used"] < 95:
        assert result["status"] == "warning"
    else:
        assert result["status"] == "critical"
