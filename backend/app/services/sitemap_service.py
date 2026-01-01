"""Sitemap Service - Discovery and health monitoring for all endpoints.

This module provides:
- Discovery of backend API endpoints (via OpenAPI)
- Discovery of frontend pages (via crawling)
- Health checks (HTTP status, console errors/warnings)
- CRUD operations for sitemap entries
- Import from existing api_capabilities table
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ..logging_config import get_logger
from ..storage.connection import get_connection_manager
from ..storage.sitemap_storage import get_sitemap_storage
from ..utils.formatters import calculate_duration_ms
from ..utils.port_discovery import (
    PortDiscovery,
    get_port_for_service,
)
from .health_check_strategies import (
    CheckDecision,
    HealthCheckStrategy,
)

logger = get_logger(__name__)

# Configuration
HTTP_TIMEOUT = 10  # seconds

# Network configuration (from environment or fallback to defaults)
FRONTEND_HOST = os.getenv("FRONTEND_HOST", "192.168.8.233")  # Network IP for SSR routing
BACKEND_HOST = os.getenv("BACKEND_HOST", "localhost")

# Timeouts for health checks
HEALTH_CHECK_TIMEOUT_NORMAL = 10  # seconds for normal endpoints
HEALTH_CHECK_TIMEOUT_PROBE = (
    5  # seconds for lightweight probe checks (enough to verify route exists)
)

# Frontend crawl patterns to skip (static assets and API calls)
FRONTEND_CRAWL_SKIP_PATTERNS = [
    "/api/",
    "/_next/",
    "/static/",
    ".js",
    ".css",
    ".png",
    ".jpg",
]

# WebSocket probe paths to check
WEBSOCKET_PROBE_PATHS = ["/ws", "/ws/{session_id}", "/socket.io"]

# Status codes that indicate WebSocket endpoint exists
WS_ENDPOINT_STATUS_CODES = (403, 426, 400)


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
        test_path = re.sub(r"\{[^}]+\}", "test-probe-value", path)

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


def _extract_openapi_endpoints(
    openapi: dict[str, Any], port: int, service_name: str | None = None
) -> list[dict[str, Any]]:
    """Extract endpoint entries from an OpenAPI specification.

    Args:
        openapi: Parsed OpenAPI JSON
        port: Port number for the endpoints
        service_name: Optional service name to include

    Returns:
        List of endpoint dicts ready for sitemap_entries
    """
    endpoints = []
    paths = openapi.get("paths", {})

    for path, methods in paths.items():
        for method, details in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue
            # Skip health/docs endpoints
            if any(x in path for x in ["/health", "/docs", "/openapi", "/redoc"]):
                continue

            entry = {
                "port": port,
                "path": path,
                "method": method.upper(),
                "entry_type": "api_endpoint",
                "source": "openapi",
                "title": details.get("summary") or details.get("operationId"),
            }
            if service_name:
                entry["service_name"] = service_name
            endpoints.append(entry)

    return endpoints


class SitemapService:
    """Discovers and monitors sitemap entries."""

    def __init__(self) -> None:
        self.conn_mgr = get_connection_manager()
        self._port_discovery = PortDiscovery()
        self._storage = get_sitemap_storage()

    @property
    def frontend_port(self) -> int:
        """Get the frontend port (dynamically discovered or fallback)."""
        return get_port_for_service("frontend") or 3000

    def get_discovered_ports(self) -> list[dict[str, Any]]:
        """Get all discovered ports with their metadata.

        Returns:
            List of port info dicts
        """
        ports = self._port_discovery.get_all_ports()
        return [
            {
                "port": p.port,
                "service_name": p.service_name,
                "service_type": p.service_type,
                "source": p.source,
                "description": p.description,
            }
            for p in ports.values()
        ]

    def refresh_port_discovery(self) -> list[dict[str, Any]]:
        """Force refresh of port discovery cache.

        Returns:
            List of newly discovered port info dicts
        """
        self._port_discovery.clear_cache()
        return self.get_discovered_ports()

    # =========================================================================
    # Discovery Methods
    # =========================================================================

    async def discover_all_openapi_endpoints(self) -> list[dict[str, Any]]:
        """Discover API endpoints from ALL ports that have OpenAPI specs.

        Iterates through all discovered ports (from systemd) and checks each
        for an OpenAPI spec, extracting endpoints from any that have one.

        Returns:
            List of discovered endpoint dicts from all ports
        """
        logger.info("sitemap_discover_all_openapi_start")
        all_discovered = []

        # Get all discovered ports
        ports = self._port_discovery.get_all_ports()

        # Ports to check for OpenAPI (backend types and websocket services)
        openapi_candidates = [
            p for p in ports.values() if p.service_type in ("backend", "websocket", "unknown")
        ]

        logger.info(
            "sitemap_openapi_candidates",
            count=len(openapi_candidates),
            ports=[p.port for p in openapi_candidates],
        )

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for port_info in openapi_candidates:
                port = port_info.port
                try:
                    response = await client.get(f"http://{BACKEND_HOST}:{port}/openapi.json")
                    if response.status_code != 200:
                        continue

                    openapi = response.json()
                    port_endpoints = _extract_openapi_endpoints(
                        openapi, port, port_info.service_name
                    )
                    all_discovered.extend(port_endpoints)

                    logger.info(
                        "sitemap_openapi_port_complete",
                        port=port,
                        service=port_info.service_name,
                        count=len(port_endpoints),
                    )

                except Exception as e:
                    logger.debug("sitemap_openapi_port_failed", port=port, error=str(e))

        logger.info("sitemap_discover_all_openapi_complete", total=len(all_discovered))
        return all_discovered

    async def discover_websocket_endpoints(self) -> list[dict[str, Any]]:
        """Discover WebSocket endpoints from services.

        Checks known WebSocket paths (/ws, /ws/{id}) on ports that
        might have WebSocket support.

        Returns:
            List of discovered WebSocket endpoint dicts
        """
        logger.info("sitemap_discover_websocket_start")
        discovered = []

        # Get ports that might have WebSocket
        ports = self._port_discovery.get_all_ports()
        ws_candidates = [
            p for p in ports.values() if p.service_type in ("websocket", "backend", "unknown")
        ]

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            for port_info in ws_candidates:
                port = port_info.port

                # Try WebSocket upgrade on common paths
                for ws_path in WEBSOCKET_PROBE_PATHS:
                    try:
                        # Check if endpoint exists (even without upgrade)
                        # FastAPI WebSocket endpoints return 403 for non-WS requests
                        test_path = ws_path.replace("{session_id}", "test")
                        response = await client.get(
                            f"http://{BACKEND_HOST}:{port}{test_path}",
                            headers={"Upgrade": "websocket", "Connection": "Upgrade"},
                        )

                        # 403 or 426 indicates WebSocket endpoint exists
                        if response.status_code in WS_ENDPOINT_STATUS_CODES:
                            discovered.append(
                                {
                                    "port": port,
                                    "path": ws_path,
                                    "method": "WS",
                                    "entry_type": "websocket",
                                    "source": "probe",
                                    "title": f"WebSocket - {port_info.service_name}",
                                    "service_name": port_info.service_name,
                                }
                            )
                            logger.info(
                                "sitemap_websocket_found",
                                port=port,
                                path=ws_path,
                                service=port_info.service_name,
                            )

                    except Exception as e:
                        logger.debug(
                            "sitemap_websocket_probe_failed", port=port, path=ws_path, error=str(e)
                        )

        logger.info("sitemap_discover_websocket_complete", count=len(discovered))
        return discovered

    async def discover_frontend_pages(self, max_depth: int = 3) -> list[dict[str, Any]]:
        """Crawl frontend to discover pages by following links.

        Args:
            max_depth: Maximum crawl depth

        Returns:
            List of discovered page dicts
        """
        logger.info("sitemap_discover_frontend_start")
        discovered = []
        visited: set[str] = set()
        to_visit: list[tuple[str, int]] = [("/", 0)]  # (path, depth)

        frontend_port = self.frontend_port
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=True) as client:
            while to_visit:
                path, depth = to_visit.pop(0)

                if path in visited or depth > max_depth:
                    continue
                visited.add(path)

                try:
                    url = f"http://{FRONTEND_HOST}:{frontend_port}{path}"
                    response = await client.get(url)

                    if response.status_code == 200:
                        # Get page title from HTML
                        title = None
                        title_match = re.search(
                            r"<title>([^<]+)</title>", response.text, re.IGNORECASE
                        )
                        if title_match:
                            title = title_match.group(1).strip()

                        discovered.append(
                            {
                                "port": frontend_port,
                                "path": path,
                                "method": "GET",
                                "entry_type": "frontend_page",
                                "source": "crawler",
                                "title": title,
                            }
                        )

                        # Extract internal links for crawling
                        if depth < max_depth:
                            links = re.findall(r'href=["\']([^"\']+)["\']', response.text)
                            for link in links:
                                # Only follow internal links, skip static assets and API calls
                                if (
                                    link.startswith("/")
                                    and not link.startswith("//")
                                    and not any(x in link for x in FRONTEND_CRAWL_SKIP_PATTERNS)
                                ):
                                    clean_path = link.split("?")[0].split("#")[0]
                                    if clean_path not in visited:
                                        to_visit.append((clean_path, depth + 1))

                except Exception as e:
                    logger.debug("sitemap_crawl_page_failed", path=path, error=str(e))

        logger.info("sitemap_discover_frontend_complete", count=len(discovered))
        return discovered

    def discover_nextjs_routes(self, frontend_dir: str | None = None) -> list[dict[str, Any]]:
        """Parse Next.js app directory to discover all routes.

        This provides complete route discovery including:
        - Static routes (/watchlist, /portfolio)
        - Dynamic routes (/ideas/[id] -> /ideas/{id})
        - Tab variations detected from useSearchParams

        Args:
            frontend_dir: Path to frontend directory, defaults to ~/portfolio-ai/frontend

        Returns:
            List of discovered route dicts
        """
        logger.info("sitemap_discover_nextjs_start")
        discovered: list[dict[str, Any]] = []

        if frontend_dir is None:
            frontend_dir = str(Path.home() / "portfolio-ai" / "frontend")

        app_dir = Path(frontend_dir) / "app"
        if not app_dir.exists():
            logger.warning("sitemap_nextjs_app_dir_not_found", path=str(app_dir))
            return discovered

        # Find all page.tsx files
        page_files = list(app_dir.glob("**/page.tsx"))
        logger.info("sitemap_nextjs_pages_found", count=len(page_files))

        for page_file in page_files:
            try:
                # Convert file path to route
                # app/page.tsx -> /
                # app/watchlist/page.tsx -> /watchlist
                # app/ideas/[id]/page.tsx -> /ideas/{id}
                relative_path = page_file.relative_to(app_dir)
                route_parts = list(relative_path.parts[:-1])  # Remove page.tsx

                if not route_parts:
                    route = "/"
                else:
                    # Convert [param] to {param} for template notation
                    converted_parts = []
                    for part in route_parts:
                        if part.startswith("[") and part.endswith("]"):
                            # Dynamic segment: [id] -> {id}
                            param_name = part[1:-1]
                            converted_parts.append(f"{{{param_name}}}")
                        else:
                            converted_parts.append(part)
                    route = "/" + "/".join(converted_parts)

                # Get page title from file (look for metadata or component name)
                title = self._extract_page_title(page_file)

                # Check for tab variations
                tab_values = self._extract_tab_values(page_file)

                # Add base route
                discovered.append(
                    {
                        "port": self.frontend_port,
                        "path": route,
                        "method": "GET",
                        "entry_type": "frontend_page",
                        "source": "nextjs_app",
                        "title": title,
                        "has_dynamic_segment": "{" in route,
                    }
                )

                # Add tab variations as separate entries
                for tab in tab_values:
                    discovered.append(
                        {
                            "port": self.frontend_port,
                            "path": f"{route}?tab={tab}",
                            "method": "GET",
                            "entry_type": "frontend_page",
                            "source": "nextjs_app",
                            "title": f"{title} - {tab.title()}" if title else tab.title(),
                            "parent_path": route,
                        }
                    )

            except Exception as e:
                logger.debug("sitemap_nextjs_parse_failed", file=str(page_file), error=str(e))

        logger.info("sitemap_discover_nextjs_complete", count=len(discovered))
        return discovered

    def _extract_page_title(self, page_file: Path) -> str | None:
        """Extract page title from Next.js page file.

        Looks for:
        - metadata.title export
        - PageHeader title prop
        - Component function name

        Args:
            page_file: Path to page.tsx file

        Returns:
            Title string or None
        """
        try:
            content = page_file.read_text()

            # Look for metadata title
            # export const metadata = { title: "Watchlist" }
            metadata_match = re.search(r'title:\s*["\']([^"\']+)["\']', content)
            if metadata_match:
                return metadata_match.group(1)

            # Look for PageHeader title prop
            # <PageHeader title="Watchlist"
            header_match = re.search(r'<PageHeader[^>]*title=["\']([^"\']+)["\']', content)
            if header_match:
                return header_match.group(1)

            # Fallback: derive from directory name
            parent_dir = page_file.parent.name
            if parent_dir != "app":
                # Convert kebab-case to Title Case
                return parent_dir.replace("-", " ").replace("_", " ").title()

            return "Home"

        except Exception:
            return None

    def _extract_tab_values(self, page_file: Path) -> list[str]:
        """Extract tab values from page that uses useSearchParams.

        Looks for:
        - TabValue type definitions
        - Tabs component with TabsTrigger values
        - searchParams.get("tab") usage

        Args:
            page_file: Path to page.tsx file

        Returns:
            List of tab value strings
        """
        tabs: list[str] = []
        try:
            content = page_file.read_text()

            # Check if page uses tabs
            if "useSearchParams" not in content and "searchParams" not in content:
                return tabs

            # Look for TabValue type definition (e.g. type TabValue = "x" | "y")
            tabvalue_match = re.search(r"type\s+TabValue\s*=\s*([^;]+);", content)
            if tabvalue_match:
                values_str = tabvalue_match.group(1)
                # Extract quoted strings
                tabs = re.findall(r'["\']([^"\']+)["\']', values_str)
                return tabs

            # Look for TabsTrigger values
            # <TabsTrigger value="workflows">
            trigger_matches = re.findall(r'<TabsTrigger[^>]*value=["\']([^"\']+)["\']', content)
            if trigger_matches:
                return list(set(trigger_matches))

        except Exception:
            pass

        return tabs

    async def run_discovery(self) -> dict[str, Any]:
        """Run comprehensive discovery across all service types.

        Discovery methods:
        - OpenAPI: All ports with /openapi.json (backend, dev-companion, etc.)
        - Frontend: Crawl pages and parse Next.js app directory
        - WebSocket: Probe for WS endpoints on applicable ports

        Returns:
            Summary of discovery results
        """
        logger.info("sitemap_full_discovery_start")

        # Run async discoveries in parallel
        all_openapi_task = asyncio.create_task(self.discover_all_openapi_endpoints())
        frontend_task = asyncio.create_task(self.discover_frontend_pages())
        websocket_task = asyncio.create_task(self.discover_websocket_endpoints())

        all_openapi_entries = await all_openapi_task
        frontend_entries = await frontend_task
        websocket_entries = await websocket_task

        # Run sync discoveries
        nextjs_entries = self.discover_nextjs_routes()

        # Combine all entries
        all_entries = all_openapi_entries + frontend_entries + websocket_entries + nextjs_entries
        saved = 0

        with self.conn_mgr.connection() as conn:
            for entry in all_entries:
                try:
                    conn.execute(
                        """
                        INSERT INTO sitemap_entries (port, path, method, entry_type, source, title, discovered_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (port, path, method) DO UPDATE SET
                            title = COALESCE(EXCLUDED.title, sitemap_entries.title),
                            source = EXCLUDED.source,
                            updated_at = NOW()
                    """,
                        [
                            entry["port"],
                            entry["path"],
                            entry["method"],
                            entry["entry_type"],
                            entry["source"],
                            entry.get("title"),
                        ],
                    )
                    saved += 1
                except Exception as e:
                    logger.debug("sitemap_save_entry_failed", path=entry["path"], error=str(e))

            conn.commit()

        result = {
            "openapi_discovered": len(all_openapi_entries),
            "frontend_discovered": len(frontend_entries),
            "websocket_discovered": len(websocket_entries),
            "nextjs_discovered": len(nextjs_entries),
            "total_saved": saved,
        }

        logger.info("sitemap_full_discovery_complete", **result)
        return result

    # =========================================================================
    # Health Check Methods
    # =========================================================================

    def _save_health_result(self, entry_id: int, result: HealthCheckResult) -> None:
        """Save health check result to database (entry update + history).

        Args:
            entry_id: ID of sitemap entry
            result: Health check result to save
        """
        with self.conn_mgr.connection() as conn:
            # Update sitemap_entries
            conn.execute(
                """
                UPDATE sitemap_entries SET
                    health_status = %s,
                    console_errors = %s,
                    console_warnings = %s,
                    http_status = %s,
                    response_time_ms = %s,
                    last_error_message = %s,
                    last_checked_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
            """,
                [
                    result.health_status,
                    result.console_errors,
                    result.console_warnings,
                    result.http_status,
                    result.response_time_ms,
                    result.last_error_message,
                    entry_id,
                ],
            )

            # Insert into history
            conn.execute(
                """
                INSERT INTO sitemap_health_history
                    (sitemap_entry_id, checked_at, health_status, console_errors, console_warnings,
                     http_status, response_time_ms, error_details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
                [
                    entry_id,
                    datetime.now(UTC),
                    result.health_status,
                    result.console_errors,
                    result.console_warnings,
                    result.http_status,
                    result.response_time_ms,
                    json.dumps(result.error_details) if result.error_details else None,
                ],
            )

            conn.commit()

    async def check_entry_health(self, entry_id: int) -> dict[str, Any]:
        """Check health of a single sitemap entry.

        For frontend pages: HTTP fetch + console capture
        For API endpoints: HTTP fetch only

        Args:
            entry_id: ID of sitemap entry to check

        Returns:
            Health check result dict
        """
        # Get entry details
        entry = self.get_entry(entry_id)
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
        entries, _total = self.get_entries(limit=1000)

        checked = 0
        healthy = 0
        warnings = 0
        errors = 0

        for entry in entries:
            result = await self.check_entry_health(entry["id"])
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

    # =========================================================================
    # CRUD Operations (delegated to storage layer)
    # =========================================================================

    def get_entries(
        self,
        port: int | None = None,
        health_status: str | None = None,
        entry_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get sitemap entries with filtering. Delegates to storage layer."""
        return self._storage.get_entries(
            port=port,
            health_status=health_status,
            entry_type=entry_type,
            limit=limit,
            offset=offset,
        )

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        """Get single entry by ID. Delegates to storage layer."""
        return self._storage.get_entry(entry_id)

    def get_health_summary(self) -> dict[str, Any]:
        """Get aggregate health statistics. Delegates to storage layer."""
        return self._storage.get_health_summary()

    def register_entry(
        self,
        port: int,
        path: str,
        method: str = "GET",
        entry_type: str = "manual",
        title: str | None = None,
    ) -> dict[str, Any] | None:
        """Manually register a new sitemap entry. Delegates to storage layer."""
        return self._storage.register_entry(
            port=port,
            path=path,
            method=method,
            entry_type=entry_type,
            title=title,
        )

    def delete_entry(self, entry_id: int) -> bool:
        """Remove a sitemap entry. Delegates to storage layer."""
        return self._storage.delete_entry(entry_id)

    # =========================================================================
    # Maintenance (delegated to storage layer)
    # =========================================================================

    def cleanup_old_history(self, days: int = 7) -> int:
        """Delete health history older than specified days. Delegates to storage layer."""
        return self._storage.cleanup_old_history(days)

    def get_history_stats(self) -> dict[str, Any]:
        """Get health history statistics for maintenance UI. Delegates to storage layer."""
        return self._storage.get_history_stats()
