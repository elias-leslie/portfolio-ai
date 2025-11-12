"""System health and service management endpoints."""

from __future__ import annotations

import asyncio
import subprocess
from datetime import UTC, datetime
from pathlib import Path

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


class RestartServicesResponse(BaseModel):
    """Response from restarting services."""

    success: bool = Field(description="Whether the operation succeeded")
    message: str = Field(description="Status message")


@router.post("/restart-services", response_model=RestartServicesResponse)
async def restart_services() -> RestartServicesResponse:
    """Restart all Portfolio AI services.

    Uses nohup to run restart script in background to avoid killing itself.
    The backend will restart itself as part of this operation.

    Returns:
        RestartServicesResponse: Status of the operation

    Raises:
        HTTPException: 500 if operation fails
    """
    try:
        restart_script = "/home/kasadis/portfolio-ai/scripts/restart.sh"
        logger.info("restart_services_start", script=restart_script)

        # Run restart in background with nohup to avoid killing the process that's running it
        # The script will restart the backend, which would kill this request otherwise
        subprocess.Popen(
            ["nohup", "bash", restart_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Give a moment for the script to start
        await asyncio.sleep(0.5)

        logger.info("restart_services_triggered")

        return RestartServicesResponse(
            success=True,
            message="Services are restarting. This will take about 10 seconds. Refresh the page after.",
        )

    except Exception as e:
        logger.error("restart_services_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error triggering restart: {e!s}") from e


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

        return ResourcesResponse(
            disk=DiskUsageResponse(**disk),
            memory=MemoryUsageResponse(**memory),
            cpu=CpuUsageResponse(**cpu),
            database_pool=DatabasePoolResponse(**db_pool),
        )

    except Exception as e:
        logger.error("get_system_resources_error", error=str(e))
        raise HTTPException(
            status_code=500, detail=f"Error retrieving system resources: {e!s}"
        ) from e


class ServiceRestartResponse(BaseModel):
    """Response for service restart operation."""

    success: bool
    service: str
    message: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


@router.post("/services/{service}/restart", response_model=ServiceRestartResponse)
def restart_service(service: str) -> ServiceRestartResponse:
    """Restart a specific service.

    Args:
        service: Service name (backend, celery_worker, celery_beat, frontend, redis)

    Returns:
        ServiceRestartResponse: Result of restart operation
    """
    # Map service names from health endpoint to restart script names
    service_name_map = {
        "backend": "backend",
        "celery_worker": "celery",
        "celery_beat": "beat",
        "frontend": "frontend",
        "redis": "redis",
    }

    # Accept both underscore and non-underscore versions
    mapped_service = service_name_map.get(service, service)

    # Whitelist of valid mapped service names
    valid_services = ["backend", "celery", "beat", "frontend", "redis"]

    if mapped_service not in valid_services:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid service name. Valid services: {', '.join(service_name_map.keys())}",
        )

    logger.info("restart_service_request", service=service, mapped_service=mapped_service)

    try:
        # Call restart script with mapped service name
        # __file__ is backend/app/api/status_system.py, go up 4 levels to project root
        script_path = Path(__file__).parent.parent.parent.parent / "scripts" / "restart-service.sh"
        subprocess.run(
            [str(script_path), mapped_service],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )

        logger.info("restart_service_success", service=service, mapped_service=mapped_service)
        return ServiceRestartResponse(
            success=True,
            service=service,
            message=f"Service {service} restarted successfully",
        )

    except subprocess.TimeoutExpired as e:
        logger.error("restart_service_timeout", service=service)
        raise HTTPException(
            status_code=504, detail="Service restart timed out after 30 seconds"
        ) from e

    except subprocess.CalledProcessError as e:
        logger.error("restart_service_failed", service=service, error=e.stderr)
        raise HTTPException(
            status_code=500,
            detail=f"Service restart failed: {e.stderr or 'Unknown error'}",
        ) from e

    except Exception as e:
        logger.error("restart_service_error", service=service, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error restarting service: {e!s}") from e
