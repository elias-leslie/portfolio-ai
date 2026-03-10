"""System resource monitoring service.

Provides functions to monitor:
- Disk usage
- Memory usage
- CPU usage
- Database connection pool statistics
"""

import shutil
from typing import TypedDict

import psutil
from sqlalchemy.engine import Connection


class DiskUsageDict(TypedDict):
    """Disk usage statistics."""

    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float
    status: str


class MemoryUsageDict(TypedDict):
    """Memory usage statistics."""

    total_gb: float
    used_gb: float
    available_gb: float
    percent_used: float
    status: str


class CPUUsageDict(TypedDict):
    """CPU usage statistics."""

    percent_used: float
    cores: int | None
    status: str


class PoolStatsDict(TypedDict):
    """Database connection pool statistics."""

    pool_size: int
    checked_out: int
    overflow: int
    percent_used: float
    status: str


def get_disk_usage() -> DiskUsageDict:
    """Get disk usage statistics for root filesystem.

    Returns:
        Dict containing:
            - total_gb: Total disk space in GB
            - used_gb: Used disk space in GB
            - free_gb: Free disk space in GB
            - percent_used: Percentage of disk space used
            - status: "ok" | "warning" | "critical"
    """
    usage = shutil.disk_usage("/")

    # Convert bytes to GB
    total_gb = usage.total / (1024**3)
    used_gb = usage.used / (1024**3)
    free_gb = usage.free / (1024**3)
    percent_used = (usage.used / usage.total) * 100

    # Determine status based on thresholds
    if percent_used >= 90:
        status = "critical"
    elif percent_used >= 80:
        status = "warning"
    else:
        status = "ok"

    return {
        "total_gb": round(total_gb, 2),
        "used_gb": round(used_gb, 2),
        "free_gb": round(free_gb, 2),
        "percent_used": round(percent_used, 2),
        "status": status,
    }


def get_memory_usage() -> MemoryUsageDict:
    """Get memory usage statistics.

    Returns:
        Dict containing:
            - total_gb: Total memory in GB
            - used_gb: Used memory in GB
            - available_gb: Available memory in GB
            - percent_used: Percentage of memory used
            - status: "ok" | "warning" | "critical"
    """
    memory = psutil.virtual_memory()

    # Convert bytes to GB
    total_gb = memory.total / (1024**3)
    used_gb = memory.used / (1024**3)
    available_gb = memory.available / (1024**3)
    percent_used = memory.percent

    # Determine status based on thresholds
    if percent_used >= 95:
        status = "critical"
    elif percent_used >= 85:
        status = "warning"
    else:
        status = "ok"

    return {
        "total_gb": round(total_gb, 2),
        "used_gb": round(used_gb, 2),
        "available_gb": round(available_gb, 2),
        "percent_used": round(percent_used, 2),
        "status": status,
    }


def get_cpu_usage() -> CPUUsageDict:
    """Get CPU usage statistics.

    Returns:
        Dict containing:
            - percent_used: Current CPU usage percentage
            - cores: Number of CPU cores
            - status: "ok" | "warning" | "critical"
    """
    # Get CPU usage (1 second sampling period for more accurate reading)
    percent_used = psutil.cpu_percent(interval=1.0)
    cores = psutil.cpu_count()

    # Determine status based on thresholds
    if percent_used >= 90:
        status = "critical"
    elif percent_used >= 80:
        status = "warning"
    else:
        status = "ok"

    return {
        "percent_used": round(percent_used, 2),
        "cores": cores,
        "status": status,
    }


def get_db_pool_stats(conn: Connection) -> PoolStatsDict:
    """Get database connection pool statistics.

    Args:
        conn: SQLAlchemy database connection (or PostgreSQLConnectionWrapper)

    Returns:
        Dict containing:
            - pool_size: Configured pool size
            - checked_out: Number of connections currently in use
            - overflow: Number of overflow connections
            - percent_used: Percentage of pool in use
            - status: "ok" | "warning" | "critical"
    """
    # Handle both raw SQLAlchemy connections and wrapped connections
    if hasattr(conn, "engine"):
        pool = conn.engine.pool
    elif hasattr(conn, "_engine"):
        pool = conn._engine.pool
    else:
        raise ValueError("Connection object does not have accessible engine")

    # Get pool statistics
    pool_size = pool.size()
    checked_out = pool.checkedout()
    overflow = pool.overflow()

    # Calculate percentage
    if pool_size > 0:
        percent_used = (checked_out / pool_size) * 100
    else:
        percent_used = 0.0

    # Determine status based on thresholds
    if percent_used >= 90:
        status = "critical"
    elif percent_used >= 75:
        status = "warning"
    else:
        status = "ok"

    return {
        "pool_size": pool_size,
        "checked_out": checked_out,
        "overflow": overflow,
        "percent_used": round(percent_used, 2),
        "status": status,
    }
