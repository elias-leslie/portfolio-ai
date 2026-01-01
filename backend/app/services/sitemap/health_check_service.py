"""Sitemap Health Check Service - Endpoint health monitoring.

This module provides:
- Health checks for sitemap entries (HTTP status, response time)
- Error and warning detection
- Health result persistence
- Batch health checking
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import httpx

from ...logging_config import get_logger
from ...storage.sitemap_storage import get_sitemap_storage
from ...utils.formatters import calculate_duration_ms
from ...utils.port_discovery import get_port_for_service
from ...utils.url_helpers import substitute_path_params
from ..health_check_strategies import (
    CheckDecision,
    HealthCheckStrategy,
)

logger = get_logger(__name__)

# Network configuration (from environment or fallback to defaults)
FRONTEND_HOST = os.getenv("FRONTEND_HOST", "192.168.8.233")  # Network IP for SSR routing
BACKEND_HOST = os.getenv("BACKEND_HOST", "localhost")

# Timeouts for health checks
HEALTH_CHECK_TIMEOUT_NORMAL = 10  # seconds for normal endpoints
HEALTH_CHECK_TIMEOUT_PROBE = (
    5  # seconds for lightweight probe checks (enough to verify route exists)
)

# Batch size limit for health checks
MAX_HEALTH_CHECK_BATCH_SIZE = 1000  # Limit prevents long-running health checks


def _interpret_response(
    response: httpx.Response, is_probe: bool, probe_pattern: str | None
) -> tuple[bool, str | None]:
    """Interpret HTTP response to determine if it's an error.

    Returns:
        Tuple of (is_error, error_message)
    """
    if is_probe:
        # PROBE CHECK: Any response = route exists = not down
        is_path_param_probe = probe_pattern == "path-param"
        if response.status_code >= 500 and not is_path_param_probe:
            return True, f"HTTP {response.status_code}"
        return False, f"Probe OK ({probe_pattern}) - HTTP {response.status_code}"

    # NORMAL CHECK: More strict validation
    if response.status_code >= 500:
        return True, f"HTTP {response.status_code}"

    if response.status_code == 404:
        try:
            body = response.json()
            if body.get("detail") == "Not Found":
                return True, "Route not found"
        except Exception:
            return True, "HTTP 404"

    return False, None


def _build_check_url(path: str, port: int, frontend_port: int) -> tuple[str, bool]:
    """Build URL for health check, substituting path parameters.

    Args:
        path: Endpoint path (may contain {param} placeholders)
        port: Port number for the endpoint
        frontend_port: Frontend port (for host selection)

    Returns:
        Tuple of (url, has_path_params)
    """
    test_path = path
    has_path_params = "{" in path
    if has_path_params:
        # Substitute all path parameters with test values
        test_path = substitute_path_params(path)

    host = FRONTEND_HOST if port == frontend_port else BACKEND_HOST
    url = f"http://{host}:{port}{test_path}"
    return url, has_path_params


def _handle_check_exception(
    e: Exception, is_probe: bool, probe_pattern: str | None, timeout: float
) -> tuple[int, int, str, dict[str, str]]:
    """Handle exception from health check and return error details.

    Args:
        e: Exception that occurred
        is_probe: Whether this was a probe check
        probe_pattern: Probe pattern if applicable
        timeout: Timeout value used

    Returns:
        Tuple of (console_errors, console_warnings, last_error_message, error_details)
    """
    error_details = {"exception": str(e)}

    if isinstance(e, httpx.TimeoutException):
        # Timeout handling depends on endpoint type
        if is_probe:
            # Probe timeout = endpoint is slow but might still work
            return 0, 1, f"Probe timeout ({timeout}s) - {probe_pattern}", error_details
        # Normal timeout = endpoint is too slow
        return 1, 0, f"Timeout after {timeout}s", error_details

    if isinstance(e, httpx.ConnectError):
        # Connection refused/failed = endpoint is DOWN
        return 1, 0, f"Connection failed: {e!s}"[:500], error_details

    # Other exceptions
    return 1, 0, str(e)[:500], error_details


class HealthCheckResult:
    """Container for health check results."""

    __slots__ = (
        "console_errors",
        "console_warnings",
        "error_details",
        "health_status",
        "http_status",
        "last_error_message",
        "response_time_ms",
    )

    def __init__(
        self,
        health_status: str = "healthy",
        console_errors: int = 0,
        console_warnings: int = 0,
        http_status: int | None = None,
        response_time_ms: int | None = None,
        last_error_message: str | None = None,
        error_details: dict[str, Any] | None = None,
    ):
        self.health_status = health_status
        self.console_errors = console_errors
        self.console_warnings = console_warnings
        self.http_status = http_status
        self.response_time_ms = response_time_ms
        self.last_error_message = last_error_message
        self.error_details = error_details or {}

    def determine_status(self) -> None:
        """Set health_status based on error/warning counts."""
        if self.console_errors > 0:
            self.health_status = "error"
        elif self.console_warnings > 0:
            self.health_status = "warning"
        else:
            self.health_status = "healthy"


class SitemapHealthCheckService:
    """Monitors health of sitemap entries."""

    def __init__(self) -> None:
        self._storage = get_sitemap_storage()

    @property
    def frontend_port(self) -> int:
        """Get the frontend port (dynamically discovered or fallback)."""
        return get_port_for_service("frontend") or 3000

    def _save_health_result(self, entry_id: int, result: HealthCheckResult) -> None:
        """Save health check result to database (entry update + history).

        Args:
            entry_id: ID of sitemap entry
            result: Health check result to save
        """
        self._storage.save_health_check_result(
            entry_id=entry_id,
            health_status=result.health_status,
            console_errors=result.console_errors,
            console_warnings=result.console_warnings,
            http_status=result.http_status,
            response_time_ms=result.response_time_ms,
            last_error_message=result.last_error_message,
            error_details=result.error_details,
        )

    async def check_entry_health(
        self, entry_id: int, entry: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Check health of a single sitemap entry.

        For frontend pages: HTTP fetch + console capture
        For API endpoints: HTTP fetch only

        Args:
            entry_id: ID of sitemap entry to check
            entry: Optional pre-fetched entry dict (to avoid redundant DB lookup)

        Returns:
            Health check result dict
        """
        # Get entry details if not provided
        if entry is None:
            entry = self._storage.get_entry(entry_id)
        if not entry:
            return {"success": False, "error": "Entry not found"}

        port = entry["port"]
        path = entry["path"]
        method = entry["method"]

        # Build URL using helper
        url, has_path_params = _build_check_url(path, port, self.frontend_port)

        console_errors = 0
        console_warnings = 0
        http_status = None
        response_time_ms = None
        error_details: dict[str, Any] = {}
        last_error_message = None

        # Use centralized strategy for check type determination
        decision: CheckDecision = HealthCheckStrategy.get_check_decision(
            path, method, has_path_params
        )

        # 1. Skip entirely: streaming, mutating, or circular-risk endpoints
        if decision.should_skip:
            skip_result = HealthCheckResult(
                health_status="healthy",
                http_status=0,  # Indicates skipped, not actually checked
                last_error_message=decision.skip_message,
            )
            self._save_health_result(entry_id, skip_result)
            return {
                "success": True,
                "entry_id": entry_id,
                "health_status": skip_result.health_status,
                "console_errors": 0,
                "console_warnings": 0,
                "http_status": skip_result.http_status,
                "response_time_ms": None,
                "error": None,
            }

        # 2. Determine timeout based on endpoint type
        # Probe endpoints get short timeout to avoid waiting for expensive operations
        timeout = HEALTH_CHECK_TIMEOUT_PROBE if decision.is_probe else HEALTH_CHECK_TIMEOUT_NORMAL

        try:
            # HTTP health check - probe or full depending on endpoint
            async with httpx.AsyncClient(timeout=timeout) as client:
                request_start = datetime.now(UTC)
                response = await client.request(method, url)
                response_time_ms = calculate_duration_ms(request_start, datetime.now(UTC))
                http_status = response.status_code

                # Determine if this is an error using helper
                is_error, last_error_message = _interpret_response(
                    response, decision.is_probe, decision.probe_pattern
                )
                if is_error:
                    console_errors = 1

        except Exception as e:
            # Handle all exceptions using helper
            console_errors, console_warnings, last_error_message, error_details = (
                _handle_check_exception(e, decision.is_probe, decision.probe_pattern, timeout)
            )

        # Build and save result
        result = HealthCheckResult(
            console_errors=console_errors,
            console_warnings=console_warnings,
            http_status=http_status,
            response_time_ms=response_time_ms,
            last_error_message=last_error_message,
            error_details=error_details,
        )
        result.determine_status()
        self._save_health_result(entry_id, result)

        return {
            "success": True,
            "entry_id": entry_id,
            "health_status": result.health_status,
            "console_errors": result.console_errors,
            "console_warnings": result.console_warnings,
            "http_status": result.http_status,
            "response_time_ms": result.response_time_ms,
        }

    async def check_all_health(self) -> dict[str, Any]:
        """Check health of all sitemap entries.

        Returns:
            Summary of health check results
        """
        logger.info("sitemap_check_all_health_start")

        # Get all entries
        entries, _total = self._storage.get_entries(limit=MAX_HEALTH_CHECK_BATCH_SIZE)

        checked = 0
        healthy = 0
        warnings = 0
        errors = 0

        for entry in entries:
            result = await self.check_entry_health(entry["id"], entry)
            checked += 1

            if result.get("health_status") == "healthy":
                healthy += 1
            elif result.get("health_status") == "warning":
                warnings += 1
            else:
                errors += 1

        result = {
            "checked": checked,
            "healthy": healthy,
            "warnings": warnings,
            "errors": errors,
        }

        logger.info("sitemap_check_all_health_complete", **result)
        return result
