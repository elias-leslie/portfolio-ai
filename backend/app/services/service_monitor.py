"""Service monitoring module for detecting and checking process health."""

from __future__ import annotations

import subprocess
import time
from typing import Literal

import httpx
import psutil
from pydantic import BaseModel, Field

from app.constants.services import SERVICE_PROCESS_PATTERNS


class ServiceStatus(BaseModel):
    """Status information for a service/process."""

    service_name: str = Field(description="Name of the service")
    status: Literal["running", "down", "degraded"] = Field(description="Service status")
    pid: int | None = Field(default=None, description="Process ID if running")
    uptime_seconds: int | None = Field(default=None, description="Uptime in seconds")
    memory_mb: int | None = Field(default=None, description="Memory usage in MB")
    message: str = Field(default="", description="Status message or error details")


def get_process_by_pattern(pattern: str) -> int | None:
    """Find process ID by pattern using pgrep.

    Args:
        pattern: Regex pattern to match process command line

    Returns:
        Process ID of the first matching process, or None if not found
    """
    try:
        result = subprocess.run(
            ["pgrep", "-f", pattern],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        if result.returncode == 0 and result.stdout.strip():
            # Return first PID if multiple matches
            pids = result.stdout.strip().split("\n")
            return int(pids[0])

        return None

    except (subprocess.TimeoutExpired, ValueError, subprocess.SubprocessError):
        return None


def get_service_status(
    service_name: str,
    process_pattern: str,
) -> ServiceStatus:
    """Get status of a service by process pattern.

    Args:
        service_name: Human-readable service name
        process_pattern: Regex pattern to match process command line

    Returns:
        ServiceStatus with current service state
    """
    pid = get_process_by_pattern(process_pattern)

    if pid is None:
        return ServiceStatus(
            service_name=service_name,
            status="down",
            message=f"Process not running (pattern: {process_pattern})",
        )

    try:
        process = psutil.Process(pid)

        # Get process info
        create_time = process.create_time()
        uptime_seconds = int(time.time() - create_time)
        memory_bytes = process.memory_info().rss
        memory_mb = int(memory_bytes / (1024 * 1024))

        return ServiceStatus(
            service_name=service_name,
            status="running",
            pid=pid,
            uptime_seconds=uptime_seconds,
            memory_mb=memory_mb,
        )

    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return ServiceStatus(
            service_name=service_name,
            status="down",
            message=f"Process found but not accessible: {e!s}",
        )


def check_backend_api(skip_http_check: bool = False) -> ServiceStatus:
    """Check backend API service status.

    Args:
        skip_http_check: If True, only check process status (fast, avoids self-HTTP calls).
                        If False, also perform HTTP health check (slow, causes congestion).

    Returns:
        ServiceStatus for backend API
    """
    status = get_service_status("portfolio-backend", r"uvicorn.*main:app")

    if status.status == "running" and not skip_http_check:
        # Additional health check: try to ping /health/simple endpoint (avoid circular dependency)
        try:
            start_time = time.time()
            response = httpx.get("http://localhost:8000/health/simple", timeout=2.0)
            latency_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 200:
                if latency_ms > 2000:
                    status.status = "degraded"
                    status.message = f"Slow response ({latency_ms}ms)"
            else:
                status.status = "degraded"
                status.message = f"Health check returned {response.status_code}"

        except httpx.TimeoutException:
            status.status = "degraded"
            status.message = "Health check timeout"
        except httpx.ConnectError:
            status.status = "down"
            status.message = "Cannot connect to API"
        except Exception as e:
            status.status = "degraded"
            status.message = f"Health check error: {e!s}"

    return status


def check_hatchet_worker() -> ServiceStatus:
    """Check Hatchet worker service status.

    Returns:
        ServiceStatus for Hatchet worker
    """
    return get_service_status(
        "portfolio-hatchet-worker",
        SERVICE_PROCESS_PATTERNS["portfolio-hatchet-worker"],
    )


def check_frontend() -> ServiceStatus:
    """Check frontend Next.js status.

    Returns:
        ServiceStatus for frontend
    """
    status = get_service_status(
        "portfolio-frontend",
        SERVICE_PROCESS_PATTERNS["portfolio-frontend"],
    )

    if status.status == "running":
        # Additional check: try to connect to port 3000
        # Next.js dev server runs on HTTP (nginx handles HTTPS externally)
        try:
            response = httpx.get("http://localhost:3000", timeout=2.0)
            if response.status_code not in [200, 304]:
                status.status = "degraded"
                status.message = f"Frontend returned {response.status_code}"

        except httpx.TimeoutException:
            status.status = "degraded"
            status.message = "Frontend timeout"
        except httpx.ConnectError:
            status.status = "down"
            status.message = "Cannot connect to frontend"
        except Exception as e:
            status.status = "degraded"
            status.message = f"Frontend check error: {e!s}"

    return status


def check_redis() -> ServiceStatus:
    """Check Redis server status.

    Returns:
        ServiceStatus for Redis
    """
    status = get_service_status("portfolio-redis", r"redis-server")

    if status.status == "running":
        # Additional check: try redis-cli ping
        try:
            result = subprocess.run(
                ["redis-cli", "ping"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )

            if result.returncode != 0 or result.stdout.strip().upper() != "PONG":
                status.status = "down"
                status.message = "Redis ping failed"

        except subprocess.TimeoutExpired:
            status.status = "degraded"
            status.message = "Redis ping timeout"
        except Exception as e:
            status.status = "degraded"
            status.message = f"Redis check error: {e!s}"

    return status


def check_dev_companion() -> ServiceStatus:
    """Check dev-companion service status.

    Returns:
        ServiceStatus for dev-companion
    """
    status = get_service_status("portfolio-dev-companion", r"dev-companion")

    if status.status == "running":
        # Additional check: try to connect to port 9999
        try:
            response = httpx.get("http://localhost:9999/health", timeout=2.0)
            if response.status_code != 200:
                status.status = "degraded"
                status.message = f"Dev companion returned {response.status_code}"

        except httpx.TimeoutException:
            status.status = "degraded"
            status.message = "Dev companion timeout"
        except httpx.ConnectError:
            # Port not responding but process running - might be starting
            status.status = "degraded"
            status.message = "Dev companion port not responding"
        except Exception as e:
            status.status = "degraded"
            status.message = f"Dev companion check error: {e!s}"

    return status


def get_all_service_statuses(skip_slow_checks: bool = False) -> dict[str, ServiceStatus]:
    """Get status of all monitored services.

    Args:
        skip_slow_checks: If True, skip slow operations like backend HTTP checks (fast).
                         If False, perform all checks including slow ones (detailed status page).

    Returns:
        Dictionary mapping service key to ServiceStatus
    """
    return {
        "portfolio-redis": check_redis(),
        "portfolio-backend": check_backend_api(skip_http_check=skip_slow_checks),
        "portfolio-hatchet-worker": check_hatchet_worker(),
        "portfolio-frontend": check_frontend(),
        "portfolio-dev-companion": check_dev_companion(),
    }
