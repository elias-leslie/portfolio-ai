"""System health resource monitoring endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..logging_config import get_logger
from ..services.resource_monitor import (
    get_cpu_usage,
    get_db_pool_stats,
    get_disk_usage,
    get_memory_usage,
)
from ..storage.connection import get_connection_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status", "system"])


class DiskUsageResponse(BaseModel):
    """Disk usage information."""

    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float
    status: str


class MemoryUsageResponse(BaseModel):
    """Memory usage information."""

    total_gb: float
    used_gb: float
    available_gb: float
    percent_used: float
    status: str


class CpuUsageResponse(BaseModel):
    """CPU usage information."""

    percent_used: float
    cores: int
    status: str


class DatabasePoolResponse(BaseModel):
    """Database connection pool information."""

    pool_size: int
    checked_out: int
    overflow: int
    percent_used: float
    status: str


class ResourcesResponse(BaseModel):
    """System resources response."""

    disk: DiskUsageResponse
    memory: MemoryUsageResponse
    cpu: CpuUsageResponse
    database_pool: DatabasePoolResponse
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


@router.get("/resources", response_model=ResourcesResponse)
def get_system_resources() -> ResourcesResponse:
    """Get current system resource usage (disk, memory, CPU, database pool).

    Returns:
        ResourcesResponse: System resource statistics with thresholds
    """
    logger.info("get_system_resources_request")

    try:
        # Get resource statistics
        disk = get_disk_usage()
        memory = get_memory_usage()
        cpu = get_cpu_usage()

        # Get database pool stats
        mgr = get_connection_manager()
        with mgr.connection() as conn:
            db_pool = get_db_pool_stats(conn)  # type: ignore[arg-type]

        # Ensure cores is not None (default to 1 if psutil.cpu_count() returns None)
        cpu_cores = cpu["cores"] if cpu["cores"] is not None else 1

        return ResourcesResponse(
            disk=DiskUsageResponse(**disk),
            memory=MemoryUsageResponse(**memory),
            cpu=CpuUsageResponse(
                percent_used=cpu["percent_used"],
                cores=cpu_cores,
                status=cpu["status"],
            ),
            database_pool=DatabasePoolResponse(**db_pool),
        )

    except Exception as e:
        logger.error("get_system_resources_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Error retrieving system resources: {e!s}"
        ) from e
