"""Status and monitoring endpoints for real-time service information."""

from __future__ import annotations

import re
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/status", tags=["status"])

# Log file paths for each service
# Service names match health endpoint (underscore format)
LOG_PATHS: dict[str, str] = {
    "backend": "/tmp/portfolio-backend.log",
    "celery_worker": "/tmp/portfolio-celery-worker.log",
    "celery_beat": "/tmp/portfolio-celery-beat.log",
    "frontend": "/tmp/portfolio-frontend.log",
    "redis": "/var/log/redis/redis-server.log",  # System redis log
    # Aliases for backward compatibility (hyphen format)
    "celery-worker": "/tmp/portfolio-celery-worker.log",
    "celery-beat": "/tmp/portfolio-celery-beat.log",
}

# ANSI escape code pattern for stripping colors
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class LogResponse(BaseModel):
    """Response model for log endpoint."""

    service: str = Field(description="Service name")
    lines: list[str] = Field(description="Log lines (last N lines)")
    total_lines: int = Field(description="Total number of lines returned")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Response timestamp"
    )


def tail_log_file(file_path: str, num_lines: int = 100) -> list[str]:
    """Read last N lines from a log file efficiently using deque.

    Args:
        file_path: Path to log file
        num_lines: Number of lines to read from end (default 100)

    Returns:
        List of log lines (ANSI codes stripped)

    Raises:
        FileNotFoundError: If log file doesn't exist
        PermissionError: If log file can't be read
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Log file not found: {file_path}")

    try:
        with path.open("r") as f:
            # Use deque with maxlen for efficient tail operation
            lines = deque(f, maxlen=num_lines)

            # Strip ANSI escape codes for clean output
            cleaned_lines = [ANSI_ESCAPE.sub("", line.rstrip()) for line in lines]

            return cleaned_lines

    except PermissionError as e:
        raise PermissionError(f"Permission denied reading log file: {file_path}") from e


@router.get("/logs/{service}", response_model=LogResponse)
async def get_service_logs(service: str, lines: int = 100) -> LogResponse:
    """Get recent log lines for a service.

    Args:
        service: Service name (backend, celery-worker, celery-beat, frontend)
        lines: Number of lines to retrieve (default 100, max 1000)

    Returns:
        LogResponse with recent log lines

    Raises:
        HTTPException: 400 if service invalid, 404 if log file not found, 403 if permission denied
    """
    # Validate service name (security: whitelist approach)
    if service not in LOG_PATHS:
        valid_services = ", ".join(LOG_PATHS.keys())
        raise HTTPException(
            status_code=400, detail=f"Invalid service. Must be one of: {valid_services}"
        )

    # Validate line count
    if lines < 1 or lines > 1000:
        raise HTTPException(status_code=400, detail="Lines must be between 1 and 1000")

    log_path = LOG_PATHS[service]

    try:
        log_lines = tail_log_file(log_path, num_lines=lines)

        return LogResponse(
            service=service,
            lines=log_lines,
            total_lines=len(log_lines),
        )

    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404, detail=f"Log file not found for service: {service}"
        ) from e

    except PermissionError as e:
        raise HTTPException(
            status_code=403, detail=f"Permission denied reading logs for service: {service}"
        ) from e

    except Exception as e:
        logger.error("get_service_logs_error", service=service, error=str(e))
        raise HTTPException(status_code=500, detail=f"Error reading logs: {e!s}") from e
