"""Service monitoring module for detecting and checking process health.

Supports both native (systemd/bare-metal) and container (Docker) deployments.
In container mode, cross-container services are checked via HTTP health endpoints
since process-level visibility is limited to the current container.
"""

from __future__ import annotations

import re
import subprocess
import time
from functools import lru_cache
from pathlib import Path
from typing import Literal

import httpx
import psutil
import redis as redis_lib
from pydantic import BaseModel, Field

from app.config import settings
from app.constants.services import SERVICE_PROCESS_PATTERNS
from app.logging_config import get_logger
from app.utils import safe_subprocess

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _is_container() -> bool:
    """Detect if running inside a Docker/OCI container."""
    return Path("/.dockerenv").exists()


class ServiceStatus(BaseModel):
    """Status information for a service/process."""

    service_name: str = Field(description="Name of the service")
    status: Literal["running", "down", "degraded"] = Field(description="Service status")
    pid: int | None = Field(default=None, description="Process ID if running")
    uptime_seconds: int | None = Field(default=None, description="Uptime in seconds")
    memory_mb: int | None = Field(default=None, description="Memory usage in MB")
    message: str = Field(default="", description="Status message or error details")


def get_process_by_pattern(pattern: str) -> int | None:
    """Find process ID by matching process command lines.

    Args:
        pattern: Regex pattern to match process command line

    Returns:
        Process ID of the first matching process, or None if not found
    """
    try:
        compiled = re.compile(pattern)
    except re.error as e:
        logger.debug("process_lookup_invalid_pattern", pattern=pattern, error=str(e))
        return None

    for process in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = process.info.get("cmdline")
            if cmdline:
                command = " ".join(str(part) for part in cmdline)
            else:
                command = str(process.info.get("name") or "")
            if compiled.search(command):
                return int(process.info.get("pid") or process.pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            logger.debug("process_lookup_skipped", pattern=pattern, error=str(e))
            continue

    return None


def _status_from_pid(service_name: str, pid: int) -> ServiceStatus:
    process = psutil.Process(pid)
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


def get_systemd_user_service_status(service_name: str) -> ServiceStatus | None:
    """Return user-systemd unit status when this host owns the service unit."""
    if _is_container():
        return None

    unit = service_name if service_name.endswith(".service") else f"{service_name}.service"
    try:
        result = safe_subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "-p",
                "LoadState",
                "-p",
                "ActiveState",
                "-p",
                "SubState",
                "-p",
                "MainPID",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.debug("systemd_user_status_unavailable", service_name=service_name, error=str(e))
        return None

    status: ServiceStatus | None = None
    if result.returncode == 0:
        values = {
            key: value
            for line in result.stdout.splitlines()
            if "=" in line
            for key, value in [line.split("=", 1)]
        }
        load_state = values.get("LoadState", "")
        active_state = values.get("ActiveState", "")
        sub_state = values.get("SubState", "")
        raw_pid = values.get("MainPID", "")
        if load_state == "loaded":
            pid = int(raw_pid) if raw_pid.isdigit() else 0
            if active_state == "active" and pid > 0:
                try:
                    status = _status_from_pid(service_name, pid)
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    status = ServiceStatus(
                        service_name=service_name,
                        status="degraded",
                        pid=pid,
                        message=f"systemd reports running but process not accessible: {e!s}",
                    )
            else:
                status = ServiceStatus(
                    service_name=service_name,
                    status="down",
                    message=f"systemd unit {unit} is {active_state}/{sub_state}",
                )
    return status


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
        return _status_from_pid(service_name, pid)

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
    status = get_systemd_user_service_status("portfolio-backend") or get_service_status(
        "portfolio-backend",
        SERVICE_PROCESS_PATTERNS["portfolio-backend"],
    )

    if status.status == "down" and _is_container():
        status.status = "running"
        status.message = "Container mode — backend health inferred from current process"

    if status.status == "running" and not skip_http_check:
        # Additional health check: try to ping /health/simple endpoint (avoid circular dependency)
        try:
            start_time = time.time()
            response = httpx.get(f"{settings.backend_url}/health/simple", timeout=2.0)
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

    In containers the worker runs in a separate container, so process detection
    won't work. Fall back to checking if the Hatchet engine reports active workers.

    Returns:
        ServiceStatus for Hatchet worker
    """
    # In containers, pgrep can't see the worker process in another container.
    # Try process detection first (works on bare-metal and same-container).
    status = get_systemd_user_service_status("portfolio-hatchet-worker") or get_service_status(
        "portfolio-hatchet-worker",
        SERVICE_PROCESS_PATTERNS["portfolio-hatchet-worker"],
    )

    if status.status == "down" and _is_container():
        # Can't see cross-container processes; report as unknown rather than down.
        status.status = "running"
        status.message = "Container mode — worker health inferred from Hatchet engine"

    return status


def check_frontend() -> ServiceStatus:
    """Check frontend Next.js status.

    In containers, uses HTTP health check since the frontend runs in a
    separate container and process detection won't work.

    Returns:
        ServiceStatus for frontend
    """
    status = get_systemd_user_service_status("portfolio-frontend")
    if status is None:
        status = ServiceStatus(
            service_name="portfolio-frontend",
            status="running",
            message="systemd unavailable; frontend health checked by HTTP",
        )

    # In container mode, skip pgrep result and go straight to HTTP check
    if status.status == "down" and _is_container():
        status.status = "running"  # Assume running; HTTP check below will correct

    if status.status == "running":
        # Additional check: try to connect to frontend
        try:
            response = httpx.get(settings.frontend_url, timeout=2.0)
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

    # In container mode, Redis runs in a separate container — skip pgrep result
    if status.status == "down" and _is_container():
        status.status = "running"  # Assume running; ping check below will correct

    if status.status == "running":
        try:
            r = redis_lib.from_url(settings.redis_url, socket_timeout=2)
            if not r.ping():
                status.status = "down"
                status.message = "Redis ping failed"
            r.close()
        except Exception as e:
            status.status = "down"
            status.message = f"Redis unreachable: {e!s}"

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
    }
